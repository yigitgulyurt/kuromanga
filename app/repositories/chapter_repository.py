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

    def get_by_number(self, manga_id, chapter_number):
        return Chapter.query.filter_by(manga_id=manga_id, number=chapter_number).first()

