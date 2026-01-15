from flask import render_template, abort

from app.blueprints.manga import manga_bp
from app.services.manga_service import MangaService
from app.services.chapter_service import ChapterService
from app.services.reading_progress_service import ReadingProgressService


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
    return render_template(
        "manga/detail.html", manga=manga, chapters=chapters
    )


@manga_bp.route("/manga/<int:manga_id>/chapters/<int:chapter_id>/read/")
def chapter_read(manga_id, chapter_id):
    manga = manga_service.get_manga(manga_id)
    if not manga:
        abort(404)
    chapter, pages = chapter_service.get_chapter_with_pages(chapter_id)
    if not chapter or chapter.manga_id != manga.id:
        abort(404)
    user_id = 1
    progress = reading_progress_service.get_progress(user_id, manga.id, chapter.id)
    last_page_number = progress.last_page_number if progress else None
    return render_template(
        "manga/read.html",
        manga=manga,
        chapter=chapter,
        pages=pages,
        last_page_number=last_page_number,
    )
