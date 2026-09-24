"""
Reset script for Beyond2U IT Helpdesk.

Wipes all tickets, events, predictions, notifications, technician skills,
and users EXCEPT for the primary system administrator account.
Reference data (organization, skills, SLA policies) is preserved.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models.user import User, UserRole
from app.models.ticket import Ticket
from app.models.notification import Notification
from app.models.ticket_event import TicketEvent
from app.models.classification import ClassificationPrediction
from app.models.skill import TechnicianSkill, Skill
from app.models.sla_policy import SLAPolicy
from app.models.organization import Organization


def reset_database(app=None):
    """Reset database to keep only the master admin account and clean slate data."""
    print("Starting database reset...")

    # 1. Identify or recreate Admin account
    admin_email = "admin@dummy.com"
    admin = User.query.filter((User.email == admin_email) | (User.username == "admin")).first()

    org = Organization.query.first()
    if not org:
        org = Organization(name="Beyond2U Sdn Bhd", description="Beyond2U Headquarters")
        db.session.add(org)
        db.session.flush()

    if not admin:
        print(f"  - Admin account not found; creating master admin ({admin_email})...")
        admin = User(
            organization_id=org.id,
            username="admin",
            email=admin_email,
            first_name="System",
            last_name="Admin",
            role=UserRole.ADMIN,
            is_active=True,
            is_available=True,
        )
        admin.set_password("AdminPassword123!")
        db.session.add(admin)
        db.session.flush()
    else:
        print(f"  - Preserving master admin: {admin.email} (ID: {admin.id}, Username: {admin.username})")
        admin.email = admin_email
        admin.failed_login_attempts = 0
        admin.locked_until = None
        admin.is_active = True
        admin.is_available = True
        # Ensure password is set to default if needed
        if not admin.check_password("AdminPassword123!"):
            admin.set_password("AdminPassword123!")

    # 2. Delete child records / user-generated data in dependency order
    from app.models.knowledge_base import KnowledgeArticle, DeflectionLog
    deleted_deflections = DeflectionLog.query.delete()
    print(f"  - Deleted {deleted_deflections} deflection log(s)")

    deleted_articles = KnowledgeArticle.query.delete()
    print(f"  - Deleted {deleted_articles} knowledge base article(s)")

    deleted_notifications = Notification.query.delete()
    print(f"  - Deleted {deleted_notifications} notification(s)")

    deleted_predictions = ClassificationPrediction.query.delete()
    print(f"  - Deleted {deleted_predictions} classification prediction(s)")

    deleted_events = TicketEvent.query.delete()
    print(f"  - Deleted {deleted_events} ticket event(s)")

    deleted_skills = TechnicianSkill.query.delete()
    print(f"  - Deleted {deleted_skills} technician skill assignment(s)")

    from app.models.attachment import TicketAttachment
    deleted_attachments = TicketAttachment.query.delete()
    print(f"  - Deleted {deleted_attachments} ticket attachment(s)")

    deleted_tickets = Ticket.query.delete()
    print(f"  - Deleted {deleted_tickets} ticket(s)")

    # 3. Delete all users except the master admin
    deleted_users = User.query.filter(User.id != admin.id).delete()
    print(f"  - Deleted {deleted_users} other user(s)")

    db.session.commit()
    print("\nDatabase reset successfully committed!")

    # 4. Summary verification
    print("\nCurrent Database Counts:")
    print(f"  - Users remaining: {User.query.count()} (Admin: {admin.email})")
    print(f"  - Tickets remaining: {Ticket.query.count()}")
    print(f"  - Notifications remaining: {Notification.query.count()}")
    print(f"  - Ticket Events remaining: {TicketEvent.query.count()}")
    print(f"  - Classification Predictions: {ClassificationPrediction.query.count()}")
    print(f"  - Technician Skills: {TechnicianSkill.query.count()}")
    print(f"  - Reference Skills: {Skill.query.count()}")
    print(f"  - SLA Policies: {SLAPolicy.query.count()}")
    print(f"  - Organizations: {Organization.query.count()}")


if __name__ == "__main__":
    app = create_app("development")
    with app.app_context():
        reset_database(app)
