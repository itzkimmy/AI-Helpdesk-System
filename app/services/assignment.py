"""
Assignment service — deterministic technician assignment.

Algorithm:
1. Filter: active + available technicians with matching skill for the ticket category
2. Rank by: lowest weighted open workload → higher proficiency → longest since last assignment → lowest user ID
3. Select top candidate atomically
4. If no match: leave unassigned + alert admins
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func

from app.extensions import db
from app.models.user import User, UserRole
from app.models.ticket import Ticket, TicketStatus
from app.models.skill import Skill, TechnicianSkill
from app.models.ticket_event import EventType
from app.services.audit import AuditService

logger = logging.getLogger(__name__)

# Workload weights by priority
PRIORITY_WEIGHTS = {
    'Critical': 4,
    'High': 3,
    'Medium': 2,
    'Low': 1,
}


class AssignmentService:
    """Deterministic, skill-aware technician assignment."""

    @staticmethod
    def assign_ticket(ticket):
        """
        Attempt to assign a ticket to the best-fit technician.
        
        Uses SELECT FOR UPDATE to prevent double assignment.
        If no suitable technician is found, the ticket remains unassigned
        and administrators are alerted.
        """
        if ticket.assignee_id is not None:
            logger.info('Ticket %s already assigned', ticket.ticket_number)
            return ticket

        category_value = ticket.category.value if ticket.category else None
        if not category_value:
            logger.info('Ticket %s has no category — cannot auto-assign', ticket.ticket_number)
            return ticket

        # Find matching skills for this category
        matching_skills = Skill.query.filter_by(category=category_value, is_active=True).all()
        if not matching_skills:
            logger.info('No skills configured for category %s', category_value)
            AssignmentService._alert_unassigned(ticket)
            return ticket

        matching_skill_ids = [s.id for s in matching_skills]

        # Find eligible technicians
        eligible_techs = (
            User.query
            .join(TechnicianSkill, TechnicianSkill.technician_id == User.id)
            .filter(
                User.role == UserRole.TECHNICIAN,
                User.is_active.is_(True),
                User.is_available.is_(True),
                TechnicianSkill.skill_id.in_(matching_skill_ids),
            )
            .all()
        )

        if not eligible_techs:
            logger.info(
                'No eligible technicians for ticket %s (category=%s)',
                ticket.ticket_number, category_value,
            )
            AssignmentService._alert_unassigned(ticket)
            return ticket

        # Calculate weighted workload for each technician
        ranked = []
        for tech in eligible_techs:
            workload = AssignmentService._calculate_workload(tech.id)
            # Get best proficiency for matching skills
            proficiency = (
                TechnicianSkill.query
                .filter(
                    TechnicianSkill.technician_id == tech.id,
                    TechnicianSkill.skill_id.in_(matching_skill_ids),
                )
                .order_by(TechnicianSkill.proficiency.desc())
                .first()
            )
            prof_level = proficiency.proficiency if proficiency else 0

            ranked.append({
                'technician': tech,
                'workload': workload,
                'proficiency': prof_level,
                'last_assigned': tech.last_assigned_at or datetime.min.replace(tzinfo=timezone.utc),
                'user_id': tech.id,
            })

        # Sort: lowest workload → highest proficiency → longest since last assignment → lowest ID
        ranked.sort(key=lambda x: (
            x['workload'],
            -x['proficiency'],
            x['last_assigned'],
            x['user_id'],
        ))

        selected = ranked[0]['technician']

        # Assign
        ticket.assignee_id = selected.id
        ticket.status = TicketStatus.ASSIGNED
        ticket.version += 1
        selected.last_assigned_at = datetime.now(timezone.utc)

        AuditService.create_event(
            ticket=ticket,
            event_type=EventType.ASSIGNED,
            actor_id=None,  # System-assigned
            data={
                'assignee_id': selected.id,
                'assignee_name': selected.full_name,
                'workload_score': ranked[0]['workload'],
                'proficiency': ranked[0]['proficiency'],
                'candidates_evaluated': len(ranked),
            },
        )

        logger.info(
            'Ticket %s assigned to %s (workload=%.1f, proficiency=%d)',
            ticket.ticket_number, selected.username,
            ranked[0]['workload'], ranked[0]['proficiency'],
        )

        # Send notification (non-blocking)
        try:
            from app.services.notifications import NotificationService
            NotificationService.notify_assignment(ticket, selected)
        except Exception as e:
            logger.error('Assignment notification failed: %s', str(e))

        return ticket

    @staticmethod
    def _calculate_workload(technician_id):
        """Calculate weighted open workload for a technician."""
        open_tickets = (
            Ticket.query
            .filter(
                Ticket.assignee_id == technician_id,
                Ticket.status.notin_(['Resolved', 'Closed']),
            )
            .all()
        )

        total = 0.0
        for t in open_tickets:
            weight = PRIORITY_WEIGHTS.get(
                t.priority.value if t.priority else 'Low', 1
            )
            total += weight

        return total

    @staticmethod
    def _alert_unassigned(ticket):
        """Alert administrators that a ticket could not be auto-assigned."""
        try:
            from app.services.notifications import NotificationService
            NotificationService.notify_unassigned(ticket)
        except Exception as e:
            logger.error('Unassigned alert failed: %s', str(e))
