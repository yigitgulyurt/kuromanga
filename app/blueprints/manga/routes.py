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
    
    # Calculate prev/next chapters
    all_chapters = chapter_service.list_chapters_for_manga(manga_id)
    # Chapters are usually sorted by number desc or asc. Assuming default sort (number asc hopefully)
    # If list_chapters_for_manga returns sorted, we can find index.
    # Note: If service returns DESC, then next in list is previous chapter.
    # Let's check service or assume and fix. Usually chapters are listed 1..N.
    # Actually, often they are listed newest first (DESC).
    # Let's check logic: if I am at ch 1, next is 2.
    
    prev_chapter = None
    next_chapter = None
    
    for i, ch in enumerate(all_chapters):
        if ch.id == chapter_id:
            # If sorted 1, 2, 3...
            # Prev is i-1, Next is i+1
            # But if sorted 3, 2, 1... (Newest first)
            # Prev (older) is i+1, Next (newer) is i-1
            # Let's assume list_chapters_for_manga returns by number ASC for now, or check service.
            # Standard for reading lists is usually ASC so you read in order.
            # But often blogs list DESC.
            # Let's safely check numbers.
            pass
            
    # Better approach: Sort by number
    all_chapters.sort(key=lambda x: x.number)
    
    for i, ch in enumerate(all_chapters):
        if ch.id == chapter_id:
            if i > 0:
                prev_chapter = all_chapters[i-1]
            if i < len(all_chapters) - 1:
                next_chapter = all_chapters[i+1]
            break

    user_id = session.get("user_id")
    if user_id is not None:
        reading_progress_service.set_last_read_chapter(user_id, manga.id, chapter.id)
    chapter_comments = Comment.query.filter_by(manga_id=manga_id, chapter_id=chapter_id).order_by(Comment.created_at.asc()).all()
    return render_template("manga/read.html", manga=manga, chapter=chapter, pages=pages, comments=chapter_comments, next_chapter=next_chapter, prev_chapter=prev_chapter)
