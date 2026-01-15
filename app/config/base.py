import os


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///kuromanga.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    STORAGE_MANGA_PATH = os.environ.get(
        "STORAGE_MANGA_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "manga"),
    )
    STORAGE_RUN_LOGS_PATH = os.environ.get(
        "STORAGE_RUN_LOGS_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "run_logs"),
    )
