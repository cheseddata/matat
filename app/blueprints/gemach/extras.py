"""Extra Access-matching screens: Hazarot, Siumim, Hork history,
Haverim tools submenu, and 3 report sub-screens (Haverim / Lovim /
Horaot-Keva). All sandbox-safe.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from decimal import Decimal
from flask import render_template, request, flash, redirect, url_for

from ...extensions import db
from ...models import (
    GemachMember, GemachLoan, GemachLoanTransaction, GemachTransaction,
    GemachCancelledLoan, GemachInstitution, GemachCancellationReason,
)
from ...utils.decorators import gemach_required
from ...utils.sandbox import is_sandbox
from ...utils.reports import ReportSpec, Column, fmt_date, fmt_money
from .reports import _dispatch, _parse_date
from . import gemach_bp
from sqlalchemy import func


# ============================================================
# Hazarot (bounces) — screens 11 + 12
# ============================================================
@gemach_bp.route('/hazarot')
@gemach_required
def hazarot_list():
    """פעולות — list of bounced loan transactions (screen 12 style)."""
    date_from = _parse_date(request.args.get('date_from'))
    date_to = _parse_date(request.args.get('date_to'))

    q = (GemachLoanTransaction.query
         .filter(GemachLoanTransaction.bounced.is_(True))
         .join(GemachLoan, GemachLoanTransaction.loan_id == GemachLoan.id)
         .join(GemachMember, GemachLoan.member_id == GemachMember.id))
    if date_from:
        q = q.filter(GemachLoanTransaction.transaction_date >= date_from)
    if date_to:
        q = q.filter(GemachLoanTransaction.transaction_date <= date_to)
    q = q.order_by(GemachLoanTransaction.transaction_date.desc())

    reasons = {r.code: r.name for r in GemachCancellationReason.query.all()}
    bounces = q.limit(500).all()
    return render_template('gemach/hazarot.html',
                           bounces=bounces, reasons=reasons,
                           date_from=date_from, date_to=date_to)


@gemach_bp.route('/hazarot/new', methods=['GET', 'POST'])
@gemach_required
def hazarot_new():
    """Record a new bounce (screen 11 style — entry form)."""
    if request.method == 'POST':
        hork_no = request.form.get('hork_no', '').strip()
        asmachta = request.form.get('asmachta', '').strip()
        amount = request.form.get('amount', '0').strip()
        reason = request.form.get('reason', '').strip()
        cancel_flag = bool(request.form.get('cancel'))

        loan = GemachLoan.query.filter_by(gmach_num_hork=int(hork_no)).first() if hork_no.isdigit() else None
        if not loan:
            flash(f'הו״ק מס׳ {hork_no} לא נמצא.', 'error')
            return redirect(url_for('gemach.hazarot_new'))

        try:
            amt = Decimal(amount.replace(',', '')) if amount else Decimal('0')
        except Exception:
            amt = Decimal('0')

        tx = GemachLoanTransaction(
            loan_id=loan.id,
            transaction_date=date.today(),
            asmachta=int(asmachta) if asmachta.isdigit() else None,
            amount_ils=amt,
            bounced=True,
            bounce_reason=reason,
        )
        db.session.add(tx)
        if cancel_flag:
            loan.status = 'b'
        db.session.commit()

        tag = '[SANDBOX] ' if is_sandbox() else ''
        flash(f'{tag}בוצע: החזר הוקלט על הו״ק {loan.gmach_num_hork} '
              f'(₪{amt:,.2f}){", הו״ק בוטל" if cancel_flag else ""}.', 'success')
        return redirect(url_for('gemach.hazarot_list'))

    reasons = GemachCancellationReason.query.order_by(GemachCancellationReason.code).all()
    return render_template('gemach/hazarot_new.html',
                           reasons=reasons, sandbox=is_sandbox())


# ============================================================
# Siumim (year-end closings)
# ============================================================
@gemach_bp.route('/siumim', methods=['GET', 'POST'])
@gemach_required
def siumim():
    """Batch-cancel hork records that completed by a given date (screen 18)."""
    if request.method == 'POST':
        end_date = _parse_date(request.form.get('end_date'))
        if not end_date:
            flash('נא להזין תאריך תקף.', 'error')
            return redirect(url_for('gemach.siumim'))

        # Pick hork that finished payments by end_date.
        candidates = (GemachLoan.query.filter(
            GemachLoan.status == 'p',
            GemachLoan.last_charge_date <= end_date,
            GemachLoan.payments_made >= GemachLoan.committed_payments,
        )).all()

        count = len(candidates)
        if is_sandbox():
            flash(f'[SANDBOX] היו מבוטלים {count} הו״ק שהסתיימו עד {end_date:%d/%m/%Y} — ללא ביצוע בפועל.', 'info')
        else:
            for l in candidates:
                l.status = 's'  # satisfied
            db.session.commit()
            flash(f'בוצע: {count} הו״ק סומנו כהושלמו.', 'success')
        return redirect(url_for('gemach.siumim'))

    # Pre-compute the default date (end of last year) and a preview count.
    default_date = date(date.today().year - 1, 12, 31)
    preview_count = (GemachLoan.query.filter(
        GemachLoan.status == 'p',
        GemachLoan.last_charge_date <= default_date,
        GemachLoan.payments_made >= GemachLoan.committed_payments,
    )).count()
    return render_template('gemach/siumim.html',
                           default_date=default_date,
                           preview_count=preview_count,
                           sandbox=is_sandbox())


# ============================================================
# Hork history (standalone) — screen 10
# ============================================================
@gemach_bp.route('/hork/history')
@gemach_required
def hork_history():
    """All loan transactions across all members (paginated)."""
    page = request.args.get('page', 1, type=int)
    only_bounced = request.args.get('bounced') == '1'

    q = (GemachLoanTransaction.query
         .join(GemachLoan, GemachLoanTransaction.loan_id == GemachLoan.id)
         .join(GemachMember, GemachLoan.member_id == GemachMember.id))
    if only_bounced:
        q = q.filter(GemachLoanTransaction.bounced.is_(True))
    q = q.order_by(GemachLoanTransaction.transaction_date.desc())

    paged = q.paginate(page=page, per_page=100)
    return render_template('gemach/hork_history.html',
                           transactions=paged, only_bounced=only_bounced)


# ============================================================
# Haverim tools submenu (screen 08)
# ============================================================
@gemach_bp.route('/tools/haverim')
@gemach_required
def haverim_tools():
    return render_template('gemach/tools_haverim.html')


# ============================================================
# Report sub-screens: Haverim / Lovim / Horaot-Keva
# (supplementary to the 8 main reports)
# ============================================================
@gemach_bp.route('/reports/haverim_detailed')
@gemach_required
def report_haverim_detailed():
    """All members with key fields — full list report."""
    members = GemachMember.query.order_by(
        GemachMember.last_name, GemachMember.first_name
    ).all()
    rows = [{
        'card_no': m.gmach_card_no,
        'title': m.title or '',
        'last':  m.last_name or '',
        'first': m.first_name or '',
        'tz':    m.teudat_zehut or '',
        'phone': m.primary_phone or '',
        'city':  m.city or '',
        'type':  m.member_type or '',
    } for m in members]

    spec = ReportSpec(
        title='דו״ח חברים (מפורט)',
        subtitle='Detailed Members Report',
        columns=[
            Column('card_no', 'כרטיס',  width=0.6, align='center'),
            Column('title',   'תואר',   width=0.6),
            Column('last',    'שם משפחה', width=1.5),
            Column('first',   'שם פרטי',  width=1.5),
            Column('tz',      'ת.ז.',   width=0.9, align='center'),
            Column('phone',   'טלפון',  width=1.0),
            Column('city',    'עיר',    width=1.0),
            Column('type',    'סוג',    width=0.5, align='center'),
        ],
        rows=rows,
    )
    return _dispatch(spec)


@gemach_bp.route('/reports/lovim')
@gemach_required
def report_lovim():
    """Borrowers — members with one or more active hork records."""
    results = (db.session.query(
        GemachMember,
        func.count(GemachLoan.id).label('n'),
        func.sum(GemachLoan.amount).label('sum_amt'),
        func.sum(GemachLoan.amount_paid).label('sum_paid'),
    ).join(GemachLoan, GemachLoan.member_id == GemachMember.id)
     .filter(GemachLoan.status == 'p')
     .group_by(GemachMember.id)
     .order_by(GemachMember.last_name, GemachMember.first_name)
    ).all()

    rows = []
    tot_amt = Decimal('0'); tot_paid = Decimal('0')
    for m, n, s_amt, s_paid in results:
        s_amt = Decimal(str(s_amt or 0)); s_paid = Decimal(str(s_paid or 0))
        rows.append({
            'card_no': m.gmach_card_no,
            'name':    m.full_name,
            'tz':      m.teudat_zehut or '',
            'phone':   m.primary_phone or '',
            'loans':   n,
            'amt':     s_amt,
            'paid':    s_paid,
            'balance': s_amt - s_paid,
        })
        tot_amt += s_amt; tot_paid += s_paid

    spec = ReportSpec(
        title='לווים — חברים עם הו״ק פעילים',
        subtitle='Active Borrowers Report',
        columns=[
            Column('card_no', 'כרטיס',   width=0.5, align='center'),
            Column('name',    'שם',      width=2.0),
            Column('tz',      'ת.ז.',    width=0.9, align='center'),
            Column('phone',   'טלפון',   width=1.0),
            Column('loans',   'הו״ק',    width=0.5, align='center'),
            Column('amt',     'סה״כ',    width=1.0, align='left'),
            Column('paid',    'שולם',    width=1.0, align='left'),
            Column('balance', 'יתרה',    width=1.0, align='left'),
        ],
        rows=rows,
        totals={'amt': tot_amt, 'paid': tot_paid, 'balance': tot_amt - tot_paid},
    )
    return _dispatch(spec)


@gemach_bp.route('/reports/horaot_keva')
@gemach_required
def report_horaot_keva():
    """Standing orders report — every active hork with its bank details."""
    loans = (GemachLoan.query
             .filter(GemachLoan.status == 'p')
             .join(GemachMember, GemachLoan.member_id == GemachMember.id)
             .order_by(GemachLoan.charge_day, GemachMember.last_name)
             .all())

    rows = []
    tot_amt = Decimal('0')
    for l in loans:
        amt = Decimal(str(l.amount or 0))
        rows.append({
            'hork':     l.gmach_num_hork,
            'card':     l.member.gmach_card_no if l.member else '',
            'name':     l.member.full_name if l.member else '',
            'bank':     l.bank_code or '',
            'branch':   l.branch_code or '',
            'account':  l.account_number or '',
            'day':      l.charge_day or '',
            'amount':   amt,
            'start':    l.start_date,
        })
        tot_amt += amt

    spec = ReportSpec(
        title='דו״ח הוראות קבע',
        subtitle='Standing Orders (Horaot Keva) Report',
        columns=[
            Column('hork',    'מס׳ הו״ק', width=0.7, align='center'),
            Column('card',    'כרטיס',   width=0.6, align='center'),
            Column('name',    'שם',      width=2.0),
            Column('bank',    'בנק',     width=0.5, align='center'),
            Column('branch',  'סניף',    width=0.6, align='center'),
            Column('account', 'חשבון',   width=1.0, align='center'),
            Column('day',     'יום',     width=0.4, align='center'),
            Column('amount',  'סכום',    width=1.0, align='left'),
            Column('start',   'התחלה',   width=0.9, align='center'),
        ],
        rows=rows,
        totals={'amount': tot_amt},
    )
    return _dispatch(spec)
