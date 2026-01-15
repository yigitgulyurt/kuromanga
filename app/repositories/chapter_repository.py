from app.models.chapter import Chapter


class ChapterRepository:
    def get_for_manga(self, manga_id):
        return (
            Chapter.query.filter_by(manga_id=manga_id)
            .order_by(Chapter.number.asc())
            .all()
        )

    def get_by_id(self, chapter_id):
        return Chapter.query.get(chapter_id)

