"""Wedding tracker — list / add / edit / delete / hide / export."""
import csv
import io
from datetime import datetime, date

from flask import (render_template, request, redirect, url_for, flash, abort,
                   Response, make_response)
from flask_login import login_required, current_user

from ...extensions import db
from ...models.wedding import Wedding
from . import weddings_bp


# Username allowlist for the wedding tracker. The list is small and
# rarely changes, so a hardcoded set is simpler than a permission row.
# (Same set is mirrored in templates/base.html for the nav-link gate.)
_WEDDING_USERNAMES = {'admin', 'ggoldblum', 'matatmor@gmail.com'}


def _admin_or_salesperson_required():
    """Wedding-tracker access: only the operators on the allowlist."""
    if (getattr(current_user, 'username', None) or '') not in _WEDDING_USERNAMES:
        abort(403)


def _ordered_query(show_hidden=False):
    """Oldest first by gregorian_date — undated rows fall to the bottom in
    insertion order. If show_hidden is False (default), filter out
    operator-hidden rows."""
    q = Wedding.query_active()
    if not show_hidden:
        q = q.filter(Wedding.hidden.is_(False))
    return q.order_by(
        # MySQL has no NULLS LAST → emulate via is_null sort key.
        Wedding.gregorian_date.is_(None).asc(),
        Wedding.gregorian_date.asc(),
        Wedding.id.asc(),
    )


@weddings_bp.route('/')
@login_required
def index():
    _admin_or_salesperson_required()
    show_hidden = request.args.get('show_hidden') == '1'
    rows = _ordered_query(show_hidden=show_hidden).all()
    return render_template('weddings/index.html',
                           weddings=rows, show_hidden=show_hidden)


@weddings_bp.route('/print')
@login_required
def print_view():
    """Print-friendly version — same data, stripped chrome, large font.
    Browser's "Save as PDF" turns this into the PDF export."""
    _admin_or_salesperson_required()
    show_hidden = request.args.get('show_hidden') == '1'
    rows = _ordered_query(show_hidden=show_hidden).all()
    return render_template('weddings/print.html', weddings=rows)


@weddings_bp.route('/export.csv')
@login_required
def export_csv():
    """CSV that opens correctly in Excel (UTF-8 BOM for Hebrew)."""
    _admin_or_salesperson_required()
    rows = _ordered_query(show_hidden=request.args.get('show_hidden') == '1').all()

    out = io.StringIO()
    out.write('﻿')  # BOM so Excel auto-detects UTF-8 (without it Hebrew is gibberish)
    w = csv.writer(out, dialect='excel')
    w.writerow(['תאריך עברי', 'תאריך לועזי', 'חתן', 'כלה',
                'אולם', 'איש קשר', 'טלפון', 'הערות'])
    for r in rows:
        w.writerow([
            r.hebrew_date or '',
            r.gregorian_date.strftime('%d/%m/%Y') if r.gregorian_date else '',
            r.groom_name or '',
            r.bride_name or '',
            r.hall_name or '',
            r.contact_name or '',
            r.phone or '',
            r.notes or '',
        ])
    return Response(
        out.getvalue().encode('utf-8'),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=weddings.csv'},
    )


@weddings_bp.route('/export.doc')
@login_required
def export_doc():
    """HTML wrapped with Word-friendly headers — Word opens it as .doc.
    Simpler than building a real .docx and good enough for a list."""
    _admin_or_salesperson_required()
    rows = _ordered_query(show_hidden=request.args.get('show_hidden') == '1').all()
    html = render_template('weddings/export_word.html', weddings=rows)
    resp = make_response(html)
    resp.headers['Content-Type'] = 'application/msword; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename=weddings.doc'
    return resp


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


@weddings_bp.route('/<int:id>/toggle-hidden', methods=['POST'])
@login_required
def toggle_hidden(id):
    """Operator can hide a wedding from the active list without deleting
    the record (e.g. wedding already happened, or family withdrew)."""
    _admin_or_salesperson_required()
    w = Wedding.query.get_or_404(id)
    w.hidden = not w.hidden
    db.session.commit()
    msg = 'הוסתר מהרשימה' if w.hidden else 'הוחזר לרשימה'
    flash(f'{w.groom_name} & {w.bride_name}: {msg}.', 'success')
    return redirect(request.referrer or url_for('weddings.index'))


# ---------------------------------------------------------------------------
def _save(wedding):
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
