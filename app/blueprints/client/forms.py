"""Client ticket forms."""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length


class SubmitTicketForm(FlaskForm):
    """Form for submitting a new IT support ticket."""

    subject = StringField('Subject', validators=[
        DataRequired(message='Subject is required.'),
        Length(min=5, max=255, message='Subject must be 5-255 characters.'),
    ], render_kw={'placeholder': 'Brief description of your issue'})

    description = TextAreaField('Description', validators=[
        DataRequired(message='Description is required.'),
        Length(min=20, max=5000, message='Description must be 20-5000 characters.'),
    ], render_kw={
        'placeholder': 'Please describe your issue in detail...',
        'rows': 6,
    })

    submit = SubmitField('Submit Ticket')
