from app.models.page import Page


class PageRepository:
    def get_for_chapter(self, chapter_id):
        return (
            Page.query.filter_by(chapter_id=chapter_id)
            .order_by(Page.number.asc())
            .all()
        )

