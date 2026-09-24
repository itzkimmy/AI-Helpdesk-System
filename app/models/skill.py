"""Skill and TechnicianSkill models for technician capability matching."""

from datetime import datetime, timezone
from app.extensions import db


class Skill(db.Model):
    """An IT support skill category that technicians can possess."""

    __tablename__ = 'skills'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    technician_skills = db.relationship(
        'TechnicianSkill', back_populates='skill',
        cascade='all, delete-orphan',
    )

    @property
    def technicians(self):
        """Return TechnicianSkill rows for this skill (used by templates)."""
        return self.technician_skills

    def __repr__(self):
        return f'<Skill {self.name} [{self.category}]>'


class TechnicianSkill(db.Model):
    """Association between a technician and a skill, with proficiency level."""

    __tablename__ = 'technician_skills'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    technician_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True
    )
    skill_id = db.Column(
        db.Integer, db.ForeignKey('skills.id'), nullable=False, index=True
    )
    proficiency = db.Column(db.Integer, nullable=False, default=3)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    technician = db.relationship('User', back_populates='technician_skills')
    skill = db.relationship('Skill', back_populates='technician_skills')

    __table_args__ = (
        db.UniqueConstraint('technician_id', 'skill_id', name='uq_technician_skill'),
        db.CheckConstraint('proficiency >= 1 AND proficiency <= 5', name='ck_proficiency_range'),
    )

    def __repr__(self):
        return f'<TechnicianSkill tech={self.technician_id} skill={self.skill_id} prof={self.proficiency}>'
