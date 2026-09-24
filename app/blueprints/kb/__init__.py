"""Knowledge Base blueprint package."""

from flask import Blueprint

kb_bp = Blueprint('kb', __name__)

from app.blueprints.kb import routes  # noqa: E402, F401
