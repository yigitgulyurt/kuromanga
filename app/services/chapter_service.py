from app.repositories.chapter_repository import ChapterRepository
from app.repositories.page_repository import PageRepository


class ChapterService:
    def __init__(self, chapter_repository=None, page_repository=None):
        self.chapter_repository = chapter_repository or ChapterRepository()
        self.page_repository = page_repository or PageRepository()

    def list_chapters_for_manga(self, manga_id):
        return self.chapter_repository.get_for_manga(manga_id)

    def get_chapter_with_pages(self, chapter_id):
        chapter = self.chapter_repository.get_by_id(chapter_id)
        if not chapter:
            return None, []
        pages = self.page_repository.get_for_chapter(chapter_id)
        return chapter, pages

