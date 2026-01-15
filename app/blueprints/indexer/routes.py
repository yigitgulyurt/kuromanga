from flask import current_app, jsonify

from app.blueprints.indexer import indexer_bp
from app.services.storage_indexer import index_storage


@indexer_bp.route("/index-storage", methods=["POST", "GET"])
def index_storage_route():
    try:
        base_path = current_app.config.get("STORAGE_MANGA_PATH")
        result = index_storage(base_path, force=False)
        return jsonify(result), 200
    except Exception as exc:
        return jsonify({"status": 0, "error": str(exc)}), 200

