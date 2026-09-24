"""
Technician routes — queue dashboard, ticket actions, status updates.

Technicians can only view and act on tickets assigned to them.
"""

import logging

from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user

from app.blueprints.technician import technician_bp
from app.blueprints.technician.forms import UpdateTicketForm
from app.decorators import technician_required
from app.extensions import db
from app.models.ticket import Ticket, TicketStatus, VALID_TRANSITIONS
from app.services.tickets import TicketService
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


@technician_bp.route('/dashboard')
@technician_required
def dashboard():
    """Technician dashboard — assigned queue ordered by urgency."""
    tickets = (
        Ticket.query
        .filter_by(assignee_id=current_user.id)
        .filter(Ticket.status.notin_(['Resolved', 'Closed']))
        .order_by(
            # Breached first, then approaching, then by deadline
            db.case(
                (Ticket.sla_state == 'Breached', 0),
                (Ticket.sla_state == 'Approaching Deadline', 1),
                else_=2,
            ),
            db.case(
                (Ticket.priority == 'Critical', 0),
                (Ticket.priority == 'High', 1),
                (Ticket.priority == 'Medium', 2),
                else_=3,
            ),
            Ticket.sla_deadline.asc().nullslast(),
        )
        .all()
    )

    total_assigned = Ticket.query.filter_by(assignee_id=current_user.id).count()
    active_count = (
        Ticket.query
        .filter_by(assignee_id=current_user.id)
        .filter(Ticket.status.notin_(['Resolved', 'Closed']))
        .count()
    )
    resolved_count = (
        Ticket.query
        .filter_by(assignee_id=current_user.id)
        .filter(Ticket.status.in_(['Resolved', 'Closed']))
        .count()
    )
    breached_count = (
        Ticket.query
        .filter_by(assignee_id=current_user.id)
        .filter(Ticket.sla_state == 'Breached')
        .filter(Ticket.status.notin_(['Resolved', 'Closed']))
        .count()
    )

    return render_template(
        'technician/dashboard.html',
        tickets=tickets,
        total_assigned=total_assigned,
        active_count=active_count,
        resolved_count=resolved_count,
        breached_count=breached_count,
    )


@technician_bp.route('/tickets/<ticket_number>', methods=['GET', 'POST'])
@technician_required
def ticket_action(ticket_number):
    """View and update an assigned ticket."""
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()

    # Object-level authorisation: technician can only act on their assigned tickets
    if ticket.assignee_id != current_user.id:
        abort(403)

    form = UpdateTicketForm()

    # Populate valid transitions
    allowed = VALID_TRANSITIONS.get(ticket.status, [])
    form.new_status.choices = [('', '-- Select status --')] + [
        (s.value, s.value) for s in allowed
    ]

    if form.validate_on_submit():
        new_status_value = form.new_status.data
        try:
            new_status = TicketStatus(new_status_value)
        except ValueError:
            flash('Invalid status selected.', 'danger')
            return redirect(url_for('technician.ticket_action', ticket_number=ticket_number))

        # Validate transition
        if not ticket.can_transition_to(new_status):
            flash(f'Cannot transition from {ticket.status.value} to {new_status.value}.', 'danger')
            return redirect(url_for('technician.ticket_action', ticket_number=ticket_number))

        # Resolution requires a summary
        if new_status == TicketStatus.RESOLVED and not form.resolution_summary.data:
            flash('Resolution summary is required when resolving a ticket.', 'danger')
            return redirect(url_for('technician.ticket_action', ticket_number=ticket_number))

        try:
            TicketService.update_status(
                ticket=ticket,
                new_status=new_status,
                actor=current_user,
                resolution_summary=form.resolution_summary.data,
            )

            # Handle optional attachments
            files = request.files.getlist('attachments')
            for f in files:
                if f and f.filename:
                    from app.services.attachment import AttachmentService
                    AttachmentService.save_attachment(ticket, current_user, f)
            db.session.commit()

            flash(f'Ticket updated to {new_status.value}.', 'success')
            logger.info(
                'Ticket status updated ticket=%s new_status=%s actor=%d',
                ticket.ticket_number, new_status.value, current_user.id,
            )
        except Exception as e:
            db.session.rollback()
            logger.error('Ticket update failed: %s', str(e))
            flash('Failed to update ticket. Please try again.', 'danger')

        return redirect(url_for('technician.ticket_action', ticket_number=ticket_number))

    events = ticket.events.order_by(db.text('created_at ASC')).all()

    from app.services.ai_automation import AIAssistantService
    ai_insights = AIAssistantService.analyze_ticket(ticket)

    return render_template(
        'technician/ticket_action.html',
        ticket=ticket,
        form=form,
        events=events,
        ai_insights=ai_insights,
    )


@technician_bp.route('/tickets/<ticket_number>/attach', methods=['POST'])
@technician_required
def attach_file(ticket_number):
    """Allow technician to attach files/screenshots to an assigned ticket."""
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    if ticket.assignee_id != current_user.id:
        abort(403)

    files = request.files.getlist('attachments')
    attached_count = 0
    errors = []

    for f in files:
        if f and f.filename:
            try:
                TicketService.add_attachment(ticket, current_user, f)
                attached_count += 1
            except Exception as e:
                errors.append(f"{f.filename}: {str(e)}")

    if attached_count > 0:
        flash(f'Successfully added {attached_count} attachment(s).', 'success')
    if errors:
        flash(f'Upload errors: {"; ".join(errors)}', 'danger')

    return redirect(url_for('technician.ticket_action', ticket_number=ticket_number))
