from flask import Flask
from flask import session
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def create_app(config_object=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    from app.config import DevelopmentConfig

    app.config.from_object(config_object or DevelopmentConfig)

    db.init_app(app)

    with app.app_context():
        try:
            uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
            if uri.startswith("sqlite"):
                rows = db.session.execute("PRAGMA table_info('user')").fetchall()
                cols = {r[1] for r in rows}
                if "password_hash" not in cols:
                    db.session.execute("ALTER TABLE user ADD COLUMN password_hash VARCHAR(256)")
                    db.session.commit()
        except Exception:
            pass

    from app.blueprints.manga import manga_bp
    from app.blueprints.user_content import user_content_bp
    from app.blueprints.indexer import indexer_bp
    from app.blueprints.health import health_bp
    from app.blueprints.status import status_bp
    from app.blueprints.storage import storage_bp
    from app.blueprints.auth import auth_bp

    app.register_blueprint(manga_bp)
    app.register_blueprint(user_content_bp)
    app.register_blueprint(indexer_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(storage_bp)
    app.register_blueprint(auth_bp)

    @app.context_processor
    def inject_current_user():
        try:
            from app.models.user import User
            uid = session.get("user_id")
            user = None
            if uid:
                user = User.query.get(uid)
            return {"current_user": user, "is_authenticated": bool(user)}
        except Exception:
            return {"current_user": None, "is_authenticated": False}

    return app
