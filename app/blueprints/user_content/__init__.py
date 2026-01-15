from flask import Blueprint


user_content_bp = Blueprint("user_content", __name__)

from . import routes

