"""
Extension singletons.

Created unbound here; bound to a concrete Flask app instance inside
create_app() via .init_app(). This pattern supports the application factory
and makes testing with isolated app instances straightforward.
"""

from flask_pymongo import PyMongo
from prometheus_flask_exporter import PrometheusMetrics

# Unbound PyMongo singleton — bound to app in create_app() via mongo.init_app(app).
# Own MongoDB only (launchpad's DB) — never used to reach field-guide-api's DB.
mongo: PyMongo = PyMongo()

# Unbound PrometheusMetrics singleton — bound in create_app() via metrics.init_app(app).
# Using .for_app_factory() defers /metrics route registration to init_app time,
# which is required when using the application factory pattern.
metrics: PrometheusMetrics = PrometheusMetrics.for_app_factory()
