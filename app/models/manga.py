import re
import unicodedata
from app import db


class Manga(db.Model):
    __tablename__ = "manga"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=True)
    description = db.Column(db.Text, nullable=True)

    chapters = db.relationship("Chapter", back_populates="manga", lazy="select")

    @staticmethod
    def slugify(text):
        text = text.lower()
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        text = re.sub(r'[^\w\s-]', '', text).strip()
        text = re.sub(r'[-\s]+', '-', text)
        return text

