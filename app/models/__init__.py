"""
Beyond2U AI-Powered IT Helpdesk - Database Models Package

Imports all models so Alembic and the app factory can discover them.
"""

from app.models.organization import Organization
from app.models.user import User
from app.models.skill import Skill, TechnicianSkill
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.classification import ClassificationPrediction
from app.models.ticket_event import TicketEvent
from app.models.notification import Notification
from app.models.knowledge_base import KnowledgeArticle, DeflectionLog
from app.models.attachment import TicketAttachment

__all__ = [
    'Organization',
    'User',
    'Skill',
    'TechnicianSkill',
    'SLAPolicy',
    'Ticket',
    'ClassificationPrediction',
    'TicketEvent',
    'Notification',
    'KnowledgeArticle',
    'DeflectionLog',
    'TicketAttachment',
]
