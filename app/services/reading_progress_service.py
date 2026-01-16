from app.repositories.reading_progress_repository import (
    ReadingProgressRepository,
)


class ReadingProgressService:
    def __init__(self, repository=None):
        self.repository = repository or ReadingProgressRepository()

    def get_last_read_chapter(self, user_id, manga_id):
        return self.repository.get_last_read_chapter(user_id, manga_id)

    def set_last_read_chapter(self, user_id, manga_id, chapter_id):
        self.repository.set_last_read_chapter(user_id, manga_id, chapter_id)
