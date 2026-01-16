from app.repositories.manga_repository import MangaRepository
from app.repositories.chapter_repository import ChapterRepository


class MangaService:
    def __init__(self, manga_repository=None, chapter_repository=None):
        self.manga_repository = manga_repository or MangaRepository()
        self.chapter_repository = chapter_repository or ChapterRepository()

    def list_manga(self):
        return self.manga_repository.get_all()

    def get_manga(self, manga_id):
        return self.manga_repository.get_by_id(manga_id)

    def get_manga_by_slug(self, slug):
        return self.manga_repository.get_by_slug(slug)

    def get_manga_with_chapters_by_slug(self, slug):
        manga = self.manga_repository.get_by_slug(slug)
        if not manga:
            return None, []
        chapters = self.chapter_repository.get_for_manga(manga.id)
        return manga, chapters

    def get_manga_with_chapters(self, manga_id):
        manga = self.manga_repository.get_by_id(manga_id)
        if not manga:
            return None, []
        chapters = self.chapter_repository.get_for_manga(manga_id)
        return manga, chapters

