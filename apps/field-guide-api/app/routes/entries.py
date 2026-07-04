"""
Entries CRUD blueprint.

Collection: mongo.db.entries
Document shape (stored):
  {
    "_id":        ObjectId,
    "title":      str,       # required on POST
    "category":   str,       # defaults to "general"
    "content":    str,       # required on POST; markdown body
    "tags":       [str],     # defaults to []
    "created_at": str,       # ISO-8601 UTC timestamp, server-generated
  }

Response shape (JSON):
  "id" replaces "_id"; ObjectId serialised to plain string.

Security notes (T-02-03):
  - All queries are passed as Python dicts — no string interpolation into queries.
  - ObjectId() wrapped in try/except: malformed id → 404, never 500.
  - Required-field check returns 400 before touching the DB.
"""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, request

from app.extensions import mongo

entries_bp = Blueprint("entries", __name__)


def _serialize(doc: dict) -> dict:
    """Convert a raw MongoDB document to a JSON-safe response dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


@entries_bp.route("/entries", methods=["GET"])
def list_entries():
    """Return all field-guide entries as a JSON array."""
    docs = list(mongo.db.entries.find())
    return jsonify([_serialize(doc) for doc in docs]), 200


@entries_bp.route("/entries/<entry_id>", methods=["GET"])
def get_entry(entry_id: str):
    """Return a single entry by id, or 404 for unknown / malformed ids."""
    try:
        oid = ObjectId(entry_id)
    except InvalidId:
        # Malformed id string — return 404 so callers never see a 500 (T-02-03)
        return jsonify({"error": "entry not found"}), 404

    doc = mongo.db.entries.find_one({"_id": oid})
    if doc is None:
        return jsonify({"error": "entry not found"}), 404

    return jsonify(_serialize(doc)), 200


@entries_bp.route("/entries", methods=["POST"])
def create_entry():
    """Create a new field-guide entry.

    Required body fields: title, content.
    Returns 201 with the created entry, or 400 if validation fails.
    """
    data = request.get_json(silent=True) or {}

    title = str(data.get("title", "")).strip()
    content = str(data.get("content", "")).strip()

    if not title or not content:
        return jsonify({"error": "title and content are required"}), 400

    doc = {
        "title": title,
        "category": str(data.get("category", "general")),
        "content": content,
        "tags": list(data.get("tags", [])),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Pass dict to PyMongo — no string query construction (T-02-03)
    result = mongo.db.entries.insert_one(doc)
    doc["_id"] = result.inserted_id

    return jsonify(_serialize(doc)), 201
