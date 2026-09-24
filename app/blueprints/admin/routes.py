"""
Admin routes — dashboard, KPI, queue management, user/skill/SLA management,
classification overrides, reassignment, reports, and audit.
"""

import csv
import io
import logging
from datetime import datetime, timezone

from flask import (
    render_template, redirect, url_for, flash, request, abort,
    Response, jsonify,
)
from flask_login import current_user

from app.blueprints.admin import admin_bp
from app.blueprints.admin.forms import (
    CreateUserForm, EditUserForm, OverrideClassificationForm,
    ReassignTicketForm, SLAPolicyForm, SkillForm, KnowledgeArticleForm,
)
from app.decorators import admin_required
from app.extensions import db
from app.models.user import User, UserRole
from app.models.ticket import Ticket, TicketStatus, TicketCategory, TicketPriority, SLAState
from app.models.skill import Skill, TechnicianSkill
from app.models.sla_policy import SLAPolicy
from app.models.classification import ClassificationPrediction
from app.models.ticket_event import TicketEvent, EventType
from app.services.tickets import TicketService
from app.services.assignment import AssignmentService
from app.services.audit import AuditService
from app.models.notification import Notification, NotificationType
from app.models.knowledge_base import KnowledgeArticle, DeflectionLog
from app.services.knowledge_base import KnowledgeBaseService

logger = logging.getLogger(__name__)


# =============================================================================
# Dashboard
# =============================================================================

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard with KPI cards, charts data, and queue overview."""
    # KPI calculations
    open_count = Ticket.query.filter(
        Ticket.status.notin_(['Resolved', 'Closed'])
    ).count()

    unassigned_count = Ticket.query.filter(
        Ticket.assignee_id.is_(None),
        Ticket.status.notin_(['Resolved', 'Closed']),
    ).count()

    approaching_count = Ticket.query.filter(
        Ticket.sla_state == SLAState.APPROACHING.value,
        Ticket.status.notin_(['Resolved', 'Closed']),
    ).count()

    breached_count = Ticket.query.filter(
        Ticket.sla_state == SLAState.BREACHED.value,
        Ticket.status.notin_(['Resolved', 'Closed']),
    ).count()

    total_tickets = Ticket.query.count()
    resolved_count = Ticket.query.filter(
        Ticket.status.in_(['Resolved', 'Closed'])
    ).count()

    # Recent tickets for queue table
    recent_tickets = (
        Ticket.query
        .order_by(Ticket.created_at.desc())
        .limit(20)
        .all()
    )

    # Category distribution for chart
    category_data = [
        (cat.value if cat else 'Unclassified', count)
        for cat, count in (
            db.session.query(Ticket.category, db.func.count(Ticket.id))
            .group_by(Ticket.category)
            .all()
        )
    ]

    # Priority distribution for chart
    priority_data = [
        (pri.value if pri else 'Unclassified', count)
        for pri, count in (
            db.session.query(Ticket.priority, db.func.count(Ticket.id))
            .group_by(Ticket.priority)
            .all()
        )
    ]

    # Workload distribution
    workload_data = (
        db.session.query(
            User.username,
            db.func.count(Ticket.id),
        )
        .join(Ticket, Ticket.assignee_id == User.id)
        .filter(Ticket.status.notin_(['Resolved', 'Closed']))
        .group_by(User.id, User.username)
        .all()
    )

    return render_template(
        'admin/dashboard.html',
        open_count=open_count,
        unassigned_count=unassigned_count,
        approaching_count=approaching_count,
        breached_count=breached_count,
        total_tickets=total_tickets,
        resolved_count=resolved_count,
        recent_tickets=recent_tickets,
        category_data=category_data,
        priority_data=priority_data,
        workload_data=workload_data,
    )


# =============================================================================
# Queue Management
# =============================================================================

@admin_bp.route('/tickets')
@admin_required
def ticket_list():
    """All tickets with filters and pagination."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')
    priority_filter = request.args.get('priority', '')
    per_page = 20

    query = Ticket.query

    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if category_filter:
        query = query.filter(Ticket.category == category_filter)
    if priority_filter:
        query = query.filter(Ticket.priority == priority_filter)

    pagination = (
        query
        .order_by(Ticket.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        'admin/ticket_list.html',
        tickets=pagination.items,
        pagination=pagination,
        status_filter=status_filter,
        category_filter=category_filter,
        priority_filter=priority_filter,
        categories=TicketCategory,
        priorities=TicketPriority,
        statuses=TicketStatus,
    )


@admin_bp.route('/tickets/<ticket_number>')
@admin_required
def ticket_detail(ticket_number):
    """Admin view of any ticket with override/reassign options."""
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()

    override_form = OverrideClassificationForm()
    reassign_form = ReassignTicketForm()

    # Populate technician choices for reassignment
    technicians = (
        User.query
        .filter_by(role=UserRole.TECHNICIAN, is_active=True)
        .order_by(User.username)
        .all()
    )
    reassign_form.assignee_id.choices = [
        (0, '-- Select technician --')
    ] + [(t.id, f'{t.full_name} ({t.username})') for t in technicians]

    events = ticket.events.order_by(db.text('created_at ASC')).all()

    from app.services.ai_automation import AIAssistantService
    ai_insights = AIAssistantService.analyze_ticket(ticket)

    return render_template(
        'admin/ticket_detail.html',
        ticket=ticket,
        override_form=override_form,
        reassign_form=reassign_form,
        events=events,
        ai_insights=ai_insights,
    )


@admin_bp.route('/tickets/<ticket_number>/override', methods=['POST'])
@admin_required
def override_classification(ticket_number):
    """Override AI classification with a reason."""
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    form = OverrideClassificationForm()

    if form.validate_on_submit():
        try:
            TicketService.override_classification(
                ticket=ticket,
                admin=current_user,
                new_category=form.override_category.data or None,
                new_priority=form.override_priority.data or None,
                reason=form.override_reason.data.strip(),
            )
            flash('Classification overridden successfully.', 'success')
            logger.info(
                'Classification overridden ticket=%s by admin=%d',
                ticket.ticket_number, current_user.id,
            )
        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            logger.error('Override failed: %s', str(e))
            flash('Failed to override classification.', 'danger')
    else:
        for errors in form.errors.values():
            for error in errors:
                flash(error, 'danger')

    return redirect(url_for('admin.ticket_detail', ticket_number=ticket_number))


@admin_bp.route('/tickets/<ticket_number>/reassign', methods=['POST'])
@admin_required
def reassign_ticket(ticket_number):
    """Reassign a ticket to a different technician."""
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first_or_404()
    form = ReassignTicketForm()

    # Repopulate choices
    technicians = User.query.filter_by(role=UserRole.TECHNICIAN, is_active=True).all()
    form.assignee_id.choices = [(0, '--')] + [(t.id, t.full_name) for t in technicians]

    if form.validate_on_submit() and form.assignee_id.data > 0:
        try:
            new_assignee = db.session.get(User, form.assignee_id.data)
            if not new_assignee or new_assignee.role != UserRole.TECHNICIAN:
                flash('Invalid technician selected.', 'danger')
            else:
                TicketService.reassign_ticket(
                    ticket=ticket,
                    new_assignee=new_assignee,
                    admin=current_user,
                    reason=form.reason.data,
                )
                flash(f'Ticket reassigned to {new_assignee.full_name}.', 'success')
                logger.info(
                    'Ticket reassigned ticket=%s to=%d by=%d',
                    ticket.ticket_number, new_assignee.id, current_user.id,
                )
        except Exception as e:
            db.session.rollback()
            logger.error('Reassignment failed: %s', str(e))
            flash('Failed to reassign ticket.', 'danger')
    else:
        flash('Please select a technician.', 'danger')

    return redirect(url_for('admin.ticket_detail', ticket_number=ticket_number))


# =============================================================================
# User Management
# =============================================================================

@admin_bp.route('/users')
@admin_required
def user_list():
    """List all users with management options."""
    page = request.args.get('page', 1, type=int)
    role_filter = request.args.get('role', '')

    query = User.query
    if role_filter:
        try:
            role_enum = UserRole(role_filter)
            query = query.filter(User.role == role_enum)
        except ValueError:
            pass  # Invalid role value — show all users

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False,
    )

    return render_template(
        'admin/user_list.html',
        users=pagination.items,
        pagination=pagination,
        role_filter=role_filter,
    )


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    """Create a new user (staff or client) with full profile details."""
    form = CreateUserForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower().strip(),
            username=form.username.data.strip(),
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            role=UserRole(form.role.data),
            phone_number=form.phone_number.data.strip() if form.phone_number.data else None,
            job_title=form.job_title.data.strip() if form.job_title.data else None,
            department=form.department.data.strip() if form.department.data else None,
            company_name=form.company_name.data.strip() if form.company_name.data else None,
            address=form.address.data.strip() if form.address.data else None,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'User {user.username} created as {user.role.value}.', 'success')
        logger.info('User created id=%d role=%s by admin=%d', user.id, user.role.value, current_user.id)
        return redirect(url_for('admin.user_list'))

    return render_template('admin/create_user.html', form=form)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit user details and role."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    form = EditUserForm(obj=user)
    if form.validate_on_submit():
        user.first_name = form.first_name.data.strip()
        user.last_name = form.last_name.data.strip()
        user.role = UserRole(form.role.data)
        user.phone_number = form.phone_number.data.strip() if form.phone_number.data else None
        user.job_title = form.job_title.data.strip() if form.job_title.data else None
        user.department = form.department.data.strip() if form.department.data else None
        user.company_name = form.company_name.data.strip() if form.company_name.data else None
        user.address = form.address.data.strip() if form.address.data else None
        user.is_active = form.is_active.data
        user.is_available = form.is_available.data
        db.session.commit()
        flash(f'User {user.username} updated.', 'success')
        logger.info('User edited id=%d by admin=%d', user.id, current_user.id)
        return redirect(url_for('admin.user_list'))

    # Pre-populate form
    form.role.data = user.role.value
    form.phone_number.data = user.phone_number
    form.job_title.data = user.job_title
    form.department.data = user.department
    form.company_name.data = user.company_name
    form.address.data = user.address
    form.is_active.data = user.is_active
    form.is_available.data = user.is_available

    return render_template('admin/edit_user.html', form=form, user=user)


@admin_bp.route('/users/<int:user_id>/deactivate', methods=['POST'])
@admin_required
def deactivate_user(user_id):
    """Toggle user active status (soft deactivate / activate)."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    if user.id == current_user.id:
        flash('You cannot change the status of your own account.', 'danger')
        return redirect(url_for('admin.user_list'))

    if user.is_active:
        user.is_active = False
        user.is_available = False
        flash(f'User {user.username} deactivated.', 'warning')
        logger.info('User deactivated id=%d by admin=%d', user.id, current_user.id)
    else:
        user.is_active = True
        user.is_available = True
        flash(f'User {user.username} re-activated.', 'success')
        logger.info('User activated id=%d by admin=%d', user.id, current_user.id)

    db.session.commit()
    return redirect(url_for('admin.user_list'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Permanently delete a user account."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    if user.id == current_user.id:
        flash('You cannot delete your own administrator account.', 'danger')
        return redirect(url_for('admin.user_list'))

    # Check for submitted tickets
    submitted_count = user.submitted_tickets.count()
    if submitted_count > 0:
        flash(
            f'Cannot delete user "{user.username}" because they have {submitted_count} submitted ticket(s). '
            'Please deactivate the account instead to maintain ticket audit history.',
            'danger'
        )
        return redirect(url_for('admin.user_list'))

    # Check for assigned tickets
    assigned_count = user.assigned_tickets.count()
    if assigned_count > 0:
        flash(
            f'Cannot delete technician "{user.username}" because they are assigned to {assigned_count} ticket(s). '
            'Please reassign their tickets first or deactivate the account.',
            'danger'
        )
        return redirect(url_for('admin.user_list'))

    username = user.username
    email = user.email

    # Clean up associated notifications
    from app.models.notification import Notification
    Notification.query.filter_by(recipient_id=user.id).delete()

    db.session.delete(user)
    db.session.commit()

    flash(f'Account "{username}" ({email}) has been permanently deleted.', 'success')
    logger.info('User permanently deleted id=%d username=%s by admin=%d', user_id, username, current_user.id)
    return redirect(url_for('admin.user_list'))


# =============================================================================
# Skill Management
# =============================================================================

@admin_bp.route('/skills')
@admin_required
def skill_list():
    """List all skills with assignment panel."""
    skills = Skill.query.order_by(Skill.category, Skill.name).all()
    technicians = (
        User.query
        .filter_by(role=UserRole.TECHNICIAN, is_active=True)
        .order_by(User.first_name)
        .all()
    )
    return render_template('admin/skill_list.html', skills=skills, technicians=technicians)


@admin_bp.route('/skills/create', methods=['GET', 'POST'])
@admin_required
def create_skill():
    """Create a new skill."""
    form = SkillForm()
    if form.validate_on_submit():
        skill = Skill(
            name=form.name.data.strip(),
            category=form.category.data,
            description=form.description.data,
        )
        db.session.add(skill)
        db.session.commit()
        flash(f'Skill "{skill.name}" created.', 'success')
        return redirect(url_for('admin.skill_list'))
    return render_template('admin/create_skill.html', form=form)


@admin_bp.route('/skills/<int:skill_id>/assign', methods=['POST'])
@admin_required
def assign_skill(skill_id):
    """Assign a skill to a technician."""
    skill = db.session.get(Skill, skill_id)
    if not skill:
        abort(404)

    tech_id = request.form.get('technician_id', type=int)
    proficiency = request.form.get('proficiency', 3, type=int)

    if not tech_id:
        flash('Please select a technician.', 'danger')
        return redirect(url_for('admin.skill_list'))

    tech = db.session.get(User, tech_id)
    if not tech or tech.role != UserRole.TECHNICIAN:
        flash('Invalid technician.', 'danger')
        return redirect(url_for('admin.skill_list'))

    existing = TechnicianSkill.query.filter_by(
        technician_id=tech_id, skill_id=skill_id,
    ).first()

    if existing:
        existing.proficiency = max(1, min(5, proficiency))
        flash(f'Proficiency updated for {tech.full_name}.', 'info')
    else:
        ts = TechnicianSkill(
            technician_id=tech_id,
            skill_id=skill_id,
            proficiency=max(1, min(5, proficiency)),
        )
        db.session.add(ts)
        flash(f'Skill assigned to {tech.full_name}.', 'success')

    db.session.commit()
    return redirect(url_for('admin.skill_list'))


@admin_bp.route('/skills/<int:skill_id>/unassign/<int:tech_id>', methods=['POST'])
@admin_required
def remove_skill_assignment(skill_id, tech_id):
    """Remove a skill assignment from a technician."""
    ts = TechnicianSkill.query.filter_by(
        skill_id=skill_id, technician_id=tech_id,
    ).first_or_404()
    tech_name = ts.technician.full_name
    db.session.delete(ts)
    db.session.commit()
    flash(f'Skill removed from {tech_name}.', 'warning')
    logger.info(
        'Skill assignment removed skill=%d tech=%d by admin=%d',
        skill_id, tech_id, current_user.id,
    )
    return redirect(url_for('admin.skill_list'))


# =============================================================================
# SLA Policy Management
# =============================================================================

@admin_bp.route('/sla-policies')
@admin_required
def sla_policy_list():
    """List SLA policies."""
    policies = SLAPolicy.query.order_by(SLAPolicy.resolution_hours).all()
    return render_template('admin/sla_policies.html', policies=policies)


@admin_bp.route('/sla-policies/<int:policy_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_sla_policy(policy_id):
    """Edit an SLA policy."""
    policy = db.session.get(SLAPolicy, policy_id)
    if not policy:
        abort(404)

    form = SLAPolicyForm(obj=policy)
    if form.validate_on_submit():
        policy.resolution_hours = form.resolution_hours.data
        policy.warning_threshold_pct = form.warning_threshold_pct.data
        db.session.commit()
        flash(f'SLA policy for {policy.priority} updated.', 'success')
        logger.info(
            'SLA policy updated priority=%s hours=%s by admin=%d',
            policy.priority, policy.resolution_hours, current_user.id,
        )
        return redirect(url_for('admin.sla_policy_list'))

    return render_template('admin/edit_sla_policy.html', form=form, policy=policy)


# =============================================================================
# Reports
# =============================================================================

@admin_bp.route('/reports/export-csv')
@admin_required
def export_csv():
    """Export tickets as CSV report."""
    tickets = (
        Ticket.query
        .order_by(Ticket.created_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Ticket Number', 'Subject', 'Category', 'Priority', 'Status',
        'SLA State', 'SLA Deadline', 'Submitter', 'Assignee',
        'Created At', 'Updated At', 'Resolved At',
    ])

    def _csv_safe(val):
        s = str(val) if val is not None else ''
        if s.startswith(('=', '+', '-', '@', '\t', '\r')):
            return f"'{s}"
        return s

    for t in tickets:
        writer.writerow([
            _csv_safe(t.ticket_number),
            _csv_safe(t.subject),
            _csv_safe(t.category.value if t.category else ''),
            _csv_safe(t.priority.value if t.priority else ''),
            _csv_safe(t.status.value),
            _csv_safe(t.sla_state.value if t.sla_state else ''),
            _csv_safe(t.sla_deadline.isoformat() if t.sla_deadline else ''),
            _csv_safe(t.submitter.full_name if t.submitter else ''),
            _csv_safe(t.assignee.full_name if t.assignee else 'Unassigned'),
            _csv_safe(t.created_at.isoformat() if t.created_at else ''),
            _csv_safe(t.updated_at.isoformat() if t.updated_at else ''),
            _csv_safe(t.resolved_at.isoformat() if t.resolved_at else ''),
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=helpdesk_report_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.csv'
        },
    )


# =============================================================================
# Chart data API (JSON for Chart.js)
# =============================================================================

@admin_bp.route('/api/chart-data')
@admin_required
def chart_data():
    """JSON endpoint for dashboard charts."""
    category_data = dict(
        db.session.query(Ticket.category, db.func.count(Ticket.id))
        .group_by(Ticket.category)
        .all()
    )
    priority_data = dict(
        db.session.query(Ticket.priority, db.func.count(Ticket.id))
        .group_by(Ticket.priority)
        .all()
    )
    status_data = dict(
        db.session.query(Ticket.status, db.func.count(Ticket.id))
        .group_by(Ticket.status)
        .all()
    )

    return jsonify({
        'categories': {
            (k.value if k else 'Unclassified'): v
            for k, v in category_data.items()
        },
        'priorities': {
            (k.value if k else 'Unclassified'): v
            for k, v in priority_data.items()
        },
        'statuses': {
            (k.value if k else 'Unknown'): v
            for k, v in status_data.items()
        },
    })


# =============================================================================
# Audit Events
# =============================================================================

@admin_bp.route('/audit')
@admin_required
def audit_log():
    """View audit events across all tickets."""
    page = request.args.get('page', 1, type=int)
    ticket_filter = request.args.get('ticket', '')

    query = TicketEvent.query

    if ticket_filter:
        ticket = Ticket.query.filter_by(ticket_number=ticket_filter).first()
        if ticket:
            query = query.filter_by(ticket_id=ticket.id)

    pagination = (
        query
        .order_by(TicketEvent.created_at.desc())
        .paginate(page=page, per_page=30, error_out=False)
    )

    return render_template(
        'admin/audit_log.html',
        events=pagination.items,
        pagination=pagination,
        ticket_filter=ticket_filter,
    )


# =============================================================================
# In-App Notifications (Admin only)
# =============================================================================

@admin_bp.route('/notifications')
@admin_required
def notification_list():
    """Full paginated notification list for admins."""
    page = request.args.get('page', 1, type=int)
    filter_unread = request.args.get('unread', '0') == '1'

    query = Notification.query.filter_by(recipient_id=current_user.id)
    if filter_unread:
        query = query.filter_by(is_read=False)

    pagination = (
        query
        .order_by(Notification.created_at.desc())
        .paginate(page=page, per_page=25, error_out=False)
    )
    unread_total = Notification.query.filter_by(
        recipient_id=current_user.id, is_read=False
    ).count()

    return render_template(
        'admin/notifications.html',
        notifications=pagination.items,
        pagination=pagination,
        filter_unread=filter_unread,
        unread_total=unread_total,
    )


@admin_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@admin_required
def notification_mark_read(notif_id):
    """Mark a single notification as read."""
    notif = Notification.query.filter_by(
        id=notif_id, recipient_id=current_user.id
    ).first_or_404()
    notif.mark_read()
    db.session.commit()
    return jsonify({'status': 'ok', 'id': notif_id})


@admin_bp.route('/notifications/read-all', methods=['POST'])
@admin_required
def notification_mark_all_read():
    """Mark all unread notifications as read for the current admin."""
    from datetime import datetime, timezone
    Notification.query.filter_by(
        recipient_id=current_user.id, is_read=False
    ).update({'is_read': True, 'read_at': datetime.now(timezone.utc)})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('admin.notification_list'))


@admin_bp.route('/notifications/api/recent')
@admin_required
def notifications_api():
    """Return JSON of the 5 most recent notifications for the bell dropdown."""
    from datetime import datetime, timezone, timedelta

    def time_ago(dt):
        if not dt:
            return ''
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt
        s = int(diff.total_seconds())
        if s < 60:
            return 'just now'
        if s < 3600:
            return f'{s // 60}m ago'
        if s < 86400:
            return f'{s // 3600}h ago'
        return f'{s // 86400}d ago'

    notifs = (
        Notification.query
        .filter_by(recipient_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )

    result = []
    for n in notifs:
        ticket_url    = None
        ticket_number = None
        if n.ticket:
            ticket_url    = url_for('admin.ticket_detail', ticket_number=n.ticket.ticket_number)
            ticket_number = n.ticket.ticket_number
        result.append({
            'id':            n.id,
            'icon':          n.icon,
            'message':       n.message,
            'is_read':       n.is_read,
            'time_ago':      time_ago(n.created_at),
            'ticket_url':    ticket_url,
            'ticket_number': ticket_number,
        })

    return jsonify(result)


# =============================================================================
# Knowledge Base Management
# =============================================================================

@admin_bp.route('/kb')
@admin_required
def kb_list():
    """Admin view for managing Knowledge Base articles."""
    articles = (
        KnowledgeArticle.query
        .order_by(KnowledgeArticle.created_at.desc())
        .all()
    )
    stats = KnowledgeBaseService.get_stats()
    return render_template('admin/kb_list.html', articles=articles, stats=stats)


@admin_bp.route('/kb/create', methods=['GET', 'POST'])
@admin_required
def kb_create():
    """Create a new Knowledge Base article."""
    form = KnowledgeArticleForm()
    if form.validate_on_submit():
        try:
            cat_enum = TicketCategory(form.category.data)
            article = KnowledgeBaseService.create_article(
                title=form.title.data,
                category=cat_enum,
                content=form.content.data,
                summary=form.summary.data,
                tags=form.tags.data,
                is_published=form.is_published.data,
                author=current_user,
            )
            flash(f'Knowledge Base article "{article.title}" created successfully!', 'success')
            return redirect(url_for('admin.kb_list'))
        except Exception as e:
            db.session.rollback()
            logger.error('Failed to create KB article: %s', str(e))
            flash('Error creating article. Please try again.', 'danger')

    return render_template('admin/kb_form.html', form=form, title='Create Knowledge Base Article')


@admin_bp.route('/kb/<int:article_id>/edit', methods=['GET', 'POST'])
@admin_required
def kb_edit(article_id):
    """Edit an existing Knowledge Base article."""
    article = KnowledgeBaseService.get_article(article_id)
    if not article:
        abort(404)

    form = KnowledgeArticleForm(obj=article)
    if request.method == 'GET':
        form.category.data = article.category.value

    if form.validate_on_submit():
        try:
            cat_enum = TicketCategory(form.category.data)
            KnowledgeBaseService.update_article(
                article=article,
                title=form.title.data,
                category=cat_enum,
                content=form.content.data,
                summary=form.summary.data,
                tags=form.tags.data,
                is_published=form.is_published.data,
            )
            flash(f'Knowledge Base article "{article.title}" updated successfully!', 'success')
            return redirect(url_for('admin.kb_list'))
        except Exception as e:
            db.session.rollback()
            logger.error('Failed to update KB article %d: %s', article_id, str(e))
            flash('Error updating article. Please try again.', 'danger')

    return render_template('admin/kb_form.html', form=form, article=article, title='Edit Knowledge Base Article')


@admin_bp.route('/kb/<int:article_id>/toggle-publish', methods=['POST'])
@admin_required
def kb_toggle_publish(article_id):
    """Toggle published state of an article."""
    article = KnowledgeBaseService.get_article(article_id)
    if not article:
        abort(404)

    article.is_published = not article.is_published
    db.session.commit()
    state_str = 'published' if article.is_published else 'unpublished'
    flash(f'Article "{article.title}" is now {state_str}.', 'info')
    return redirect(url_for('admin.kb_list'))


@admin_bp.route('/kb/<int:article_id>/delete', methods=['POST'])
@admin_required
def kb_delete(article_id):
    """Delete a Knowledge Base article."""
    article = KnowledgeBaseService.get_article(article_id)
    if not article:
        abort(404)

    title = article.title
    KnowledgeBaseService.delete_article(article)
    flash(f'Knowledge Base article "{title}" was deleted.', 'warning')
    return redirect(url_for('admin.kb_list'))
