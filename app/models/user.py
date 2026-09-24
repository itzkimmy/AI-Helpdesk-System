"""User model with role-based access, Argon2id hashing, and availability tracking."""

from datetime import datetime, timezone
from enum import Enum as PyEnum

from flask_login import UserMixin
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from app.extensions import db

_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


class UserRole(PyEnum):
    """User roles. Staff accounts (technician, admin) must be created/promoted by admin."""
    CLIENT = 'client'
    TECHNICIAN = 'technician'
    ADMIN = 'admin'


class User(UserMixin, db.Model):
    """Application user with authentication and role information."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.CLIENT,
        index=True,
    )
    organization_id = db.Column(
        db.Integer, db.ForeignKey('organizations.id'), nullable=True, index=True
    )
    # Profile & Contact details
    phone_number = db.Column(db.String(50), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    company_name = db.Column(db.String(150), nullable=True)
    job_title = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(255), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_available = db.Column(db.Boolean, nullable=False, default=True, index=True)
    last_assigned_at = db.Column(db.DateTime, nullable=True)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    organization = db.relationship('Organization', back_populates='users')
    technician_skills = db.relationship(
        'TechnicianSkill', back_populates='technician', lazy='dynamic',
        cascade='all, delete-orphan',
    )
    submitted_tickets = db.relationship(
        'Ticket', foreign_keys='Ticket.submitter_id',
        back_populates='submitter', lazy='dynamic',
    )
    assigned_tickets = db.relationship(
        'Ticket', foreign_keys='Ticket.assignee_id',
        back_populates='assignee', lazy='dynamic',
    )

    def set_password(self, password):
        """Hash password using Argon2id."""
        self.password_hash = _ph.hash(password)

    def check_password(self, password):
        """Verify password against stored Argon2id hash. Returns False on mismatch."""
        try:
            return _ph.verify(self.password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False

    def needs_rehash(self):
        """Check if the stored hash needs to be re-hashed with updated parameters."""
        try:
            return _ph.check_needs_rehash(self.password_hash)
        except InvalidHashError:
            return True

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN

    @property
    def is_technician(self):
        return self.role == UserRole.TECHNICIAN

    @property
    def is_client(self):
        return self.role == UserRole.CLIENT

    def is_account_locked(self):
        """Check if the account is currently locked due to failed login attempts."""
        if self.locked_until is None:
            return False
        now = datetime.now(timezone.utc)
        if now >= self.locked_until:
            # Lock expired — reset
            self.failed_login_attempts = 0
            self.locked_until = None
            return False
        return True

    def __repr__(self):
        return f'<User {self.username} ({self.role.value})>'
