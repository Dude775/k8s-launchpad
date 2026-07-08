"""
Extension singletons.

Created unbound here; bound to a concrete Flask app instance inside
create_app() via .init_app(). This pattern supports the application factory
and makes testing with isolated app instances straightforward.

No PyMongo singleton in Phase 5 — MongoDB wiring is deferred to Phase 7/9 (D-02).
"""

from prometheus_flask_exporter import PrometheusMetrics

# Unbound PrometheusMetrics singleton — bound in create_app() via metrics.init_app(app).
# Using .for_app_factory() defers /metrics route registration to init_app time,
# which is required when using the application factory pattern.
metrics: PrometheusMetrics = PrometheusMetrics.for_app_factory()
