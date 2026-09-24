"""Technician blueprint — assigned queue, ticket actions, workflow."""

from flask import Blueprint

technician_bp = Blueprint('technician', __name__, template_folder='../../templates/technician')

from app.blueprints.technician import routes  # noqa: E402, F401
