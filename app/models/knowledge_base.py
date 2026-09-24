"""Knowledge Base models — articles, categories, helpful feedback, and deflection tracking."""

import re
from datetime import datetime, timezone

from app.extensions import db
from app.models.ticket import TicketCategory


def slugify(text: str) -> str:
    """Generate a clean URL slug from text."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')


class KnowledgeArticle(db.Model):
    """Knowledge base article for user self-service and ticket deflection."""

    __tablename__ = 'knowledge_articles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    slug = db.Column(db.String(255), nullable=False, unique=True, index=True)

    # Category matching TicketCategory
    category = db.Column(
        db.Enum(TicketCategory, values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True,
    )

    summary = db.Column(db.String(500), nullable=True)
    content = db.Column(db.Text, nullable=False)
    tags = db.Column(db.String(255), nullable=True, index=True)  # Comma-separated

    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    view_count = db.Column(db.Integer, nullable=False, default=0)
    helpful_count = db.Column(db.Integer, nullable=False, default=0)
    not_helpful_count = db.Column(db.Integer, nullable=False, default=0)

    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    author = db.relationship('User', foreign_keys=[author_id])
    deflections = db.relationship('DeflectionLog', back_populates='article', cascade='all, delete-orphan')

    @property
    def helpful_ratio(self) -> int:
        total = self.helpful_count + self.not_helpful_count
        if total == 0:
            return 100
        return int((self.helpful_count / total) * 100)

    def __repr__(self):
        return f'<KnowledgeArticle {self.id}: {self.title}>'


class DeflectionLog(db.Model):
    """Tracks when an article prevented a ticket submission (deflection)."""

    __tablename__ = 'deflection_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    article_id = db.Column(db.Integer, db.ForeignKey('knowledge_articles.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    search_query = db.Column(db.String(255), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    article = db.relationship('KnowledgeArticle', back_populates='deflections')
    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<DeflectionLog article_id={self.article_id} user_id={self.user_id}>'
