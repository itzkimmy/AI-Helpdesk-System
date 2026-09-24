"""Main/landing page blueprint with Admin Calendar and System Health."""

from datetime import datetime, timezone, timedelta
from flask import Blueprint, redirect, url_for, render_template, jsonify
from flask_login import current_user

from app.decorators import admin_required
from app.models.ticket import Ticket

main_bp = Blueprint('main', __name__)

# Standard UTC+8 timezone for display (Asia/Kuala_Lumpur)
_KL_TZ = timezone(timedelta(hours=8))


def _to_local_str(dt):
    """Convert naive UTC or aware datetime to local date & time strings."""
    if not dt:
        return None, None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(_KL_TZ)
    return local_dt.strftime('%Y-%m-%d'), local_dt.strftime('%H:%M')


@main_bp.route('/')
def index():
    """Landing page — redirects authenticated users to their role dashboard."""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        elif current_user.is_technician:
            return redirect(url_for('technician.dashboard'))
        else:
            return redirect(url_for('client.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/calendar')
@admin_required
def calendar_view():
    """Interactive SLA and ticket deadline calendar view (Admin only)."""
    return render_template('calendar.html')


@main_bp.route('/api/calendar-events')
@admin_required
def calendar_events_api():
    """Return JSON events for all tickets and SLA deadlines (Admin only)."""
    tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(200).all()

    events = []
    for t in tickets:
        target_url = url_for('admin.ticket_detail', ticket_number=t.ticket_number)

        # 1. SLA Deadline event (if set)
        if t.sla_deadline:
            d_str, t_str = _to_local_str(t.sla_deadline)
            events.append({
                'id': t.ticket_number,
                'title': t.subject,
                'date': d_str,
                'time': t_str,
                'type': 'deadline',
                'priority': t.priority.value if t.priority else 'Medium',
                'category': t.category.value if t.category else 'General',
                'status': t.status.value,
                'sla_state': t.sla_state.value if t.sla_state else 'Healthy',
                'assignee': t.assignee.full_name if t.assignee else 'Unassigned',
                'submitter': t.submitter.full_name if t.submitter else 'Client',
                'url': target_url,
            })
        elif t.created_at:
            # Fallback to created date if no SLA deadline
            d_str, t_str = _to_local_str(t.created_at)
            events.append({
                'id': t.ticket_number,
                'title': t.subject,
                'date': d_str,
                'time': t_str,
                'type': 'created',
                'priority': t.priority.value if t.priority else 'Medium',
                'category': t.category.value if t.category else 'General',
                'status': t.status.value,
                'sla_state': 'Normal',
                'assignee': t.assignee.full_name if t.assignee else 'Unassigned',
                'submitter': t.submitter.full_name if t.submitter else 'Client',
                'url': target_url,
            })

    return jsonify(events)


@main_bp.route('/health')
def health():
    """Health check endpoint — does not leak secrets."""
    from app.extensions import db
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = 'ok'
    except Exception:
        db_status = 'error'

    return {
        'status': 'ok' if db_status == 'ok' else 'degraded',
        'database': db_status,
    }


@main_bp.route('/ready')
def readiness():
    """Readiness check including ML model availability."""
    from app.extensions import db
    from app.services.classification import ClassificationService

    checks = {}
    try:
        db.session.execute(db.text('SELECT 1'))
        checks['database'] = 'ok'
    except Exception:
        checks['database'] = 'error'

    try:
        svc = ClassificationService()
        checks['ml_models'] = 'ok' if svc.is_ready() else 'unavailable'
    except Exception:
        checks['ml_models'] = 'unavailable'

    all_ok = all(v == 'ok' for v in checks.values())
    return {'status': 'ready' if all_ok else 'not_ready', 'checks': checks}


@main_bp.route('/tickets/attachment/<int:attachment_id>')
def download_attachment(attachment_id):
    """
    Secure attachment download/preview route.
    Enforces object-level authorization (submitter, assigned technician, or admin).
    """
    from flask import send_from_directory, abort, request
    from app.extensions import db
    from app.models.attachment import TicketAttachment
    from app.services.attachment import AttachmentService

    if not current_user.is_authenticated:
        abort(401)

    attachment = db.session.get(TicketAttachment, attachment_id)
    if not attachment:
        abort(404)

    if not AttachmentService.can_access(attachment, current_user):
        abort(403)

    file_path = AttachmentService.get_file_path(attachment)
    if not file_path:
        abort(404)

    upload_dir = AttachmentService.get_upload_dir()
    as_attachment = request.args.get('download', '0') == '1'

    return send_from_directory(
        upload_dir,
        attachment.filename,
        download_name=attachment.original_filename,
        as_attachment=as_attachment,
        mimetype=attachment.mime_type,
    )


@main_bp.route('/favicon.ico')
def favicon():
    """Serve favicon.ico directly from static directory for browsers."""
    import os
    from flask import current_app, send_from_directory
    return send_from_directory(
        os.path.join(current_app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

