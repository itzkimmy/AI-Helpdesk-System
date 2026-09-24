"""
Ticket event model — append-only, hash-chained audit trail.

Events are immutable once created. Application code must never UPDATE or DELETE events.
Each event stores a SHA-256 hash of its canonical payload plus the previous event's hash,
forming a tamper-evident chain.
"""

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum as PyEnum

from app.extensions import db


class EventType(PyEnum):
    """All auditable ticket lifecycle events."""
    CREATED = 'created'
    CLASSIFIED = 'classified'
    ASSIGNED = 'assigned'
    REASSIGNED = 'reassigned'
    CATEGORY_OVERRIDDEN = 'category_overridden'
    PRIORITY_OVERRIDDEN = 'priority_overridden'
    STATUS_CHANGED = 'status_changed'
    SLA_APPROACHING = 'sla_approaching'
    SLA_BREACHED = 'sla_breached'
    SLA_COMPLETED = 'sla_completed'
    RESOLVED = 'resolved'
    REOPENED = 'reopened'
    COMMENT = 'comment'
    ATTACHMENT_ADDED = 'attachment_added'


class TicketEvent(db.Model):
    """
    Append-only audit event with hash chaining for tamper evidence.
    
    Hash chain: each event's current_hash = SHA-256(previous_hash + canonical_payload).
    The genesis event uses previous_hash = '0' * 64.
    """

    __tablename__ = 'ticket_events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(
        db.Integer, db.ForeignKey('tickets.id'), nullable=False, index=True
    )
    event_type = db.Column(
        db.Enum(EventType, values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True,
    )
    actor_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=True, index=True
    )
    data = db.Column(db.JSON, nullable=True)
    previous_hash = db.Column(db.String(64), nullable=False)
    current_hash = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    ticket = db.relationship('Ticket', back_populates='events')
    actor = db.relationship('User', foreign_keys=[actor_id])

    __table_args__ = (
        db.Index('ix_ticket_events_ticket_created', 'ticket_id', 'created_at'),
    )

    @staticmethod
    def compute_hash(previous_hash, ticket_id, event_type, actor_id, data, timestamp):
        """
        Compute the SHA-256 hash from the canonical event payload.
        
        The canonical form is a JSON string with sorted keys, ensuring
        deterministic hash computation regardless of dict ordering.
        """
        if timestamp:
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            ts_str = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')
        else:
            ts_str = None

        canonical = json.dumps({
            'previous_hash': previous_hash,
            'ticket_id': ticket_id,
            'event_type': event_type if isinstance(event_type, str) else event_type.value,
            'actor_id': actor_id,
            'data': data,
            'timestamp': ts_str,
        }, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def verify_hash(self):
        """Verify that this event's current_hash matches the computed hash."""
        expected = self.compute_hash(
            self.previous_hash,
            self.ticket_id,
            self.event_type,
            self.actor_id,
            self.data,
            self.created_at,
        )
        return self.current_hash == expected

    def __repr__(self):
        return f'<TicketEvent {self.event_type.value} ticket={self.ticket_id}>'
