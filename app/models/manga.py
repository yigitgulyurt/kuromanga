from app import db


class Manga(db.Model):
    __tablename__ = "manga"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    chapters = db.relationship("Chapter", back_populates="manga", lazy="select")

