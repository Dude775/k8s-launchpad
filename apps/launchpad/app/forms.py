"""
ServiceForm — WTForms validation schema for the onboard form (CAT-02, CAT-03).

Field set and rules are locked by D-01/D-02; every error message is
character-for-character the UI-SPEC Copywriting Contract copy — locked
strings, not placeholders. Uniqueness of `name` is deliberately NOT a form
validator: the MongoDB unique index is the enforcement boundary and
catalog.register_service() translates the race-safe DuplicateKeyError into
its own locked copy (RESEARCH Pattern 4).

repo_url is scheme-restricted to http(s) explicitly (RESEARCH Pitfall 5,
T-09-01): URL(require_tld=True) alone validates shape, not scheme, so a
javascript:/ftp: URI must additionally fail the ^https?:// Regexp below.
"""

import re

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, TextAreaField, URLField
from wtforms.validators import URL, DataRequired, Length, Regexp

NAME_PATTERN = re.compile(r"^[a-z0-9-]{2,40}$")
HTTP_SCHEME_PATTERN = re.compile(r"^https?://")

# Locked UI-SPEC Copywriting Contract strings.
REQUIRED_MESSAGE = "This field is required."
NAME_FORMAT_MESSAGE = "Use lowercase letters, numbers, and hyphens only (2–40 characters)."
URL_MESSAGE = "Enter a valid http:// or https:// URL."
OWNER_REQUIRED_MESSAGE = "Owner is required."


class ServiceForm(FlaskForm):
    """Onboard-form schema; fields in D-01 display order."""

    name = StringField(
        "Service Name",
        validators=[
            DataRequired(message=REQUIRED_MESSAGE),
            Regexp(NAME_PATTERN, message=NAME_FORMAT_MESSAGE),
        ],
    )
    repo_url = URLField(
        "Repository URL",
        validators=[
            DataRequired(message=REQUIRED_MESSAGE),
            Regexp(HTTP_SCHEME_PATTERN, message=URL_MESSAGE),
            URL(require_tld=True, message=URL_MESSAGE),
        ],
    )
    owner = StringField(
        "Owner",
        validators=[
            DataRequired(message=OWNER_REQUIRED_MESSAGE),
            Length(max=100),
        ],
    )
    description = TextAreaField("Description")  # optional — no validators
    environment = SelectField(
        "Environment",
        choices=[("dev", "dev"), ("staging", "staging"), ("prod", "prod")],
        default="dev",
        validators=[DataRequired(message=REQUIRED_MESSAGE)],
    )
