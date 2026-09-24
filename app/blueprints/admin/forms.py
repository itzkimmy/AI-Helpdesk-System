"""Admin forms for user management, overrides, SLA policies, etc."""

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SelectField, TextAreaField,
    BooleanField, FloatField, IntegerField, SubmitField,
)
from wtforms.validators import (
    DataRequired, Email, Length, Optional, NumberRange, Regexp, ValidationError,
)

from app.models.user import User, UserRole
from app.models.ticket import TicketCategory, TicketPriority


class CreateUserForm(FlaskForm):
    """Admin form for creating staff or client accounts with profile details."""

    first_name = StringField('First Name', validators=[
        DataRequired(), Length(min=1, max=100),
    ])
    last_name = StringField('Last Name', validators=[
        DataRequired(), Length(min=1, max=100),
    ])
    username = StringField('Username', validators=[
        DataRequired(), Length(min=3, max=80),
        Regexp(r'^[a-zA-Z0-9_]+$', message='Letters, numbers, and underscores only.'),
    ])
    email = StringField('Email', validators=[
        DataRequired(), Email(), Length(max=255),
    ])
    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=8, max=128),
    ])
    role = SelectField('Role', choices=[
        (UserRole.CLIENT.value, 'Client'),
        (UserRole.TECHNICIAN.value, 'Technician'),
        (UserRole.ADMIN.value, 'Administrator'),
    ], validators=[DataRequired()])

    # Profile & Contact fields
    phone_number = StringField('Phone Number', validators=[Optional(), Length(max=50)])
    job_title = StringField('Job Title / Position', validators=[Optional(), Length(max=100)])
    department = StringField('Department', validators=[Optional(), Length(max=100)])
    company_name = StringField('Company / Branch Name', validators=[Optional(), Length(max=150)])
    address = TextAreaField('Office Address', validators=[Optional(), Length(max=255)])

    submit = SubmitField('Create User')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower().strip()).first():
            raise ValidationError('Email already in use.')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError('Username already taken.')


class EditUserForm(FlaskForm):
    """Admin form for editing user details."""

    first_name = StringField('First Name', validators=[
        DataRequired(), Length(min=1, max=100),
    ])
    last_name = StringField('Last Name', validators=[
        DataRequired(), Length(min=1, max=100),
    ])
    role = SelectField('Role', choices=[
        (UserRole.CLIENT.value, 'Client'),
        (UserRole.TECHNICIAN.value, 'Technician'),
        (UserRole.ADMIN.value, 'Administrator'),
    ], validators=[DataRequired()])

    # Profile & Contact fields
    phone_number = StringField('Phone Number', validators=[Optional(), Length(max=50)])
    job_title = StringField('Job Title / Position', validators=[Optional(), Length(max=100)])
    department = StringField('Department', validators=[Optional(), Length(max=100)])
    company_name = StringField('Company / Branch Name', validators=[Optional(), Length(max=150)])
    address = TextAreaField('Office Address', validators=[Optional(), Length(max=255)])

    is_active = BooleanField('Active')
    is_available = BooleanField('Available for Assignment')
    submit = SubmitField('Save Changes')


class OverrideClassificationForm(FlaskForm):
    """Admin form for overriding ML classification."""

    override_category = SelectField('Category', choices=[
        ('', '-- Keep current --'),
    ] + [(c.value, c.value) for c in TicketCategory], validators=[Optional()])

    override_priority = SelectField('Priority', choices=[
        ('', '-- Keep current --'),
    ] + [(p.value, p.value) for p in TicketPriority], validators=[Optional()])

    override_reason = TextAreaField('Reason for Override', validators=[
        DataRequired(message='A reason is required for overriding AI classification.'),
        Length(min=10, max=1000),
    ], render_kw={'placeholder': 'Explain why this override is necessary...', 'rows': 3})

    submit = SubmitField('Apply Override')


class ReassignTicketForm(FlaskForm):
    """Admin form for reassigning a ticket to a different technician."""

    assignee_id = SelectField('Assign To', coerce=int, validators=[
        DataRequired(message='Please select a technician.'),
    ])
    reason = TextAreaField('Reason', validators=[
        Optional(), Length(max=500),
    ], render_kw={'placeholder': 'Reason for reassignment (optional)', 'rows': 2})
    submit = SubmitField('Reassign')


class SLAPolicyForm(FlaskForm):
    """Admin form for editing SLA policies."""

    resolution_hours = FloatField('Resolution Time (hours)', validators=[
        DataRequired(),
        NumberRange(min=0.25, max=720, message='Must be between 0.25 and 720 hours.'),
    ])
    warning_threshold_pct = IntegerField('Warning Threshold (%)', validators=[
        DataRequired(),
        NumberRange(min=10, max=95, message='Must be between 10% and 95%.'),
    ])
    submit = SubmitField('Save Policy')


class SkillForm(FlaskForm):
    """Admin form for creating/editing skills."""

    name = StringField('Skill Name', validators=[
        DataRequired(), Length(min=2, max=100),
    ])
    category = SelectField('Category', choices=[
        (c.value, c.value) for c in TicketCategory
    ], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[
        Optional(), Length(max=500),
    ], render_kw={'rows': 3})
    submit = SubmitField('Save Skill')


class KnowledgeArticleForm(FlaskForm):
    """Admin form for creating and editing Knowledge Base articles."""

    title = StringField('Article Title', validators=[
        DataRequired(), Length(min=3, max=255),
    ], render_kw={'placeholder': 'e.g. How to Connect to Beyond2U Office Wi-Fi'})

    category = SelectField('Category', choices=[
        (c.value, c.value) for c in TicketCategory
    ], validators=[DataRequired()])

    summary = TextAreaField('Brief Summary', validators=[
        Optional(), Length(max=500),
    ], render_kw={'placeholder': 'A short overview shown in search results and preview cards...', 'rows': 2})

    content = TextAreaField('Article Content / Steps to Resolve', validators=[
        DataRequired(), Length(min=10),
    ], render_kw={'placeholder': 'Detailed instructions, prerequisites, step-by-step resolution...', 'rows': 10})

    tags = StringField('Search Keywords / Tags', validators=[
        Optional(), Length(max=255),
    ], render_kw={'placeholder': 'e.g. wifi, wireless, ssid, password, network (comma-separated)'})

    is_published = BooleanField('Publish Article (Visible to users)', default=True)

    submit = SubmitField('Save Article')
