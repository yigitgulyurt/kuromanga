from flask import Blueprint


manga_bp = Blueprint("manga", __name__)

from . import routes

