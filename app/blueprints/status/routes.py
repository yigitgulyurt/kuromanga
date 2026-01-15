from flask import render_template, jsonify, current_app
from app.blueprints.status import status_bp
from app.models.manga import Manga
from app.models.chapter import Chapter
from app.models.page import Page
from app.services.storage_health import check_storage_health
import shutil
import os

@status_bp.route("/")
def dashboard():
    return render_template("status/dashboard.html")

@status_bp.route("/data")
def status_data():
    # DB Stats
    try:
        manga_count = Manga.query.count()
        chapter_count = Chapter.query.count()
        page_count = Page.query.count()
    except Exception as e:
        return jsonify({"error": f"DB Error: {str(e)}"}), 500

    # Storage Health
    storage_path = current_app.config.get("STORAGE_MANGA_PATH")
    health_data = {}
    
    # Disk Usage
    disk_usage = {}
    
    if storage_path:
        # Health Check
        try:
            # check_storage_health handles its own caching
            health_data = check_storage_health(storage_path)
        except Exception as e:
            health_data = {"error": str(e)}

        # Disk Usage
        try:
            if os.path.exists(storage_path):
                total, used, free = shutil.disk_usage(storage_path)
                disk_usage = {
                    "total_gb": round(total / (1024**3), 2),
                    "used_gb": round(used / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2),
                    "percent_free": round((free / total) * 100, 1)
                }
        except Exception:
            disk_usage = {"error": "Could not determine disk usage"}

    return jsonify({
        "db_stats": {
            "mangas": manga_count,
            "chapters": chapter_count,
            "pages": page_count
        },
        "storage_health": health_data,
        "disk_usage": disk_usage
    })
