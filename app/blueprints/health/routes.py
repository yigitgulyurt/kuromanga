from flask import current_app, jsonify

from app.blueprints.health import health_bp
from app.services.storage_health import storage_health


@health_bp.route("/health/storage", methods=["GET"])
def storage_health_route():
    try:
        base_path = current_app.config.get("STORAGE_MANGA_PATH")
        result = storage_health(base_path, force=False)
        return jsonify(result), 200
    except Exception as exc:
        empty = {
            "missing_on_disk": {"manga": [], "chapters": [], "pages": []},
            "missing_in_db": {"chapters": [], "images": []},
            "broken_chapters": [],
        }
        return jsonify(empty), 200

