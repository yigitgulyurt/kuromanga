from flask import Flask
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def create_app(config_object=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    from app.config import DevelopmentConfig

    app.config.from_object(config_object or DevelopmentConfig)

    db.init_app(app)

    from app.blueprints.manga import manga_bp

    app.register_blueprint(manga_bp)

    return app

