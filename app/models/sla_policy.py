"""SLA Policy model — configurable resolution targets by priority."""

from datetime import datetime, timezone
from app.extensions import db


class SLAPolicy(db.Model):
    """
    Configurable SLA resolution targets by ticket priority.
    
    Demo defaults (clearly labelled, NOT Beyond2U production policy):
      Critical: 1 hour
      High: 4 hours
      Medium: 8 hours
      Low: 24 hours
    """

    __tablename__ = 'sla_policies'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    priority = db.Column(db.String(20), nullable=False, unique=True, index=True)
    resolution_hours = db.Column(db.Float, nullable=False)
    warning_threshold_pct = db.Column(
        db.Integer, nullable=False, default=75
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.CheckConstraint(
            'resolution_hours > 0', name='ck_positive_resolution_hours'
        ),
        db.CheckConstraint(
            'warning_threshold_pct >= 0 AND warning_threshold_pct <= 100',
            name='ck_valid_threshold_pct',
        ),
    )

    def __repr__(self):
        return f'<SLAPolicy {self.priority}: {self.resolution_hours}h>'
