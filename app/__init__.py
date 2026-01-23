from flask import Flask, session, render_template
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def create_app(config_object=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    from app.config import DevelopmentConfig

    app.config.from_object(config_object or DevelopmentConfig)

    db.init_app(app)

    with app.app_context():
        try:
            from app.models.manga import Manga
            uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
            if uri.startswith("sqlite"):
                rows = db.session.execute("PRAGMA table_info('user')").fetchall()
                cols = {r[1] for r in rows}
                if "password_hash" not in cols:
                    db.session.execute("ALTER TABLE user ADD COLUMN password_hash VARCHAR(256)")
                if "is_admin" not in cols:
                    db.session.execute("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0")
                
                # Manga slug migration
                m_rows = db.session.execute("PRAGMA table_info('manga')").fetchall()
                m_cols = {r[1] for r in m_rows}
                if "slug" not in m_cols:
                    db.session.execute("ALTER TABLE manga ADD COLUMN slug VARCHAR(255)")
                    db.session.commit()
                    # Populate slugs for existing mangas
                    mangas = Manga.query.all()
                    for m in mangas:
                        if not m.slug:
                            m.slug = Manga.slugify(m.title)
                    db.session.commit()
                
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

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("errors/403.html"), 403

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

    @app.route("/sw.js")
    def serve_sw():
        from flask import make_response
        response = make_response(app.send_static_file("sw.js"))
        response.headers["Content-Type"] = "application/javascript"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.route("/manifest.json")
    def serve_manifest():
        from flask import make_response
        response = make_response(app.send_static_file("manifest.json"))
        response.headers["Content-Type"] = "application/manifest+json"
        return response

    @app.route("/offline")
    def offline():
        return render_template("offline.html")

    @app.route("/install")
    def install():
        return render_template("install.html")

    return app
