"""
gunicorn WSGI entrypoint.

Target: gunicorn wsgi:app
This is the only runnable production entrypoint — the Flask dev server is never
used in a container or Kubernetes deployment path.
"""

from app import create_app

app = create_app()
