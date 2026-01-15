from app import db


class ReadingProgress(db.Model):
    __tablename__ = "reading_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    manga_id = db.Column(db.Integer, nullable=False)
    chapter_id = db.Column(db.Integer, nullable=False)
    last_page_number = db.Column(db.Integer, nullable=False)

