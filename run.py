from app import create_app, db
from app.models.manga import Manga
from app.models.chapter import Chapter
from app.models.page import Page
from app.models.reading_progress import ReadingProgress


app = create_app()


@app.cli.command("init-db")
def init_db():
    with app.app_context():
        db.create_all()

@app.cli.command("drop-db")
def drop_db():
    with app.app_context():
        db.drop_all()

@app.cli.command("reset-db")
def reset_db():
    with app.app_context():
        db.drop_all()
        db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
