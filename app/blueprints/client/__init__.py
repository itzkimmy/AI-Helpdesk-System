"""Client blueprint — ticket submission, tracking, and dashboard."""

from flask import Blueprint

client_bp = Blueprint('client', __name__, template_folder='../../templates/client')

from app.blueprints.client import routes  # noqa: E402, F401
