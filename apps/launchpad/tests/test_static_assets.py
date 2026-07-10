"""Filesystem-presence tests for vendored offline front-end assets (UI-05).

Phase 6 Plan 01 scope: assert the vendored htmx/Pico files exist on disk.
The no-CDN-reference test is added in Plan 02, once rendered templates exist
to grep for CDN URLs.
"""

from pathlib import Path


def test_vendored_assets_exist_on_disk():
    """htmx.min.js and pico.min.css are vendored under app/static/vendor/."""
    static_dir = Path(__file__).parent.parent / "app" / "static" / "vendor"
    assert (static_dir / "htmx.min.js").is_file()
    assert (static_dir / "pico.min.css").is_file()
