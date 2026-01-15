from flask import current_app, send_from_directory, abort
from app.blueprints.storage import storage_bp
import os

@storage_bp.route("/storage/manga/<path:relpath>")
def serve_manga(relpath: str):
    base_path = current_app.config.get("STORAGE_MANGA_PATH")
    if not base_path or not os.path.exists(base_path):
        abort(404)
    return send_from_directory(base_path, relpath)
