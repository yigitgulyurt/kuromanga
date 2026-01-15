from app import db


class Page(db.Model):
    __tablename__ = "page"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    image_path = db.Column(db.String(512), nullable=False)

    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"), nullable=False)
    chapter = db.relationship("Chapter", back_populates="pages", lazy="joined")

