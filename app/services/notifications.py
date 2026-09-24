"""
Notification service — in-app notifications only (no SMTP).

Creates persistent Notification records in the DB.
Admins see these via the bell icon in the navbar.
Idempotency keys prevent duplicate records.
"""

import logging
from datetime import datetime, timezone

from app.extensions import db
from app.models.notification import Notification, NotificationType, NotificationIcon
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


class NotificationService:
    """In-app notification management with idempotency."""

    # ------------------------------------------------------------------
    # Public notify methods
    # ------------------------------------------------------------------

    @staticmethod
    def notify_assignment(ticket, technician):
        """Notify admins that a ticket was auto-assigned to a technician."""
        key = f'assignment:{ticket.id}:{technician.id}:{ticket.version}'
        cat  = ticket.category.value  if ticket.category  else 'Unclassified'
        pri  = ticket.priority.value  if ticket.priority  else 'Unclassified'
        message = (
            f'Ticket {ticket.ticket_number} ({cat} · {pri}) was auto-assigned '
            f'to {technician.full_name}.'
        )
        admins = User.query.filter_by(role=UserRole.ADMIN, is_active=True).all()
        for admin in admins:
            NotificationService._create(
                notification_type=NotificationType.TICKET_ASSIGNED,
                recipient=admin,
                ticket=ticket,
                idempotency_key=f'{key}:{admin.id}',
                message=message,
                icon=NotificationIcon.USER,
            )

    @staticmethod
    def notify_sla_approaching(ticket):
        """Notify admins that a ticket's SLA deadline is approaching."""
        key      = f'sla_approaching:{ticket.id}:{ticket.sla_deadline.isoformat()}'
        pri      = ticket.priority.value if ticket.priority else 'N/A'
        assignee = ticket.assignee.full_name if ticket.assignee else 'Unassigned'
        deadline = (
            ticket.sla_deadline.strftime('%d %b %Y %H:%M UTC')
            if ticket.sla_deadline else 'N/A'
        )
        message = (
            f'⚠ SLA Warning — {ticket.ticket_number} ({pri}) assigned to '
            f'{assignee} is approaching its deadline at {deadline}.'
        )
        admins = User.query.filter_by(role=UserRole.ADMIN, is_active=True).all()
        for admin in admins:
            NotificationService._create(
                notification_type=NotificationType.SLA_APPROACHING,
                recipient=admin,
                ticket=ticket,
                idempotency_key=f'{key}:{admin.id}',
                message=message,
                icon=NotificationIcon.WARNING,
            )

    @staticmethod
    def notify_sla_breached(ticket):
        """Notify admins that a ticket's SLA deadline has been breached."""
        key      = f'sla_breached:{ticket.id}:{ticket.sla_deadline.isoformat()}'
        pri      = ticket.priority.value if ticket.priority else 'N/A'
        assignee = ticket.assignee.full_name if ticket.assignee else 'Unassigned'
        deadline = (
            ticket.sla_deadline.strftime('%d %b %Y %H:%M UTC')
            if ticket.sla_deadline else 'N/A'
        )
        message = (
            f'🔴 SLA Breached — {ticket.ticket_number} ({pri}) assigned to '
            f'{assignee} exceeded its deadline ({deadline}). Immediate action required.'
        )
        admins = User.query.filter_by(role=UserRole.ADMIN, is_active=True).all()
        for admin in admins:
            NotificationService._create(
                notification_type=NotificationType.SLA_BREACHED,
                recipient=admin,
                ticket=ticket,
                idempotency_key=f'{key}:{admin.id}',
                message=message,
                icon=NotificationIcon.DANGER,
            )

    @staticmethod
    def notify_unassigned(ticket):
        """Notify admins that a ticket could not be auto-assigned."""
        key  = f'unassigned:{ticket.id}:{ticket.version}'
        cat  = ticket.category.value if ticket.category else 'Unclassified'
        pri  = ticket.priority.value if ticket.priority else 'Unclassified'
        message = (
            f'Ticket {ticket.ticket_number} ({cat} · {pri}) could not be '
            f'automatically assigned — no available technician with matching skills. '
            f'Please assign manually.'
        )
        admins = User.query.filter_by(role=UserRole.ADMIN, is_active=True).all()
        for admin in admins:
            NotificationService._create(
                notification_type=NotificationType.TICKET_UNASSIGNED_ALERT,
                recipient=admin,
                ticket=ticket,
                idempotency_key=f'{key}:{admin.id}',
                message=message,
                icon=NotificationIcon.WARNING,
            )

    @staticmethod
    def notify_resolved(ticket):
        """Notify admins that a ticket has been resolved."""
        if not ticket.submitter:
            return
        key  = f'resolved:{ticket.id}:{ticket.version}'
        message = (
            f'Ticket {ticket.ticket_number} submitted by '
            f'{ticket.submitter.full_name} has been resolved. '
            f'Resolution: {ticket.resolution_summary or "N/A"}'
        )
        admins = User.query.filter_by(role=UserRole.ADMIN, is_active=True).all()
        for admin in admins:
            NotificationService._create(
                notification_type=NotificationType.TICKET_RESOLVED,
                recipient=admin,
                ticket=ticket,
                idempotency_key=f'{key}:{admin.id}',
                message=message,
                icon=NotificationIcon.CHECK,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create(notification_type, recipient, ticket, idempotency_key, message, icon):
        """
        Create a persistent in-app notification record.

        Skips silently if an identical idempotency_key already exists.
        """
        existing = Notification.query.filter_by(
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            logger.debug('Duplicate notification skipped: %s', idempotency_key)
            return

        notification = Notification(
            notification_type=notification_type,
            recipient_id=recipient.id,
            ticket_id=ticket.id if ticket else None,
            idempotency_key=idempotency_key,
            message=message,
            icon=icon.value if hasattr(icon, 'value') else icon,
        )
        db.session.add(notification)
        db.session.flush()
        logger.info(
            'In-app notification created: %s for user %s',
            idempotency_key, recipient.id,
        )

    @staticmethod
    def unread_count_for(user):
        """Return the unread notification count for a given user."""
        return Notification.query.filter_by(
            recipient_id=user.id,
            is_read=False,
        ).count()
