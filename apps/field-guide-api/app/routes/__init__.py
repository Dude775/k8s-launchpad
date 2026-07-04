# Route blueprint package.
# Re-exports so callers can do: from app.routes import entries_bp, health_bp
from app.routes.entries import entries_bp
from app.routes.health import health_bp

__all__ = ["entries_bp", "health_bp"]
