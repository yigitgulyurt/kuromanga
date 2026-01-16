from app import db
from datetime import datetime


class ToRead(db.Model):
    __tablename__ = "to_read"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    manga_id = db.Column(db.Integer, db.ForeignKey("manga.id"), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "manga_id", name="uq_to_read_user_manga"),
    )

