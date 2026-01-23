from flask import render_template, jsonify, current_app, session, redirect, url_for, request, abort
from app.blueprints.status import status_bp
from app.models.manga import Manga
from app.models.chapter import Chapter
from app.models.page import Page
from app.models.user import User
from app.services.storage_health import storage_health
from app.services.run_history import get_runs_status
import shutil
import os
import json

def _require_admin():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = User.query.get(user_id)
    if not user or not user.is_admin:
        return False
    return True

@status_bp.route("/runs")
def runs_status():
    is_admin = _require_admin()
    if is_admin is None:
        return jsonify({"error": "login_required"}), 401
    if is_admin is False:
        return jsonify({"error": "forbidden"}), 403
    data = get_runs_status()
    return jsonify(data), 200

@status_bp.route("/")
def dashboard():
    is_admin = _require_admin()
    if is_admin is None:
        return redirect(url_for("auth.login"))
    if is_admin is False:
        abort(403)
    return render_template("status/dashboard.html")

@status_bp.route("/data")
def status_data():
    is_admin = _require_admin()
    if is_admin is None:
        return jsonify({"error": "login_required"}), 401
    if is_admin is False:
        return jsonify({"error": "forbidden"}), 403
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
            health_data = storage_health(storage_path, force=False)
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

@status_bp.route("/logs")
def get_logs():
    is_admin = _require_admin()
    if is_admin is None:
        return jsonify({"error": "login_required"}), 401
    if is_admin is False:
        return jsonify({"error": "forbidden"}), 403
    
    log_dir = current_app.config.get("ACTIVITY_LOGS_PATH")
    if not log_dir:
        return jsonify({"logs": [], "total": 0})
        
    master_log = os.path.join(log_dir, "activity.log")
    
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    username_filter = request.args.get('username')
    event_filter = request.args.get('event')
    
    logs = []
    total_count = 0
    
    if os.path.exists(master_log):
        try:
            with open(master_log, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
                # Filter logs
                filtered_lines = []
                for line in lines:
                    try:
                        entry = json.loads(line)
                        if username_filter and entry.get('username') != username_filter:
                            continue
                        if event_filter and entry.get('event') != event_filter:
                            continue
                        filtered_lines.append(entry)
                    except:
                        continue
                
                # Sort by timestamp descending
                filtered_lines.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                
                total_count = len(filtered_lines)
                logs = filtered_lines[offset:offset + limit]
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    return jsonify({
        "logs": logs,
        "total": total_count
    })
