from app import db
from app.models.reading_progress import ReadingProgress


class ReadingProgressRepository:
    def get_progress(self, user_id, manga_id, chapter_id):
        return ReadingProgress.query.filter_by(
            user_id=user_id,
            manga_id=manga_id,
            chapter_id=chapter_id,
        ).first()

    def upsert_progress(self, user_id, manga_id, chapter_id, page_number):
        progress = self.get_progress(user_id, manga_id, chapter_id)
        if progress is None:
            progress = ReadingProgress(
                user_id=user_id,
                manga_id=manga_id,
                chapter_id=chapter_id,
                last_page_number=page_number,
            )
            db.session.add(progress)
        else:
            progress.last_page_number = page_number
        db.session.commit()

