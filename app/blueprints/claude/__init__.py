from flask import Blueprint

claude_bp = Blueprint('claude', __name__, url_prefix='/claude')

from . import routes
