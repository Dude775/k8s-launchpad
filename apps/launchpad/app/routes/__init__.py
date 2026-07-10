# Route blueprint package.
# Re-exports so callers can do: from app.routes import health_bp
from app.routes.health import health_bp
from app.routes.pages import pages_bp
from app.routes.partials import partials_bp
from app.routes.status import status_bp

__all__ = ["health_bp", "pages_bp", "partials_bp", "status_bp"]
