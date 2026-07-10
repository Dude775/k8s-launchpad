"""Filesystem-presence and no-CDN-reference tests for offline front-end assets (UI-05).

Phase 6 Plan 01 scope: assert the vendored htmx/Pico files exist on disk.
Phase 6 Plan 02 scope: assert rendered HTML never references a CDN URL, now
that the page templates exist to grep.
"""

from pathlib import Path


def test_vendored_assets_exist_on_disk():
    """htmx.min.js and pico.min.css are vendored under app/static/vendor/."""
    static_dir = Path(__file__).parent.parent / "app" / "static" / "vendor"
    assert (static_dir / "htmx.min.js").is_file()
    assert (static_dir / "pico.min.css").is_file()


def test_no_cdn_references(client):
    """UI-05: rendered HTML must reference only local /static/vendor/ assets,
    never a CDN URL — enforced across the shell + all four page routes."""
    for path in ("/", "/catalog", "/diagnostics", "/feed"):
        body = client.get(path).get_data(as_text=True)
        assert "https://unpkg.com" not in body
        assert "https://cdn." not in body
        assert 'src="http://' not in body
        assert 'href="http://' not in body
