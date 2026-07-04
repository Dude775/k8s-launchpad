"""
Application configuration.

Config values are read exclusively from the environment (or .env via python-dotenv).
No real credentials appear in this file.
"""

import os

from dotenv import load_dotenv

# Load .env automatically for local development; no-op in production containers
# where env vars are injected by Docker / Kubernetes Secrets.
load_dotenv()


class Config:
    # MongoDB connection string — must be env-supplied; local default for dev only.
    # Never embed a real URI or password here.
    MONGO_URI: str = os.environ.get(
        "MONGO_URI", "mongodb://localhost:27017/fieldguide"
    )
    MONGO_DBNAME: str = os.environ.get("MONGO_DBNAME", "fieldguide")

    # Debug mode is opt-in via FLASK_DEBUG; default is False (secure in containers).
    DEBUG: bool = bool(os.environ.get("FLASK_DEBUG", ""))

    # Never enable TESTING by default — tests override this via create_app().
    TESTING: bool = False
