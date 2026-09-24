"""
SLA service — deadline calculation, state management, and scheduled scanning.

Stores all timestamps in UTC. Display conversion happens at the template level.
"""

import logging
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.ticket import Ticket, TicketStatus, SLAState
from app.models.sla_policy import SLAPolicy
from app.models.ticket_event import EventType
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


class SLAService:
    """SLA deadline calculation and state management."""

    @staticmethod
    def set_deadline(ticket):
        """Calculate and set SLA deadline based on ticket priority."""
        if not ticket.priority:
            return

        policy = SLAPolicy.query.filter_by(
            priority=ticket.priority.value, is_active=True,
        ).first()

        if not policy:
            logger.warning(
                'No SLA policy found for priority %s', ticket.priority.value,
            )
            return

        now = datetime.now(timezone.utc)
        ticket.sla_deadline = now + timedelta(hours=policy.resolution_hours)
        ticket.sla_state = SLAState.HEALTHY

    @staticmethod
    def _make_aware(dt):
        """Return dt with UTC tzinfo, whether it was naive or already aware."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def scan_and_update():
        """
        Scan all open tickets and update SLA states.

        Safe to call on every web request (guarded by a 60-second cooldown
        stored in the app's g object) as well as from the dedicated scheduler
        process.  Must be idempotent.
        States: HEALTHY -> APPROACHING -> BREACHED (COMPLETED when resolved).
        """
        now = datetime.now(timezone.utc)

        open_tickets = (
            Ticket.query
            .filter(
                Ticket.status.notin_(['Resolved', 'Closed']),
                Ticket.sla_deadline.isnot(None),
                Ticket.sla_state != SLAState.COMPLETED.value,
            )
            .all()
        )

        updates = 0
        for ticket in open_tickets:
            old_state = ticket.sla_state
            new_state = SLAService._compute_state(ticket, now)

            if new_state != old_state:
                ticket.sla_state = new_state
                updates += 1

                # Create audit events for state changes
                if new_state == SLAState.APPROACHING:
                    AuditService.create_event(
                        ticket=ticket,
                        event_type=EventType.SLA_APPROACHING,
                        data={
                            'deadline': ticket.sla_deadline.isoformat(),
                            'previous_state': old_state.value if old_state else None,
                        },
                    )
                    # Notify admins
                    try:
                        from app.services.notifications import NotificationService
                        NotificationService.notify_sla_approaching(ticket)
                    except Exception as e:
                        logger.error('SLA approaching notification failed: %s', str(e))

                elif new_state == SLAState.BREACHED:
                    AuditService.create_event(
                        ticket=ticket,
                        event_type=EventType.SLA_BREACHED,
                        data={
                            'deadline': ticket.sla_deadline.isoformat(),
                            'breached_at': now.isoformat(),
                        },
                    )
                    # Notify admins
                    try:
                        from app.services.notifications import NotificationService
                        NotificationService.notify_sla_breached(ticket)
                    except Exception as e:
                        logger.error('SLA breach notification failed: %s', str(e))

        if updates > 0:
            db.session.commit()
            logger.info('SLA scan completed: %d ticket(s) updated', updates)

    @staticmethod
    def _compute_state(ticket, now):
        """Compute the SLA state based on elapsed time vs deadline.

        ``now`` is always timezone-aware (UTC).  ``sla_deadline`` and
        ``created_at`` may be naive (stored without tzinfo by SQLite); we
        normalise them to UTC before every comparison so that Python never
        raises a TypeError from mixing aware and naive datetimes.
        """
        if not ticket.sla_deadline:
            return ticket.sla_state

        deadline = SLAService._make_aware(ticket.sla_deadline)

        if now >= deadline:
            return SLAState.BREACHED

        # Get warning threshold
        policy = SLAPolicy.query.filter_by(
            priority=ticket.priority.value if ticket.priority else 'Low',
            is_active=True,
        ).first()

        threshold_pct = policy.warning_threshold_pct if policy else 75

        # Calculate elapsed percentage
        created = SLAService._make_aware(ticket.created_at)

        if created:
            total_seconds = (deadline - created).total_seconds()
            elapsed_seconds = (now - created).total_seconds()

            if total_seconds > 0:
                elapsed_pct = (elapsed_seconds / total_seconds) * 100
                if elapsed_pct >= threshold_pct:
                    return SLAState.APPROACHING

        return SLAState.HEALTHY

    @staticmethod
    def get_remaining_time(ticket):
        """Get remaining time until SLA deadline as a timedelta, or None."""
        if not ticket.sla_deadline:
            return None
        now = datetime.now(timezone.utc)
        remaining = ticket.sla_deadline - now
        return remaining if remaining.total_seconds() > 0 else timedelta(0)
