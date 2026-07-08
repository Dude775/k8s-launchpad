# Route blueprint package.
# Re-exports so callers can do: from app.routes import health_bp
from app.routes.health import health_bp

__all__ = ["health_bp"]
