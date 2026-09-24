"""Ticket attachment model for files and screenshots."""

from datetime import datetime, timezone

from app.extensions import db


class TicketAttachment(db.Model):
    """File or screenshot attached to a support ticket."""

    __tablename__ = 'ticket_attachments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(
        db.Integer, db.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, index=True
    )
    uploader_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True
    )
    filename = db.Column(db.String(255), nullable=False)  # Unique stored file name on disk
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # Size in bytes
    mime_type = db.Column(db.String(100), nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    ticket = db.relationship('Ticket', back_populates='attachments')
    uploader = db.relationship('User', foreign_keys=[uploader_id])

    @property
    def is_image(self) -> bool:
        """Check if attachment is an image for rendering inline previews."""
        return self.mime_type.startswith('image/') or any(
            self.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']
        )

    @property
    def formatted_size(self) -> str:
        """Return human readable file size."""
        size = float(self.file_size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}" if unit != 'B' else f"{int(size)} B"
            size /= 1024.0
        return f"{size:.1f} TB"

    def __repr__(self):
        return f'<TicketAttachment {self.id}: {self.original_filename} ({self.formatted_size})>'
