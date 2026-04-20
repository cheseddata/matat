from flask import Blueprint

gemach_bp = Blueprint('gemach', __name__, url_prefix='/gemach')

from . import routes  # noqa
from . import reports  # noqa — report endpoints (PDF/Excel)
from . import sync     # noqa — Access sync endpoints
from . import extras   # noqa — Hazarot, Siumim, Hork history, Tools, extra reports
