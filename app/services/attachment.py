"""Ticket attachment service — file & screenshot upload validation, storage, and access control."""

import os
import uuid
import logging
from typing import Optional, List, Tuple
from flask import current_app
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models.attachment import TicketAttachment
from app.models.ticket import Ticket
from app.models.ticket_event import EventType
from app.services.audit import AuditService

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    # Images (including screenshots pasted via clipboard)
    'png', 'jpg', 'jpeg', 'gif', 'webp',
    # Documents and text logs
    'pdf', 'txt', 'log', 'docx', 'xlsx', 'csv'
}

MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB per file


class AttachmentService:
    """Handles secure file uploads, validation, and authorization for ticket attachments."""

    @staticmethod
    def get_upload_dir() -> str:
        """Get or create the storage directory for ticket attachments."""
        upload_dir = current_app.config.get(
            'UPLOAD_FOLDER',
            os.path.join(current_app.instance_path, 'uploads', 'attachments')
        )
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir

    @staticmethod
    def is_allowed_file(filename: str) -> bool:
        """Check if filename has a permitted extension."""
        if not filename or '.' not in filename:
            return False
        ext = filename.rsplit('.', 1)[1].lower()
        return ext in ALLOWED_EXTENSIONS

    @staticmethod
    def can_access(attachment: TicketAttachment, user) -> bool:
        """
        Object-level authorization check for downloading/viewing an attachment.
        Only admin, the ticket submitter, or the assigned technician may access.
        """
        if not user or not user.is_authenticated:
            return False
        if user.is_admin:
            return True
        if attachment.ticket.submitter_id == user.id:
            return True
        if attachment.ticket.assignee_id == user.id:
            return True
        return False

    @classmethod
    def save_attachment(
        cls,
        ticket: Ticket,
        uploader,
        file_storage: FileStorage,
    ) -> Tuple[Optional[TicketAttachment], Optional[str]]:
        """
        Validate, store to disk, create database record, and audit log an attachment.
        Returns (attachment_object, error_message).
        """
        if not file_storage or not file_storage.filename:
            return None, "No file provided"

        raw_name = file_storage.filename
        if not cls.is_allowed_file(raw_name):
            allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
            return None, f"File type not permitted. Allowed types: {allowed_list}"

        # Check file size
        file_storage.seek(0, os.SEEK_END)
        file_size = file_storage.tell()
        file_storage.seek(0)  # Reset pointer

        if file_size <= 0:
            return None, "Uploaded file is empty"
        if file_size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
            return None, f"File exceeds maximum allowed size of {max_mb} MB"

        # Sanitize filename & generate unique stored filename
        clean_name = secure_filename(raw_name)
        if not clean_name:
            clean_name = f"attachment_{int(uuid.uuid4().hex[:8], 16)}"
        
        stored_filename = f"{uuid.uuid4().hex}_{clean_name}"
        upload_dir = cls.get_upload_dir()
        dest_path = os.path.join(upload_dir, stored_filename)

        # Save to disk
        file_storage.save(dest_path)

        # Infer MIME type or fallback
        mime_type = file_storage.mimetype or 'application/octet-stream'

        attachment = TicketAttachment(
            ticket_id=ticket.id,
            uploader_id=uploader.id,
            filename=stored_filename,
            original_filename=raw_name[:250],
            file_size=file_size,
            mime_type=mime_type,
        )
        db.session.add(attachment)
        db.session.flush()

        # Audit event in the hash-chained ledger
        AuditService.create_event(
            ticket=ticket,
            event_type=EventType.ATTACHMENT_ADDED,
            actor_id=uploader.id,
            data={
                'attachment_id': attachment.id,
                'filename': attachment.original_filename,
                'size': attachment.formatted_size,
                'mime_type': mime_type,
            }
        )

        logger.info(
            "Attachment saved for ticket %s: file=%s size=%d",
            ticket.ticket_number, attachment.original_filename, file_size
        )
        return attachment, None

    @classmethod
    def get_file_path(cls, attachment: TicketAttachment) -> Optional[str]:
        """Return absolute path to stored file if it exists."""
        upload_dir = cls.get_upload_dir()
        file_path = os.path.join(upload_dir, attachment.filename)
        if os.path.isfile(file_path):
            return file_path
        return None
