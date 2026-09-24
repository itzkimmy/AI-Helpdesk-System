"""
Audit service — append-only, hash-chained ticket event management.

Creates tamper-evident audit events. Application code must NEVER update or delete events.
"""

import logging
from datetime import datetime, timezone

from app.extensions import db
from app.models.ticket_event import TicketEvent, EventType

logger = logging.getLogger(__name__)

# Genesis hash for the first event in a ticket's chain
GENESIS_HASH = '0' * 64


class AuditService:
    """Append-only audit event creation and chain verification."""

    @staticmethod
    def create_event(ticket, event_type, actor_id=None, data=None):
        """
        Create a new audit event with hash chaining.
        
        The previous_hash is taken from the most recent event for this ticket,
        or GENESIS_HASH if this is the first event.
        """
        # Get the last event's hash for this ticket
        last_event = (
            TicketEvent.query
            .filter_by(ticket_id=ticket.id)
            .order_by(TicketEvent.created_at.desc(), TicketEvent.id.desc())
            .first()
        )
        previous_hash = last_event.current_hash if last_event else GENESIS_HASH

        timestamp = datetime.now(timezone.utc)

        # Compute the hash
        current_hash = TicketEvent.compute_hash(
            previous_hash=previous_hash,
            ticket_id=ticket.id,
            event_type=event_type,
            actor_id=actor_id,
            data=data,
            timestamp=timestamp,
        )

        event = TicketEvent(
            ticket_id=ticket.id,
            event_type=event_type,
            actor_id=actor_id,
            data=data,
            previous_hash=previous_hash,
            current_hash=current_hash,
            created_at=timestamp,
        )
        db.session.add(event)
        # Don't commit — let the caller manage the transaction
        return event

    @staticmethod
    def verify_chain(ticket_id):
        """
        Verify the integrity of the entire audit chain for a ticket.
        
        Returns (is_valid, details) where details contains any errors found.
        """
        events = (
            TicketEvent.query
            .filter_by(ticket_id=ticket_id)
            .order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc())
            .all()
        )

        if not events:
            return True, {'message': 'No events found for this ticket.', 'event_count': 0}

        errors = []
        expected_previous = GENESIS_HASH

        for i, event in enumerate(events):
            # Check chain linkage
            if event.previous_hash != expected_previous:
                errors.append({
                    'event_id': event.id,
                    'event_index': i,
                    'error': 'Chain break: previous_hash mismatch',
                    'expected_previous': expected_previous,
                    'actual_previous': event.previous_hash,
                })

            # Verify self-hash
            if not event.verify_hash():
                expected = TicketEvent.compute_hash(
                    event.previous_hash,
                    event.ticket_id,
                    event.event_type,
                    event.actor_id,
                    event.data,
                    event.created_at,
                )
                errors.append({
                    'event_id': event.id,
                    'event_index': i,
                    'error': 'Hash mismatch: event data may have been tampered with',
                    'expected_hash': expected,
                    'actual_hash': event.current_hash,
                })

            expected_previous = event.current_hash

        return len(errors) == 0, {
            'event_count': len(events),
            'errors': errors,
            'message': 'Chain verified successfully.' if not errors else f'{len(errors)} error(s) found.',
        }

    @staticmethod
    def get_ticket_timeline(ticket_id):
        """Get all audit events for a ticket, ordered chronologically."""
        return (
            TicketEvent.query
            .filter_by(ticket_id=ticket_id)
            .order_by(TicketEvent.created_at.asc())
            .all()
        )
