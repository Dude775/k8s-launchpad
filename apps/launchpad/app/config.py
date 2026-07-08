"""
Application configuration.

Config values are read exclusively from the environment (or .env via python-dotenv).
No real credentials appear in this file.

Kept minimal in Phase 5 (DEBUG/TESTING only) — MongoDB config keys are deferred
to Phase 7/9 where they are actually used (D-02).
"""

import os

from dotenv import load_dotenv

# Load .env automatically for local development; no-op in production containers
# where env vars are injected by Docker / Kubernetes Secrets.
load_dotenv()


def _env_flag(name: str, default: str = "") -> bool:
    """Parse a boolean env var the way Flask's CLI does.

    Only "1", "true", "yes", "on" (case-insensitive) enable the flag;
    "0", "false", empty, or unset all disable it — so FLASK_DEBUG=0
    never accidentally turns debug mode ON.
    """
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # Debug mode is opt-in via FLASK_DEBUG=1/true/yes/on; default is False.
    # FLASK_DEBUG=0 / FLASK_DEBUG=false explicitly disable it (secure in containers).
    DEBUG: bool = _env_flag("FLASK_DEBUG")

    # Never enable TESTING by default — tests override this via create_app().
    TESTING: bool = False
