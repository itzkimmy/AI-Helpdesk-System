"""Authentication forms with server-side validation."""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length


class LoginForm(FlaskForm):
    """Login form with email/password."""

    email = StringField('Email Address', validators=[
        DataRequired(message='Email is required.'),
        Email(message='Please enter a valid email address.'),
        Length(max=255),
    ], render_kw={'autocomplete': 'email', 'placeholder': 'you@example.com'})

    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required.'),
    ], render_kw={'autocomplete': 'current-password'})

    remember_me = BooleanField('Remember me')
    submit = SubmitField('Sign In')

