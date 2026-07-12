"""
app.catalog never-raise repo helper tests (CAT-02, CAT-03 data layer).

Mirrors test_status.py's shape: call the helper inside `with
app.app_context():`, assert on the returned tuple/list/dict. Every failure
path must degrade to a safe sentinel — no function in app.catalog may ever
raise past its own boundary.
"""

import pytest

from app import catalog


class _Boom:
    """Any attribute access raises — simulates a dead MongoDB collection."""

    def __getattr__(self, item):
        raise RuntimeError("mongo unavailable")


class _FakeDB:
    services = _Boom()
    events = _Boom()


class _FakeMongo:
    db = _FakeDB()


@pytest.fixture
def broken_mongo(monkeypatch):
    """Replace app.catalog's mongo singleton with one whose collections raise
    on every operation, exercising the never-raise degradation paths."""
    import app.catalog as catalog_module

    monkeypatch.setattr(catalog_module, "mongo", _FakeMongo())


def _service(name="my-service", **overrides):
    doc = {
        "name": name,
        "repo_url": "https://github.com/org/repo",
        "owner": "team-platform",
        "description": "",
        "environment": "dev",
    }
    doc.update(overrides)
    return doc


# --- register_service ------------------------------------------------------


def test_register_service_persists_and_returns_true(app):
    with app.app_context():
        catalog.ensure_indexes()
        ok, error = catalog.register_service(_service())

    assert ok is True
    assert error is None

    from app.extensions import mongo

    stored = mongo.db.services.find_one({"name": "my-service"})
    assert stored is not None
    assert stored["owner"] == "team-platform"
    # register_service stamps registered_at so list_services' sort key
    # always exists.
    assert "registered_at" in stored


def test_register_service_duplicate_name_returns_locked_error(app):
    """Second insert with the same name returns (False, locked copy) and
    writes no second document — DuplicateKeyError never escapes."""
    from app.extensions import mongo

    with app.app_context():
        catalog.ensure_indexes()
        first_ok, _ = catalog.register_service(_service())
        second_ok, error = catalog.register_service(_service())

    assert first_ok is True
    assert second_ok is False
    assert error == "This name is already registered — choose another."
    assert mongo.db.services.count_documents({}) == 1


def test_register_service_generic_failure_returns_false(app, broken_mongo):
    with app.app_context():
        ok, error = catalog.register_service(_service())

    assert ok is False
    assert error == "Could not save this service. Check the fields below and try again."


# --- list_services ----------------------------------------------------------


def test_list_services_sorted_by_registered_at_descending(app):
    with app.app_context():
        catalog.ensure_indexes()
        catalog.register_service(_service("svc-oldest"))
        catalog.register_service(_service("svc-middle"))
        catalog.register_service(_service("svc-newest"))
        # Make the sort deterministic even at equal-clock resolution.
        from datetime import datetime, timedelta, timezone

        from app.extensions import mongo

        base = datetime.now(timezone.utc)
        for offset, name in enumerate(["svc-oldest", "svc-middle", "svc-newest"]):
            mongo.db.services.update_one(
                {"name": name},
                {"$set": {"registered_at": base + timedelta(minutes=offset)}},
            )

        services = catalog.list_services()

    assert [s["name"] for s in services] == ["svc-newest", "svc-middle", "svc-oldest"]


def test_list_services_empty_collection_returns_empty_list(app):
    with app.app_context():
        assert catalog.list_services() == []


def test_list_services_db_error_returns_empty_list(app, broken_mongo):
    with app.app_context():
        assert catalog.list_services() == []


# --- get_service -------------------------------------------------------------


def test_get_service_returns_matching_document(app):
    with app.app_context():
        catalog.ensure_indexes()
        catalog.register_service(_service())
        found = catalog.get_service("my-service")

    assert found is not None
    assert found["name"] == "my-service"


def test_get_service_absent_name_returns_none(app):
    with app.app_context():
        assert catalog.get_service("no-such-service") is None


def test_get_service_db_error_returns_none(app, broken_mongo):
    with app.app_context():
        assert catalog.get_service("my-service") is None


# --- deregister_service -------------------------------------------------------


def test_deregister_service_true_when_document_removed(app):
    from app.extensions import mongo

    with app.app_context():
        catalog.ensure_indexes()
        catalog.register_service(_service())
        removed = catalog.deregister_service("my-service")

    assert removed is True
    assert mongo.db.services.count_documents({}) == 0


def test_deregister_service_false_when_name_absent(app):
    with app.app_context():
        assert catalog.deregister_service("no-such-service") is False


def test_deregister_service_false_on_db_error(app, broken_mongo):
    with app.app_context():
        assert catalog.deregister_service("my-service") is False


# --- ensure_indexes ------------------------------------------------------------


def test_ensure_indexes_creates_unique_name_index_idempotently(app):
    """Calling ensure_indexes twice never raises; the unique index on name
    exists afterwards."""
    from app.extensions import mongo

    with app.app_context():
        catalog.ensure_indexes()
        catalog.ensure_indexes()

    info = mongo.db.services.index_information()
    assert "name_1" in info
    assert info["name_1"].get("unique") is True


def test_ensure_indexes_never_raises_on_db_failure(app, broken_mongo):
    with app.app_context():
        catalog.ensure_indexes()  # must not raise


# --- ServiceForm validation schema (CAT-02, CAT-03, D-01, D-02) ----------------
#
# Error strings asserted below are character-for-character the UI-SPEC
# Copywriting Contract locked copy — they are contracts, not placeholders.

REQUIRED_ERROR = "This field is required."
NAME_FORMAT_ERROR = "Use lowercase letters, numbers, and hyphens only (2–40 characters)."
URL_ERROR = "Enter a valid http:// or https:// URL."
OWNER_ERROR = "Owner is required."

VALID_FORM_DATA = {
    "name": "my-service-1",
    "repo_url": "https://github.com/org/repo",
    "owner": "team-platform",
    "description": "",
    "environment": "dev",
}


def _validate_form(app, data):
    """Build a ServiceForm from raw formdata inside an app context with CSRF
    disabled (the two-tier CSRF posture: field validation is tested here;
    the CSRF-enabled round-trip is a dedicated route test in Plan 09-02)."""
    from werkzeug.datastructures import MultiDict

    from app.forms import ServiceForm

    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        form = ServiceForm(formdata=MultiDict(data))
        valid = form.validate()
    return form, valid


def test_form_valid_submission_passes(app):
    form, valid = _validate_form(app, VALID_FORM_DATA)

    assert valid is True
    assert form.errors == {}


def test_form_description_is_optional(app):
    data = dict(VALID_FORM_DATA)
    del data["description"]
    form, valid = _validate_form(app, data)

    assert valid is True


@pytest.mark.parametrize("bad_name", ["MyService", "a", "x" * 41, "has space"])
def test_form_name_format_rejected_with_locked_copy(app, bad_name):
    form, valid = _validate_form(app, {**VALID_FORM_DATA, "name": bad_name})

    assert valid is False
    assert NAME_FORMAT_ERROR in form.name.errors


def test_form_empty_name_yields_required_error(app):
    form, valid = _validate_form(app, {**VALID_FORM_DATA, "name": ""})

    assert valid is False
    assert REQUIRED_ERROR in form.name.errors


@pytest.mark.parametrize(
    "good_url", ["https://github.com/org/repo", "http://example.com"]
)
def test_form_repo_url_accepts_http_and_https(app, good_url):
    form, valid = _validate_form(app, {**VALID_FORM_DATA, "repo_url": good_url})

    assert valid is True


@pytest.mark.parametrize("bad_url", ["ftp://x", "javascript:alert(1)", "not-a-url"])
def test_form_repo_url_rejects_non_http_schemes_with_locked_copy(app, bad_url):
    form, valid = _validate_form(app, {**VALID_FORM_DATA, "repo_url": bad_url})

    assert valid is False
    assert URL_ERROR in form.repo_url.errors


def test_form_empty_owner_yields_owner_required_error(app):
    form, valid = _validate_form(app, {**VALID_FORM_DATA, "owner": ""})

    assert valid is False
    assert OWNER_ERROR in form.owner.errors


def test_form_owner_over_max_length_fails(app):
    form, valid = _validate_form(app, {**VALID_FORM_DATA, "owner": "x" * 101})

    assert valid is False
    assert form.owner.errors


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_form_environment_accepts_allowed_values(app, env):
    form, valid = _validate_form(app, {**VALID_FORM_DATA, "environment": env})

    assert valid is True


def test_form_environment_rejects_unknown_value(app):
    form, valid = _validate_form(app, {**VALID_FORM_DATA, "environment": "qa"})

    assert valid is False
    assert form.environment.errors


def test_form_environment_defaults_to_dev(app):
    from app.forms import ServiceForm

    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        form = ServiceForm()

    assert form.environment.data == "dev"


def test_form_fully_invalid_submission_surfaces_all_errors_at_once(app):
    """All field errors show simultaneously on re-render (D-06) — not
    one-at-a-time."""
    form, valid = _validate_form(
        app,
        {
            "name": "Bad Name!",
            "repo_url": "ftp://nope",
            "owner": "",
            "description": "",
            "environment": "qa",
        },
    )

    assert valid is False
    assert NAME_FORMAT_ERROR in form.name.errors
    assert URL_ERROR in form.repo_url.errors
    assert OWNER_ERROR in form.owner.errors
    assert form.environment.errors
