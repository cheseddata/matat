from flask import Blueprint

weddings_bp = Blueprint('weddings', __name__, url_prefix='/weddings')

from . import routes  # noqa: E402,F401
