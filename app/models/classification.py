"""Classification prediction model — stores ML outputs separate from effective labels."""

from datetime import datetime, timezone
from app.extensions import db


class ClassificationPrediction(db.Model):
    """
    Stores the ML model's predicted category and priority for a ticket,
    along with confidence scores, model versions, and any admin override.
    
    The ticket's effective category/priority fields may differ from these
    predictions if an admin has overridden them.
    """

    __tablename__ = 'classification_predictions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(
        db.Integer, db.ForeignKey('tickets.id'), nullable=False, unique=True, index=True
    )

    # ML predictions
    predicted_category = db.Column(db.String(50), nullable=True)
    category_confidence = db.Column(db.Float, nullable=True)
    category_model_version = db.Column(db.String(50), nullable=True)

    predicted_priority = db.Column(db.String(50), nullable=True)
    priority_confidence = db.Column(db.Float, nullable=True)
    priority_model_version = db.Column(db.String(50), nullable=True)

    inference_timestamp = db.Column(db.DateTime, nullable=True)

    # AI Sentiment & Urgency Analysis
    sentiment_label = db.Column(db.String(50), nullable=True)
    sentiment_score = db.Column(db.Float, nullable=True)
    urgency_score = db.Column(db.Integer, nullable=True)
    urgency_triggers = db.Column(db.Text, nullable=True)

    # Override tracking
    is_category_overridden = db.Column(db.Boolean, nullable=False, default=False)
    is_priority_overridden = db.Column(db.Boolean, nullable=False, default=False)
    override_reason = db.Column(db.Text, nullable=True)
    overridden_by_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=True
    )
    overridden_at = db.Column(db.DateTime, nullable=True)

    # Metadata
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    ticket = db.relationship('Ticket', back_populates='prediction')
    overridden_by = db.relationship('User', foreign_keys=[overridden_by_id])

    def __repr__(self):
        return f'<ClassificationPrediction ticket={self.ticket_id}>'
