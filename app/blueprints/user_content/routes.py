from flask import request, jsonify, redirect, url_for, session, render_template
from app.blueprints.user_content import user_content_bp
from app import db
from app.models.comment import Comment
from app.models.favorite import Favorite
from app.models.to_read import ToRead
from app.models.manga import Manga
from app.models.chapter import Chapter
from app.models.user import User
from app.models.manga import Manga


def _require_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return int(user_id)


@user_content_bp.route("/manga/<int:manga_id>/comment", methods=["POST"])
def add_comment(manga_id):
    user_id = _require_user()
    if not user_id:
        if request.is_json:
            return jsonify({"error": "login_required"}), 401
        return redirect(url_for("auth.login"))
    content = None
    chapter_id = None
    if request.is_json:
        data = request.get_json(silent=True) or {}
        content = (data.get("content") or "").strip()
        chapter_id = data.get("chapter_id")
    else:
        content = (request.form.get("content") or "").strip()
        chapter_id = request.form.get("chapter_id")
    if not content:
        if request.is_json:
            return jsonify({"error": "content_required"}), 400
        return redirect(url_for("manga.manga_detail", manga_id=manga_id))
    manga = Manga.query.get(manga_id)
    if not manga:
        if request.is_json:
            return jsonify({"error": "manga_not_found"}), 404
        return redirect(url_for("manga.manga_list"))
    ch_obj = None
    if chapter_id:
        try:
            ch_obj = Chapter.query.get(int(chapter_id))
        except Exception:
            ch_obj = None
    c = Comment(user_id=user_id, manga_id=manga_id, chapter_id=(ch_obj.id if ch_obj else None), content=content)
    db.session.add(c)
    db.session.commit()
    if request.is_json:
        return jsonify({"status": "ok", "comment_id": c.id}), 201
    target = url_for("manga.manga_detail", manga_id=manga_id)
    if ch_obj:
        target = url_for("manga.chapter_read", manga_id=manga_id, chapter_id=ch_obj.id)
    return redirect(target)


@user_content_bp.route("/comment/<int:comment_id>", methods=["PUT"])
def update_comment(comment_id):
    user_id = _require_user()
    if not user_id:
        return jsonify({"error": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content_required"}), 400
    c = Comment.query.get(comment_id)
    if not c:
        return jsonify({"error": "comment_not_found"}), 404
    if c.user_id != user_id:
        return jsonify({"error": "forbidden"}), 403
    c.content = content
    db.session.commit()
    return jsonify({"status": "ok"}), 200


@user_content_bp.route("/comment/<int:comment_id>", methods=["DELETE"])
def delete_comment(comment_id):
    user_id = _require_user()
    if not user_id:
        return jsonify({"error": "login_required"}), 401
    
    user = User.query.get(user_id)
    c = Comment.query.get(comment_id)
    if not c:
        return jsonify({"error": "comment_not_found"}), 404
        
    # Yorum sahibi veya admin silebilir
    if c.user_id != user_id and not (user and user.is_admin):
        return jsonify({"error": "forbidden"}), 403
        
    db.session.delete(c)
    db.session.commit()
    return jsonify({"status": "ok"}), 200


@user_content_bp.route("/manga/<int:manga_id>/favorite", methods=["POST"])
def toggle_favorite(manga_id):
    user_id = _require_user()
    if not user_id:
        if request.is_json:
            return jsonify({"error": "login_required"}), 401
        return redirect(url_for("auth.login"))
    existing = Favorite.query.filter_by(user_id=user_id, manga_id=manga_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        result = {"status": "removed"}
    else:
        f = Favorite(user_id=user_id, manga_id=manga_id)
        db.session.add(f)
        db.session.commit()
        result = {"status": "added"}
    if request.is_json:
        return jsonify(result), 200
    return redirect(url_for("manga.manga_detail", manga_id=manga_id))


@user_content_bp.route("/manga/<int:manga_id>/to-read", methods=["POST"])
def toggle_to_read(manga_id):
    user_id = _require_user()
    if not user_id:
        if request.is_json:
            return jsonify({"error": "login_required"}), 401
        return redirect(url_for("auth.login"))
    existing = ToRead.query.filter_by(user_id=user_id, manga_id=manga_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        result = {"status": "removed"}
    else:
        t = ToRead(user_id=user_id, manga_id=manga_id)
        db.session.add(t)
        db.session.commit()
        result = {"status": "added"}
    if request.is_json:
        return jsonify(result), 200
    return redirect(url_for("manga.manga_detail", manga_id=manga_id))


@user_content_bp.route("/profile", methods=["GET"])
def profile():
    user_id = _require_user()
    if not user_id:
        return redirect(url_for("auth.login"))
    
    favorites = Favorite.query.filter_by(user_id=user_id).all()
    to_read_items = ToRead.query.filter_by(user_id=user_id).all()
    
    fav_manga = []
    tr_manga = []
    
    for f in favorites:
        m = Manga.query.get(f.manga_id)
        if m:
            cover = None
            chs = Chapter.query.filter_by(manga_id=m.id).order_by(Chapter.number.asc()).all()
            if chs:
                from app.repositories.page_repository import PageRepository
                pages = PageRepository().get_for_chapter(chs[0].id)
                if pages:
                    cover = pages[0].image_path
            fav_manga.append({"manga": m, "cover": cover})
            
    for t in to_read_items:
        m = Manga.query.get(t.manga_id)
        if m:
            cover = None
            chs = Chapter.query.filter_by(manga_id=m.id).order_by(Chapter.number.asc()).all()
            if chs:
                from app.repositories.page_repository import PageRepository
                pages = PageRepository().get_for_chapter(chs[0].id)
                if pages:
                    cover = pages[0].image_path
            tr_manga.append({"manga": m, "cover": cover})
            
    return render_template("user/profile.html", favorites=fav_manga, to_read=tr_manga)
