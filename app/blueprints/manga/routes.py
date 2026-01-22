from flask import render_template, abort, session, request
from app.models.manga import Manga

from app.blueprints.manga import manga_bp
from app.services.manga_service import MangaService
from app.services.chapter_service import ChapterService
from app.services.reading_progress_service import ReadingProgressService
from app.models.comment import Comment
from app.models.favorite import Favorite
from app.models.to_read import ToRead
from app.repositories.page_repository import PageRepository


manga_service = MangaService()
chapter_service = ChapterService()
reading_progress_service = ReadingProgressService()
page_repository = PageRepository()


@manga_bp.route("/")
def manga_list():
    query = request.args.get('q', '').strip()
    if query:
        manga_items = Manga.query.filter(Manga.title.ilike(f'%{query}%')).all()
    else:
        manga_items = manga_service.list_manga()
        
    display = []
    for m in manga_items:
        cover = None
        chs = chapter_service.list_chapters_for_manga(m.id)
        if chs:
            # Sort chapters to get the first one for the cover
            chs.sort(key=lambda x: x.number)
            pages = page_repository.get_for_chapter(chs[0].id)
            if pages:
                cover = pages[0].image_path
        display.append({"manga": m, "cover": cover})
    return render_template("manga/list.html", display_manga=display, query=query)


@manga_bp.route("/<string:slug>/")
def manga_detail(slug):
    manga, chapters = manga_service.get_manga_with_chapters_by_slug(slug)
    if not manga:
        abort(404)
    last_read_chapter = None
    user_id = session.get("user_id")
    comments = Comment.query.filter_by(manga_id=manga.id, chapter_id=None).order_by(Comment.created_at.asc()).all()
    is_favorite = False
    is_to_read = False
    if user_id is not None:
        progress = reading_progress_service.get_last_read_chapter(user_id, manga.id)
        if progress:
            last_read_chapter = ChapterService().chapter_repository.get_by_id(progress.chapter_id)
        is_favorite = Favorite.query.filter_by(user_id=user_id, manga_id=manga.id).first() is not None
        is_to_read = ToRead.query.filter_by(user_id=user_id, manga_id=manga.id).first() is not None
    return render_template("manga/detail.html", manga=manga, chapters=chapters, last_read_chapter=last_read_chapter, comments=comments, is_favorite=is_favorite, is_to_read=is_to_read)

# url adlandırma için
@manga_bp.route("/<string:slug>/bolum-<int:chapter_number>/")
def chapter_read(slug, chapter_number):
    manga = manga_service.get_manga_by_slug(slug)
    if not manga:
        abort(404)
    chapter, pages = chapter_service.get_chapter_by_number_with_pages(manga.id, chapter_number)
    if not chapter:
        abort(404)
    
    # Calculate prev/next chapters
    all_chapters = chapter_service.list_chapters_for_manga(manga.id)
    # Chapters are sorted by number ASC in repository
    
    prev_chapter = None
    next_chapter = None
    
    for i, ch in enumerate(all_chapters):
        if ch.number == chapter_number:
            if i > 0:
                prev_chapter = all_chapters[i-1]
            if i < len(all_chapters) - 1:
                next_chapter = all_chapters[i+1]
            break

    user_id = session.get("user_id")
    if user_id is not None:
        reading_progress_service.set_last_read_chapter(user_id, manga.id, chapter.id)
    chapter_comments = Comment.query.filter_by(manga_id=manga.id, chapter_id=chapter.id).order_by(Comment.created_at.asc()).all()
    return render_template("manga/read.html", manga=manga, chapter=chapter, pages=pages, comments=chapter_comments, next_chapter=next_chapter, prev_chapter=prev_chapter)
