from flask import request, redirect, url_for, session, render_template
from app.blueprints.auth import auth_bp
from app.models.user import User
from app import db


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html", error=None)
    username = None
    password = None
    if request.is_json:
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
    if not username:
        username = request.form.get("username") or request.args.get("username")
    if not password:
        password = request.form.get("password") or request.args.get("password")
    if not username or not str(username).strip():
        if request.is_json:
            return {"error": "username_required"}, 400
        return render_template("auth/login.html", error="Kullanıcı adı gerekli")
    if not password or not str(password).strip():
        if request.is_json:
            return {"error": "password_required"}, 400
        return render_template("auth/login.html", error="Şifre gerekli")
    existing = User.query.filter_by(username=username.strip()).first()
    if existing is None:
        if request.is_json:
            return {"error": "user_not_found"}, 404
        return render_template("auth/login.html", error="Kullanıcı bulunamadı")
    if not existing.check_password(password):
        if request.is_json:
            return {"error": "invalid_credentials"}, 401
        return render_template("auth/login.html", error="Şifre yanlış")
    session["user_id"] = existing.id
    if request.is_json:
        return {"status": "ok", "user_id": existing.id}, 200
    return redirect(url_for("manga.manga_list"))


@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    session.pop("user_id", None)
    return redirect(url_for("manga.manga_list"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("auth/register.html", error=None)
    username = None
    password = None
    if request.is_json:
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
    if not username:
        username = request.form.get("username") or request.args.get("username")
    if not password:
        password = request.form.get("password") or request.args.get("password")
    if not username or not str(username).strip():
        if request.is_json:
            return {"error": "username_required"}, 400
        return render_template("auth/register.html", error="Kullanıcı adı gerekli")
    if not password or not str(password).strip():
        if request.is_json:
            return {"error": "password_required"}, 400
        return render_template("auth/register.html", error="Şifre gerekli")
    if len(str(password)) < 6:
        if request.is_json:
            return {"error": "password_too_short"}, 400
        return render_template("auth/register.html", error="Şifre en az 6 karakter olmalı")
    existing = User.query.filter_by(username=username.strip()).first()
    if existing is not None:
        if request.is_json:
            return {"error": "username_taken"}, 409
        return render_template("auth/register.html", error="Kullanıcı adı kullanımda")
    u = User(username=username.strip())
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    session["user_id"] = u.id
    if request.is_json:
        return {"status": "ok", "user_id": u.id}, 201
    return redirect(url_for("manga.manga_list"))
