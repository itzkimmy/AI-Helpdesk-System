"""
Client routes — dashboard, ticket submission, ticket list, ticket detail.

Object-level authorisation: clients see ONLY their own tickets.
"""

import logging

from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user

from app.blueprints.client import client_bp
from app.blueprints.client.forms import SubmitTicketForm
from app.decorators import client_required
from app.extensions import db
from app.models.ticket import Ticket
from app.services.tickets import TicketService
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


@client_bp.route('/dashboard')
@client_required
def dashboard():
    """Client dashboard — summary and recent tickets."""
    tickets = (
        Ticket.query
        .filter_by(submitter_id=current_user.id)
        .order_by(Ticket.created_at.desc())
        .limit(10)
        .all()
    )

    total = Ticket.query.filter_by(submitter_id=current_user.id).count()
    open_count = (
        Ticket.query
        .filter_by(submitter_id=current_user.id)
        .filter(Ticket.status.notin_(['Resolved', 'Closed']))
        .count()
    )
    resolved_count = (
        Ticket.query
        .filter_by(submitter_id=current_user.id)
        .filter(Ticket.status.in_(['Resolved', 'Closed']))
        .count()
    )

    return render_template(
        'client/dashboard.html',
        tickets=tickets,
        total=total,
        open_count=open_count,
        resolved_count=resolved_count,
    )


@client_bp.route('/tickets')
@client_required
def ticket_list():
    """Paginated list of client's own tickets with filters."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    per_page = 15

    query = Ticket.query.filter_by(submitter_id=current_user.id)

    if status_filter:
        query = query.filter_by(status=status_filter)

    pagination = (
        query
        .order_by(Ticket.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        'client/ticket_list.html',
        tickets=pagination.items,
        pagination=pagination,
        status_filter=status_filter,
    )


@client_bp.route('/tickets/submit', methods=['GET', 'POST'])
@client_required
def submit_ticket():
    """Submit a new IT support ticket."""
    form = SubmitTicketForm()
    if form.validate_on_submit():
        try:
            uploaded_files = request.files.getlist('attachments')
            ticket = TicketService.create_ticket(
                submitter=current_user,
                subject=form.subject.data.strip(),
                description=form.description.data.strip(),
                files=uploaded_files,
            )
            flash(
                f'Ticket {ticket.ticket_number} submitted successfully! '
                'Our team will review it shortly.',
                'success',
            )
            logger.info(
                'Ticket created ticket_number=%s user_id=%d',
                ticket.ticket_number, current_user.id,
            )
            return redirect(url_for('client.ticket_detail', ticket_number=ticket.ticket_number))
        except Exception as e:
            db.session.rollback()
            logger.error('Ticket creation failed: %s', str(e))
            flash('An error occurred while submitting your ticket. Please try again.', 'danger')

    return render_template('client/submit_ticket.html', form=form)


@client_bp.route('/tickets/<ticket_number>')
@client_required
def ticket_detail(ticket_number):
    """View ticket detail and timeline. Object-level auth: own tickets only."""
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()

    # Object-level authorisation
    if ticket.submitter_id != current_user.id:
        abort(403)

    events = (
        ticket.events
        .order_by(db.text('created_at ASC'))
        .all()
    )

    return render_template(
        'client/ticket_detail.html',
        ticket=ticket,
        events=events,
    )


@client_bp.route('/tickets/<ticket_number>/attach', methods=['POST'])
@client_required
def attach_file(ticket_number):
    """Allow client to attach an additional file/screenshot to their ticket."""
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    if ticket.submitter_id != current_user.id:
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

    return redirect(url_for('client.ticket_detail', ticket_number=ticket_number))
