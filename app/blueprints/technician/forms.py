"""Technician forms for ticket actions."""

from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class UpdateTicketForm(FlaskForm):
    """Form for updating ticket status."""

    new_status = SelectField('New Status', validators=[
        DataRequired(message='Please select a status.'),
    ])

    resolution_summary = TextAreaField('Resolution Summary', validators=[
        Optional(),
        Length(max=5000, message='Resolution summary must be under 5000 characters.'),
    ], render_kw={
        'placeholder': 'Describe how the issue was resolved...',
        'rows': 4,
    })

    submit = SubmitField('Update Ticket')
