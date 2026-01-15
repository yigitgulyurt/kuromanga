from app.models.manga import Manga


class MangaRepository:
    def get_all(self):
        return Manga.query.order_by(Manga.title).all()

    def get_by_id(self, manga_id):
        return Manga.query.get(manga_id)

