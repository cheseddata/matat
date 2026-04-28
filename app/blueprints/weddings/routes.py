"""Wedding tracker routes — list / add / edit / delete weddings the org
is supporting. Replaces the operator's Word-doc list."""
from datetime import datetime, date

from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from ...extensions import db
from ...models.wedding import Wedding
from . import weddings_bp


def _admin_or_salesperson_required():
    """Both admins and salespersons can manage the wedding list."""
    role = getattr(current_user, 'role', None)
    if role not in ('admin', 'salesperson'):
        abort(403)


@weddings_bp.route('/')
@login_required
def index():
    """List all upcoming weddings, soonest-Gregorian first.
    Rows without a Gregorian date sink to the bottom."""
    _admin_or_salesperson_required()
    # MySQL doesn't support `NULLS LAST` — we emulate it by sorting on
    # `is_null` first (False sorts before True), then the date itself.
    rows = (Wedding.query_active()
            .order_by(
                Wedding.gregorian_date.is_(None).asc(),
                Wedding.gregorian_date.asc(),
                Wedding.id.desc(),
            )
            .all())
    return render_template('weddings/index.html', weddings=rows)


@weddings_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    _admin_or_salesperson_required()
    if request.method == 'POST':
        return _save(None)
    return render_template('weddings/form.html', wedding=None)


@weddings_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    _admin_or_salesperson_required()
    w = Wedding.query.get_or_404(id)
    if w.is_deleted:
        abort(404)
    if request.method == 'POST':
        return _save(w)
    return render_template('weddings/form.html', wedding=w)


@weddings_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    _admin_or_salesperson_required()
    w = Wedding.query.get_or_404(id)
    w.deleted_at = datetime.utcnow()
    db.session.commit()
    flash('Wedding entry removed.', 'success')
    return redirect(url_for('weddings.index'))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _save(wedding):
    """Shared form-handling for new + edit. Pass `None` to create."""
    f = request.form
    hebrew_date = (f.get('hebrew_date') or '').strip()
    groom = (f.get('groom_name') or '').strip()
    bride = (f.get('bride_name') or '').strip()
    if not (hebrew_date and groom and bride):
        flash('Hebrew date, groom name, and bride name are all required.', 'error')
        return redirect(request.url)

    greg_str = (f.get('gregorian_date') or '').strip()
    greg = None
    if greg_str:
        try:
            greg = datetime.strptime(greg_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Gregorian date must be in YYYY-MM-DD format.', 'error')
            return redirect(request.url)

    is_new = wedding is None
    if is_new:
        wedding = Wedding(created_by_id=getattr(current_user, 'id', None))
        db.session.add(wedding)

    wedding.hebrew_date = hebrew_date
    wedding.gregorian_date = greg
    wedding.groom_name = groom
    wedding.bride_name = bride
    wedding.hall_name = (f.get('hall_name') or '').strip() or None
    wedding.phone = (f.get('phone') or '').strip() or None
    wedding.contact_name = (f.get('contact_name') or '').strip() or None
    wedding.notes = (f.get('notes') or '').strip() or None
    db.session.commit()

    flash(f"Wedding {'added' if is_new else 'updated'} — "
          f"{wedding.groom_name} & {wedding.bride_name}, "
          f"{wedding.hebrew_date}.", 'success')
    return redirect(url_for('weddings.index'))
