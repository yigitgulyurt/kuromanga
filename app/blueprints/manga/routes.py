from flask import render_template, abort, session

from app.blueprints.manga import manga_bp
from app.services.manga_service import MangaService
from app.services.chapter_service import ChapterService
from app.services.reading_progress_service import ReadingProgressService
from app.models.comment import Comment
from app.models.favorite import Favorite
from app.models.to_read import ToRead


manga_service = MangaService()
chapter_service = ChapterService()
reading_progress_service = ReadingProgressService()


@manga_bp.route("/")
def manga_list():
    manga_items = manga_service.list_manga()
    return render_template("manga/list.html", manga_items=manga_items)


@manga_bp.route("/manga/<int:manga_id>/")
def manga_detail(manga_id):
    manga, chapters = manga_service.get_manga_with_chapters(manga_id)
    if not manga:
        abort(404)
    last_read_chapter = None
    user_id = session.get("user_id")
    comments = Comment.query.filter_by(manga_id=manga_id, chapter_id=None).order_by(Comment.created_at.asc()).all()
    is_favorite = False
    is_to_read = False
    if user_id is not None:
        progress = reading_progress_service.get_last_read_chapter(user_id, manga.id)
        if progress:
            last_read_chapter = ChapterService().chapter_repository.get_by_id(progress.chapter_id)
        is_favorite = Favorite.query.filter_by(user_id=user_id, manga_id=manga_id).first() is not None
        is_to_read = ToRead.query.filter_by(user_id=user_id, manga_id=manga_id).first() is not None
    return render_template("manga/detail.html", manga=manga, chapters=chapters, last_read_chapter=last_read_chapter, comments=comments, is_favorite=is_favorite, is_to_read=is_to_read)


@manga_bp.route("/manga/<int:manga_id>/chapters/<int:chapter_id>/read/")
def chapter_read(manga_id, chapter_id):
    manga = manga_service.get_manga(manga_id)
    if not manga:
        abort(404)
    chapter, pages = chapter_service.get_chapter_with_pages(chapter_id)
    if not chapter or chapter.manga_id != manga.id:
        abort(404)
    user_id = session.get("user_id")
    if user_id is not None:
        reading_progress_service.set_last_read_chapter(user_id, manga.id, chapter.id)
    chapter_comments = Comment.query.filter_by(manga_id=manga_id, chapter_id=chapter_id).order_by(Comment.created_at.asc()).all()
    return render_template("manga/read.html", manga=manga, chapter=chapter, pages=pages, comments=chapter_comments)
