from app.repositories.reading_progress_repository import (
    ReadingProgressRepository,
)


class ReadingProgressService:
    def __init__(self, repository=None):
        self.repository = repository or ReadingProgressRepository()

    def get_progress(self, user_id, manga_id, chapter_id):
        return self.repository.get_progress(user_id, manga_id, chapter_id)

    def save_progress(self, user_id, manga_id, chapter_id, page_number):
        self.repository.upsert_progress(user_id, manga_id, chapter_id, page_number)

