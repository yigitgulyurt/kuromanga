from flask import request, jsonify, abort

from app.blueprints.user_content import user_content_bp
from app.services.reading_progress_service import ReadingProgressService


reading_progress_service = ReadingProgressService()


@user_content_bp.route("/progress", methods=["POST"])
def save_progress():
    data = request.get_json(silent=True) or request.form

    manga_id = data.get("manga_id")
    chapter_id = data.get("chapter_id")
    page_number = data.get("page_number")

    if not manga_id or not chapter_id or not page_number:
        abort(400)

    try:
        manga_id = int(manga_id)
        chapter_id = int(chapter_id)
        page_number = int(page_number)
    except (TypeError, ValueError):
        abort(400)

    user_id = 1

    reading_progress_service.save_progress(
        user_id=user_id,
        manga_id=manga_id,
        chapter_id=chapter_id,
        page_number=page_number,
    )

    return jsonify({"status": "ok"})

