from flask import Blueprint

status_bp = Blueprint("status", __name__, url_prefix="/status")

from app.blueprints.status import routes
