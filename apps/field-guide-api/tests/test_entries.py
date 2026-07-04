"""
Entries CRUD endpoint tests.

Covers all response paths for:
    GET  /entries              200 list
    GET  /entries/<id>         200 found | 404 missing | 404 malformed id
    POST /entries              201 created | 400 missing title | 400 missing content

All tests use the mocked-MongoDB fixtures from conftest.py; no real database
or network is required.
"""

import pytest


# ───────────────────────────── GET /entries ──────────────────────────────────


def test_list_empty(client):
    """GET /entries returns 200 and an empty JSON list on a fresh collection."""
    resp = client.get("/entries")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data == []


# ──────────────────────────── POST /entries ───────────────────────────────────


def test_post_creates_entry(client):
    """POST /entries with valid payload returns 201 with correct fields."""
    payload = {"title": "Kubernetes Basics", "content": "# k8s\nPods and nodes."}
    resp = client.post("/entries", json=payload)
    assert resp.status_code == 201

    data = resp.get_json()
    assert isinstance(data.get("id"), str) and len(data["id"]) == 24
    assert data["title"] == "Kubernetes Basics"
    assert data["category"] == "general"
    assert data["tags"] == []
    assert data["created_at"]


def test_list_after_post(client):
    """GET /entries returns one item after a successful POST."""
    client.post("/entries", json={"title": "Docker Basics", "content": "Images and containers."})
    resp = client.get("/entries")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["title"] == "Docker Basics"


def test_post_missing_title_returns_400(client):
    """POST /entries without 'title' returns 400 with an error key."""
    resp = client.post("/entries", json={"content": "some content"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_post_missing_content_returns_400(client):
    """POST /entries without 'content' returns 400 with an error key."""
    resp = client.post("/entries", json={"title": "x"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_post_empty_body_returns_400(client):
    """POST /entries with empty JSON body returns 400 with an error key."""
    resp = client.post("/entries", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_post_array_body_returns_400(client):
    """POST /entries with a JSON array body returns 400 — never 500 (CR-01)."""
    resp = client.post("/entries", json=[1, 2])
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_post_string_body_returns_400(client):
    """POST /entries with a JSON string body returns 400 — never 500 (CR-01)."""
    resp = client.post("/entries", json="just a string")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_post_null_body_returns_400(client):
    """POST /entries with no JSON body at all returns 400 — never 500 (CR-01)."""
    resp = client.post("/entries", data="not json", content_type="text/plain")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_post_non_iterable_tags_returns_400(client):
    """POST /entries with tags=5 returns 400 — never 500 (CR-02)."""
    resp = client.post("/entries", json={"title": "t", "content": "c", "tags": 5})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_post_string_tags_returns_400(client):
    """POST /entries with tags="abc" returns 400 — no char-splitting (CR-02)."""
    resp = client.post("/entries", json={"title": "t", "content": "c", "tags": "abc"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_post_non_string_tag_items_returns_400(client):
    """POST /entries with a non-string element inside tags returns 400 (CR-02)."""
    resp = client.post("/entries", json={"title": "t", "content": "c", "tags": ["ok", 1]})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_post_valid_tags_stored_verbatim(client):
    """POST /entries with a valid list of string tags stores it unchanged."""
    resp = client.post(
        "/entries", json={"title": "t", "content": "c", "tags": ["k8s", "helm"]}
    )
    assert resp.status_code == 201
    assert resp.get_json()["tags"] == ["k8s", "helm"]


def test_post_missing_fields_does_not_persist(client):
    """Failed POST (400) must not insert any document into the collection."""
    client.post("/entries", json={})
    client.post("/entries", json={"title": "only title"})
    resp = client.get("/entries")
    assert resp.get_json() == []


# ─────────────────────────── GET /entries/<id> ───────────────────────────────


def test_get_by_id_found(client):
    """GET /entries/<id> returns 200 with the matching entry after a POST."""
    create_resp = client.post(
        "/entries",
        json={"title": "Helm Charts", "content": "Template everything."},
    )
    entry_id = create_resp.get_json()["id"]

    resp = client.get(f"/entries/{entry_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Helm Charts"
    assert data["id"] == entry_id


def test_get_by_id_missing(client):
    """GET /entries/<valid 24-hex ObjectId> that does not exist returns 404."""
    valid_but_absent_id = "aabbccddeeff001122334455"
    resp = client.get(f"/entries/{valid_but_absent_id}")
    assert resp.status_code == 404


def test_get_by_id_malformed(client):
    """GET /entries/<malformed id> returns 404 — never 500."""
    resp = client.get("/entries/not-an-objectid")
    assert resp.status_code == 404
