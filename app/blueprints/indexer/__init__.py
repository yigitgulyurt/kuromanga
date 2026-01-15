from flask import Blueprint


indexer_bp = Blueprint("indexer", __name__)

from . import routes

