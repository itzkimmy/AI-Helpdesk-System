"""
Ticket service — creation, classification, status transitions, and overrides.

Owns ticket lifecycle business rules. Routes should delegate here.
"""

import json
import logging
from datetime import datetime, timezone

from app.extensions import db
from app.models.ticket import (
    Ticket, TicketStatus, TicketCategory, TicketPriority, SLAState,
)
from app.models.classification import ClassificationPrediction
from app.models.ticket_event import EventType
from app.services.audit import AuditService
from app.services.sla import SLAService

logger = logging.getLogger(__name__)

# Counter for today's tickets (in-memory; for production use DB sequence)
_ticket_counter = {}


class TicketService:
    """Ticket lifecycle management."""

    @staticmethod
    def generate_ticket_number():
        """Generate a human-readable ticket number: TKT-YYYYMMDD-XXXX."""
        today = datetime.now(timezone.utc).strftime('%Y%m%d')
        # Get current count from DB for today
        count = (
            Ticket.query
            .filter(Ticket.ticket_number.like(f'TKT-{today}-%'))
            .count()
        )
        next_num = count + 1
        return f'TKT-{today}-{next_num:04d}'

    @staticmethod
    def create_ticket(submitter, subject, description, files=None):
        """
        Create a new ticket with classification and SLA.
        
        Transaction boundary: ticket + prediction + SLA + audit event.
        If ML inference fails, the ticket is still persisted with null classification.
        """
        ticket_number = TicketService.generate_ticket_number()

        ticket = Ticket(
            ticket_number=ticket_number,
            subject=subject,
            description=description,
            submitter_id=submitter.id,
            status=TicketStatus.NEW,
        )
        db.session.add(ticket)
        db.session.flush()  # Get ticket.id for relationships

        # Attach any provided files/screenshots
        if files:
            from app.services.attachment import AttachmentService
            file_list = files if isinstance(files, list) else [files]
            for f in file_list:
                if f and getattr(f, 'filename', None):
                    AttachmentService.save_attachment(ticket, submitter, f)

        # Attempt ML classification
        predicted_category = None
        predicted_priority = None
        category_confidence = None
        priority_confidence = None
        category_model_version = None
        priority_model_version = None

        try:
            from app.services.classification import ClassificationService
            cls_service = ClassificationService()
            if cls_service.is_ready():
                result = cls_service.predict(subject, description)
                predicted_category = result.get('category')
                predicted_priority = result.get('priority')
                category_confidence = result.get('category_confidence')
                priority_confidence = result.get('priority_confidence')
                category_model_version = result.get('category_model_version')
                priority_model_version = result.get('priority_model_version')

                # Set effective labels from ML prediction
                try:
                    ticket.category = TicketCategory(predicted_category)
                except (ValueError, KeyError):
                    logger.warning('Invalid predicted category: %s', predicted_category)

                try:
                    ticket.priority = TicketPriority(predicted_priority)
                except (ValueError, KeyError):
                    logger.warning('Invalid predicted priority: %s', predicted_priority)
            else:
                logger.info('ML models not ready — ticket created without classification')
        except Exception as e:
            logger.error('ML classification failed: %s', str(e))
            # Ticket is still created without classification

        # Run AI Sentiment & Urgency analysis
        from app.services.ai_automation import AIAssistantService
        ai_insights = AIAssistantService.analyze_and_record(ticket)

        # Store prediction record
        prediction = ClassificationPrediction(
            ticket_id=ticket.id,
            predicted_category=predicted_category,
            category_confidence=category_confidence,
            category_model_version=category_model_version,
            predicted_priority=predicted_priority,
            priority_confidence=priority_confidence,
            priority_model_version=priority_model_version,
            inference_timestamp=datetime.now(timezone.utc) if predicted_category else None,
            sentiment_label=ai_insights.get('sentiment_label'),
            sentiment_score=ai_insights.get('sentiment_score'),
            urgency_score=ai_insights.get('urgency_score'),
            urgency_triggers=json.dumps(ai_insights.get('triggers', [])),
        )
        db.session.add(prediction)

        # Calculate SLA deadline if priority is set
        if ticket.priority:
            SLAService.set_deadline(ticket)

        # Create audit event
        AuditService.create_event(
            ticket=ticket,
            event_type=EventType.CREATED,
            actor_id=submitter.id,
            data={
                'subject': subject[:100],  # Truncate for audit
                'status': TicketStatus.NEW.value,
            },
        )

        # Create classification event if classified
        if predicted_category or predicted_priority:
            AuditService.create_event(
                ticket=ticket,
                event_type=EventType.CLASSIFIED,
                actor_id=None,  # System action
                data={
                    'predicted_category': predicted_category,
                    'category_confidence': round(category_confidence, 4) if category_confidence else None,
                    'predicted_priority': predicted_priority,
                    'priority_confidence': round(priority_confidence, 4) if priority_confidence else None,
                    'sentiment_tone': ai_insights.get('sentiment_label'),
                    'urgency_score': f"{ai_insights.get('urgency_score')}/100",
                    'category_model_version': category_model_version,
                    'priority_model_version': priority_model_version,
                },
            )

        # Attempt assignment
        try:
            from app.services.assignment import AssignmentService
            AssignmentService.assign_ticket(ticket)
        except Exception as e:
            logger.error('Auto-assignment failed for ticket %s: %s', ticket_number, str(e))
            # Ticket remains unassigned

        db.session.commit()
        return ticket

    @staticmethod
    def update_status(ticket, new_status, actor, resolution_summary=None):
        """
        Transition a ticket to a new status.
        
        Validates the transition, enforces resolution summary requirement,
        and creates an audit event.
        """
        is_admin = actor.is_admin

        if not ticket.can_transition_to(new_status, is_admin=is_admin):
            raise ValueError(
                f'Invalid transition: {ticket.status.value} → {new_status.value}'
            )

        if new_status == TicketStatus.RESOLVED and not resolution_summary:
            raise ValueError('Resolution summary is required when resolving a ticket.')

        old_status = ticket.status
        ticket.status = new_status
        ticket.version += 1

        if new_status == TicketStatus.RESOLVED:
            ticket.resolution_summary = resolution_summary
            ticket.resolved_at = datetime.now(timezone.utc)
            ticket.sla_state = SLAState.COMPLETED
            try:
                from app.services.notifications import NotificationService
                NotificationService.notify_resolved(ticket)
            except Exception as e:
                logger.error('Failed to notify client of resolution for ticket %s: %s', ticket.ticket_number, str(e))

        event_type = EventType.STATUS_CHANGED
        if new_status == TicketStatus.RESOLVED:
            event_type = EventType.RESOLVED
        elif new_status == TicketStatus.NEW and old_status == TicketStatus.CLOSED:
            event_type = EventType.REOPENED

        AuditService.create_event(
            ticket=ticket,
            event_type=event_type,
            actor_id=actor.id,
            data={
                'from_status': old_status.value,
                'to_status': new_status.value,
                'resolution_summary': resolution_summary[:200] if resolution_summary else None,
            },
        )

        db.session.commit()
        return ticket

    @staticmethod
    def override_classification(ticket, admin, new_category=None, new_priority=None, reason=None):
        """
        Admin override of AI classification.
        
        Both original prediction and override are preserved for audit.
        """
        if not reason:
            raise ValueError('A reason is required for overriding classification.')

        if not new_category and not new_priority:
            raise ValueError('Provide at least one of category or priority to override.')

        prediction = ticket.prediction
        if not prediction:
            raise ValueError('No prediction record found for this ticket.')

        data = {'reason': reason}

        if new_category:
            try:
                cat = TicketCategory(new_category)
            except ValueError:
                raise ValueError(f'Invalid category: {new_category}')
            data['old_category'] = ticket.category.value if ticket.category else None
            data['new_category'] = cat.value
            ticket.category = cat
            prediction.is_category_overridden = True

            AuditService.create_event(
                ticket=ticket,
                event_type=EventType.CATEGORY_OVERRIDDEN,
                actor_id=admin.id,
                data=data.copy(),
            )

        if new_priority:
            try:
                pri = TicketPriority(new_priority)
            except ValueError:
                raise ValueError(f'Invalid priority: {new_priority}')
            data['old_priority'] = ticket.priority.value if ticket.priority else None
            data['new_priority'] = pri.value
            ticket.priority = pri
            prediction.is_priority_overridden = True

            # Recalculate SLA with new priority
            SLAService.set_deadline(ticket)

            AuditService.create_event(
                ticket=ticket,
                event_type=EventType.PRIORITY_OVERRIDDEN,
                actor_id=admin.id,
                data=data.copy(),
            )

        prediction.override_reason = reason
        prediction.overridden_by_id = admin.id
        prediction.overridden_at = datetime.now(timezone.utc)
        ticket.version += 1

        db.session.commit()
        return ticket

    @staticmethod
    def reassign_ticket(ticket, new_assignee, admin, reason=None):
        """Admin reassignment of a ticket."""
        old_assignee_id = ticket.assignee_id
        ticket.assignee_id = new_assignee.id
        ticket.version += 1

        if ticket.status == TicketStatus.NEW:
            ticket.status = TicketStatus.ASSIGNED

        AuditService.create_event(
            ticket=ticket,
            event_type=EventType.REASSIGNED,
            actor_id=admin.id,
            data={
                'old_assignee_id': old_assignee_id,
                'new_assignee_id': new_assignee.id,
                'new_assignee_name': new_assignee.full_name,
                'reason': reason,
            },
        )

        db.session.commit()

        # Send notification to new assignee
        try:
            from app.services.notifications import NotificationService
            NotificationService.notify_assignment(ticket, new_assignee)
        except Exception as e:
            logger.error('Assignment notification failed: %s', str(e))

        return ticket

    @staticmethod
    def add_attachment(ticket, uploader, file_storage):
        """Add an attachment to an existing ticket."""
        from app.services.attachment import AttachmentService
        attachment, error = AttachmentService.save_attachment(ticket, uploader, file_storage)
        if error:
            raise ValueError(error)
        ticket.version += 1
        db.session.commit()
        return attachment
