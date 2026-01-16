from flask import current_app, jsonify, session
from app.blueprints.indexer import indexer_bp
from app.services.storage_indexer import index_storage
from app.models.user import User

@indexer_bp.route("/index-storage", methods=["POST", "GET"])
def index_storage_route():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "login_required"}), 401
    user = User.query.get(user_id)
    if not user or not user.is_admin:
        return jsonify({"error": "forbidden"}), 403
    try:
        base_path = current_app.config.get("STORAGE_MANGA_PATH")
        run_logs_path = current_app.config.get("STORAGE_RUN_LOGS_PATH")
        result = index_storage(base_path, run_logs_path=run_logs_path, force=False)
        return jsonify(result), 200
    except Exception as exc:
        return jsonify({"status": 0, "error": str(exc)}), 200

