# Route blueprint package marker.
#
# Intentionally empty: blueprints are imported per-module and deferred INSIDE
# create_app() (see app/__init__.py) so this package stays importable before
# every route file exists and a single broken/missing route module cannot break
# `import app.routes`. Eagerly re-exporting the blueprints here would defeat
# that guarantee and create a second import surface that can silently drift
# from create_app()'s registration list (WR-04).
