from app import db
from app.models.reading_progress import ReadingProgress


class ReadingProgressRepository:
    def get_last_read_chapter(self, user_id, manga_id):
        return ReadingProgress.query.filter_by(
            user_id=user_id,
            manga_id=manga_id,
        ).first()

    def set_last_read_chapter(self, user_id, manga_id, chapter_id):
        progress = self.get_last_read_chapter(user_id, manga_id)
        if progress is None:
            progress = ReadingProgress(
                user_id=user_id,
                manga_id=manga_id,
                chapter_id=chapter_id,
                last_page_number=None,
            )
            db.session.add(progress)
        else:
            progress.chapter_id = chapter_id
            progress.last_page_number = None
        db.session.commit()
