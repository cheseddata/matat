from flask import Blueprint

ztorm_bp = Blueprint('ztorm', __name__, url_prefix='/ztorm')

from . import routes  # noqa
