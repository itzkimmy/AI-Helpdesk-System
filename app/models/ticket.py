"""Ticket model with status state machine, SLA tracking, and optimistic locking."""

from datetime import datetime, timezone
from enum import Enum as PyEnum

from app.extensions import db


class TicketCategory(PyEnum):
    """Six exact ticket categories per specification."""
    NETWORK = 'Network'
    HARDWARE = 'Hardware'
    SOFTWARE = 'Software'
    ACCESS_ACCOUNTS = 'Access and Accounts'
    EMAIL_COMMUNICATION = 'Email and Communication'
    SERVER_INFRASTRUCTURE = 'Server and Infrastructure'


class TicketPriority(PyEnum):
    """Four exact priorities per specification."""
    CRITICAL = 'Critical'
    HIGH = 'High'
    MEDIUM = 'Medium'
    LOW = 'Low'


class TicketStatus(PyEnum):
    """
    Ticket status state machine.

    Valid transitions:
      NEW -> ASSIGNED
      ASSIGNED -> IN_PROGRESS
      IN_PROGRESS -> PENDING_CLIENT
      IN_PROGRESS -> RESOLVED
      PENDING_CLIENT -> IN_PROGRESS
      RESOLVED -> CLOSED
      CLOSED -> (none, unless admin reopens)

    Admin-only:
      Any -> NEW (reopen)
      ASSIGNED -> NEW (unassign)
    """
    NEW = 'New'
    ASSIGNED = 'Assigned'
    IN_PROGRESS = 'In Progress'
    PENDING_CLIENT = 'Pending Client'
    RESOLVED = 'Resolved'
    CLOSED = 'Closed'


# Valid state transitions: {current_status: [allowed_next_statuses]}
VALID_TRANSITIONS = {
    TicketStatus.NEW: [TicketStatus.ASSIGNED],
    TicketStatus.ASSIGNED: [TicketStatus.IN_PROGRESS, TicketStatus.NEW],
    TicketStatus.IN_PROGRESS: [
        TicketStatus.PENDING_CLIENT,
        TicketStatus.RESOLVED,
    ],
    TicketStatus.PENDING_CLIENT: [TicketStatus.IN_PROGRESS],
    TicketStatus.RESOLVED: [TicketStatus.CLOSED],
    TicketStatus.CLOSED: [],
}

# Admin-only transitions (superset of standard)
ADMIN_TRANSITIONS = {
    TicketStatus.NEW: [TicketStatus.ASSIGNED],
    TicketStatus.ASSIGNED: [TicketStatus.IN_PROGRESS, TicketStatus.NEW],
    TicketStatus.IN_PROGRESS: [
        TicketStatus.PENDING_CLIENT,
        TicketStatus.RESOLVED,
    ],
    TicketStatus.PENDING_CLIENT: [TicketStatus.IN_PROGRESS],
    TicketStatus.RESOLVED: [TicketStatus.CLOSED, TicketStatus.IN_PROGRESS],
    TicketStatus.CLOSED: [TicketStatus.NEW],  # Admin reopen
}


class SLAState(PyEnum):
    """SLA countdown states."""
    HEALTHY = 'Healthy'
    APPROACHING = 'Approaching Deadline'
    BREACHED = 'Breached'
    COMPLETED = 'Completed'


class Ticket(db.Model):
    """IT support ticket with classification, assignment, SLA, and audit tracking."""

    __tablename__ = 'tickets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_number = db.Column(db.String(20), nullable=False, unique=True, index=True)
    subject = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Submitter
    submitter_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True
    )

    # Effective (possibly overridden) classification
    category = db.Column(
        db.Enum(TicketCategory, values_callable=lambda x: [e.value for e in x]),
        nullable=True, index=True,
    )
    priority = db.Column(
        db.Enum(TicketPriority, values_callable=lambda x: [e.value for e in x]),
        nullable=True, index=True,
    )

    # Status
    status = db.Column(
        db.Enum(TicketStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=TicketStatus.NEW, index=True,
    )

    # Assignment
    assignee_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=True, index=True
    )

    # SLA
    sla_deadline = db.Column(db.DateTime, nullable=True, index=True)
    sla_state = db.Column(
        db.Enum(SLAState, values_callable=lambda x: [e.value for e in x]),
        nullable=True, default=SLAState.HEALTHY,
    )

    # Resolution
    resolution_summary = db.Column(db.Text, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Optimistic locking
    version = db.Column(db.Integer, nullable=False, default=1)

    # Timestamps
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    submitter = db.relationship(
        'User', foreign_keys=[submitter_id], back_populates='submitted_tickets'
    )
    assignee = db.relationship(
        'User', foreign_keys=[assignee_id], back_populates='assigned_tickets'
    )
    prediction = db.relationship(
        'ClassificationPrediction', back_populates='ticket', uselist=False,
        cascade='all, delete-orphan',
    )
    events = db.relationship(
        'TicketEvent', back_populates='ticket', lazy='dynamic',
        order_by='TicketEvent.created_at',
        cascade='all, delete-orphan',
    )
    attachments = db.relationship(
        'TicketAttachment', back_populates='ticket',
        cascade='all, delete-orphan',
        order_by='TicketAttachment.created_at',
    )

    __table_args__ = (
        db.Index('ix_tickets_status_sla', 'status', 'sla_state', 'sla_deadline'),
        db.Index('ix_tickets_assignee_status', 'assignee_id', 'status'),
    )

    def can_transition_to(self, new_status, is_admin=False):
        """Check if a status transition is valid."""
        transitions = ADMIN_TRANSITIONS if is_admin else VALID_TRANSITIONS
        allowed = transitions.get(self.status, [])
        return new_status in allowed

    def __repr__(self):
        return f'<Ticket {self.ticket_number} [{self.status.value}]>'
