from app import db


class Chapter(db.Model):
    __tablename__ = "chapter"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=True)

    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id"), nullable=False)
    manga = db.relationship("Manga", back_populates="chapters", lazy="joined")

    pages = db.relationship("Page", back_populates="chapter", lazy="select")

