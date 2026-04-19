"""Gemach report endpoints.

Each report is a route that:
  * reads filter params (date range, status, institution, member…)
  * runs a query
  * builds a ReportSpec
  * renders HTML, or exports PDF / Excel, depending on ?format=...

The switchboard's Reports page links each tile to one of these routes.
Masav Collection and Hash Export are here too — they write their output to
`instance/masav_batches/` and `instance/hash_exports/` respectively and
in sandbox mode NEVER submit to the bank or external accounting system.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from flask import render_template, request, flash, redirect, url_for, current_app
from sqlalchemy import and_, or_, func

from ...extensions import db
from ...models import (
    GemachMember, GemachLoan, GemachLoanTransaction, GemachTransaction,
    GemachCancelledLoan, GemachInstitution, GemachMemorial,
    Donor, Donation,
)
from ...utils.decorators import gemach_required
from ...utils.reports import (
    ReportSpec, Column, export_pdf, export_xlsx,
    fmt_money, fmt_date, fmt_int,
)
from ...utils.sandbox import is_sandbox
from . import gemach_bp


# ---------------------------------------------------------------------------
# Shared: render the requested output format
# ---------------------------------------------------------------------------
def _dispatch(spec: ReportSpec, tpl: str = 'gemach/reports/_base.html'):
    fmt = (request.args.get('format') or '').lower()
    if fmt == 'pdf':
        return export_pdf(spec)
    if fmt == 'xlsx':
        return export_xlsx(spec)
    qs = request.query_string.decode('utf-8')
    return render_template(tpl, spec=spec, query_string=qs)


def _parse_date(s: str):
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# 1. Loans Report  (דו״ח הלוואות)
# ---------------------------------------------------------------------------
@gemach_bp.route('/reports/loans')
@gemach_required
def report_loans():
    status = request.args.get('status', 'p')
    institution_id = request.args.get('institution_id', type=int)

    q = GemachLoan.query.join(GemachMember, GemachLoan.member_id == GemachMember.id)
    if status:
        q = q.filter(GemachLoan.status == status)
    if institution_id:
        q = q.filter(GemachLoan.institution_id == institution_id)
    q = q.order_by(GemachLoan.start_date.desc().nullslast())
    loans = q.all()

    status_label = {'p': 'פעיל', 's': 'הושלם', 'b': 'בוטל', '': 'הכל'}.get(status, status)
    institutions = GemachInstitution.query.order_by(GemachInstitution.name).all()
    inst = next((i for i in institutions if i.id == institution_id), None)

    rows = []
    tot_amount = Decimal('0')
    tot_paid = Decimal('0')
    for l in loans:
        rows.append({
            'num_hork':   l.gmach_num_hork,
            'member':     l.member.full_name if l.member else '—',
            'card_no':    l.member.gmach_card_no if l.member else '',
            'amount':     l.amount,
            'paid':       l.amount_paid,
            'currency':   l.currency,
            'start_date': l.start_date,
            'payments':   f'{l.payments_made or 0} / {l.committed_payments or "∞"}',
            'status':     {'p': 'פעיל', 's': 'הושלם', 'b': 'בוטל'}.get(l.status, l.status),
            'institution': l.institution.name if l.institution else '',
        })
        tot_amount += Decimal(str(l.amount or 0))
        tot_paid += Decimal(str(l.amount_paid or 0))

    spec = ReportSpec(
        title='דו״ח הו״ק (הלוואות)',
        subtitle='Gemach Loans Report',
        columns=[
            Column('num_hork',   'מס׳ הו״ק',   width=0.8, align='center'),
            Column('card_no',    'כרטיס',      width=0.7, align='center'),
            Column('member',     'חבר',        width=2.2),
            Column('amount',     'סכום',       width=1.0, align='left'),
            Column('paid',       'שולם',       width=1.0, align='left'),
            Column('currency',   'מטבע',       width=0.5, align='center'),
            Column('start_date', 'התחלה',      width=0.9, align='center'),
            Column('payments',   'תשלומים',    width=0.9, align='center'),
            Column('status',     'סטטוס',      width=0.7, align='center'),
            Column('institution','מוסד',       width=1.2),
        ],
        rows=rows,
        filters={'סטטוס': status_label, 'מוסד': inst.name if inst else 'הכל'},
        totals={'amount': tot_amount, 'paid': tot_paid},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# 2. Summaries  (סיכומים — monthly cash flow)
# ---------------------------------------------------------------------------
@gemach_bp.route('/reports/summaries')
@gemach_required
def report_summaries():
    year = request.args.get('year', type=int) or datetime.utcnow().year

    # Aggregate general transactions by (category, month).
    # SQLite: strftime('%Y-%m', transaction_date)
    results = db.session.execute(db.text(
        """
        SELECT
            strftime('%Y-%m', transaction_date) AS ym,
            category,
            COUNT(*) AS n,
            SUM(COALESCE(amount_ils, 0)) AS sum_ils,
            SUM(COALESCE(amount_usd, 0)) AS sum_usd
        FROM gemach_transactions
        WHERE strftime('%Y', transaction_date) = :y
        GROUP BY ym, category
        ORDER BY ym, category
        """
    ), {'y': str(year)}).fetchall()

    cat_label = {
        'הלו': 'הלוואות', 'פקד': 'פקדונות', 'תרו': 'תרומות',
        'תמי': 'תמיכות', 'הוצ': 'הוצאות',
    }

    rows = []
    tot_ils = Decimal('0')
    tot_usd = Decimal('0')
    for r in results:
        rows.append({
            'month':    r.ym,
            'category': cat_label.get(r.category, r.category) if r.category else '',
            'n':        r.n,
            'sum_ils':  r.sum_ils or 0,
            'sum_usd':  r.sum_usd or 0,
        })
        tot_ils += Decimal(str(r.sum_ils or 0))
        tot_usd += Decimal(str(r.sum_usd or 0))

    spec = ReportSpec(
        title=f'סיכומים {year}',
        subtitle='Monthly Summary by Category',
        columns=[
            Column('month',    'חודש',     width=0.9, align='center'),
            Column('category', 'קטגוריה',  width=1.2),
            Column('n',        'מס׳ תנועות', width=0.8, align='center'),
            Column('sum_ils',  'סה״כ ש״ח', width=1.2, align='left'),
            Column('sum_usd',  'סה״כ $',   width=1.2, align='left'),
        ],
        rows=rows,
        filters={'שנה': year},
        totals={'sum_ils': tot_ils, 'sum_usd': tot_usd},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# 3. Donations  (דו״ח תרומות)
# ---------------------------------------------------------------------------
@gemach_bp.route('/reports/donations')
@gemach_required
def report_donations():
    date_from = _parse_date(request.args.get('date_from'))
    date_to   = _parse_date(request.args.get('date_to'))

    q = GemachTransaction.query.filter(GemachTransaction.category == 'תרו')
    if date_from:
        q = q.filter(GemachTransaction.transaction_date >= date_from)
    if date_to:
        q = q.filter(GemachTransaction.transaction_date <= date_to)
    q = q.order_by(GemachTransaction.transaction_date.desc())
    txns = q.all()

    rows = []
    tot_ils = Decimal('0')
    tot_usd = Decimal('0')
    for t in txns:
        rows.append({
            'date':        t.transaction_date,
            'member':      t.member.full_name if t.member else '—',
            'card_no':     t.member.gmach_card_no if t.member else '',
            'amount_ils':  t.amount_ils,
            'amount_usd':  t.amount_usd,
            'method':      t.payment_method or '',
            'description': t.description or '',
            'receipt':     '✓' if t.receipt_issued else '',
        })
        tot_ils += Decimal(str(t.amount_ils or 0))
        tot_usd += Decimal(str(t.amount_usd or 0))

    spec = ReportSpec(
        title='דו״ח תרומות',
        subtitle='Donations Report',
        columns=[
            Column('date',        'תאריך',   width=0.9, align='center'),
            Column('card_no',     'כרטיס',   width=0.6, align='center'),
            Column('member',      'תורם',    width=2.0),
            Column('amount_ils',  'ש״ח',     width=1.0, align='left'),
            Column('amount_usd',  '$',       width=0.9, align='left'),
            Column('method',      'שיטה',    width=0.9),
            Column('description', 'הערה',    width=1.8),
            Column('receipt',     'קבלה',    width=0.5, align='center'),
        ],
        rows=rows,
        filters={
            'מתאריך': fmt_date(date_from) or '—',
            'עד תאריך': fmt_date(date_to) or '—',
        },
        totals={'amount_ils': tot_ils, 'amount_usd': tot_usd},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# 4. Deposits  (דו״ח פקדונות)
# ---------------------------------------------------------------------------
@gemach_bp.route('/reports/deposits')
@gemach_required
def report_deposits():
    q = GemachTransaction.query.filter(GemachTransaction.category == 'פקד')
    q = q.order_by(GemachTransaction.transaction_date.desc())
    txns = q.all()

    # Group by member to show current deposit balance
    by_member = {}
    for t in txns:
        if not t.member_id:
            continue
        key = t.member_id
        d = by_member.setdefault(key, {
            'member_id': t.member_id,
            'member':    t.member.full_name if t.member else '',
            'card_no':   t.member.gmach_card_no if t.member else '',
            'deposits':  Decimal('0'),
            'deposits_usd': Decimal('0'),
            'last_date': None,
            'count':     0,
        })
        # Deposits typically increase balance; tash (deposit_or_withdraw) indicates direction
        sign = 1 if (t.deposit_or_withdraw or '').startswith('ה') else -1
        d['deposits'] += sign * Decimal(str(t.amount_ils or 0))
        d['deposits_usd'] += sign * Decimal(str(t.amount_usd or 0))
        if d['last_date'] is None or (t.transaction_date and t.transaction_date > d['last_date']):
            d['last_date'] = t.transaction_date
        d['count'] += 1

    rows = sorted(by_member.values(), key=lambda r: r['member'])
    tot_ils = sum((r['deposits'] for r in rows), Decimal('0'))
    tot_usd = sum((r['deposits_usd'] for r in rows), Decimal('0'))

    spec = ReportSpec(
        title='דו״ח פקדונות',
        subtitle='Deposits Report — current balance per member',
        columns=[
            Column('card_no',      'כרטיס',     width=0.6, align='center'),
            Column('member',       'חבר',       width=2.0),
            Column('deposits',     'יתרה ש״ח',  width=1.0, align='left'),
            Column('deposits_usd', 'יתרה $',    width=1.0, align='left'),
            Column('last_date',    'תנועה אחרונה', width=0.9, align='center'),
            Column('count',        'תנועות',    width=0.6, align='center'),
        ],
        rows=rows,
        totals={'deposits': tot_ils, 'deposits_usd': tot_usd},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# 5. Supports  (תמיכות outgoing)
# ---------------------------------------------------------------------------
@gemach_bp.route('/reports/supports')
@gemach_required
def report_supports():
    q = GemachTransaction.query.filter(GemachTransaction.category == 'תמי')
    q = q.order_by(GemachTransaction.transaction_date.desc())
    txns = q.all()
    rows = []
    tot_ils = Decimal('0')
    for t in txns:
        rows.append({
            'date':        t.transaction_date,
            'member':      t.member.full_name if t.member else '—',
            'card_no':     t.member.gmach_card_no if t.member else '',
            'amount_ils':  t.amount_ils,
            'description': t.description or '',
            'method':      t.payment_method or '',
        })
        tot_ils += Decimal(str(t.amount_ils or 0))

    spec = ReportSpec(
        title='דו״ח תמיכות',
        subtitle='Supports / Grants Report',
        columns=[
            Column('date',        'תאריך',  width=0.9, align='center'),
            Column('card_no',     'כרטיס',  width=0.6, align='center'),
            Column('member',      'מקבל',   width=2.0),
            Column('amount_ils',  'ש״ח',    width=1.0, align='left'),
            Column('method',      'שיטה',   width=0.9),
            Column('description', 'הערה',   width=1.8),
        ],
        rows=rows,
        totals={'amount_ils': tot_ils},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# 6. Gmach Totals  (סיכומי גמ״ח — fund overview)
# ---------------------------------------------------------------------------
@gemach_bp.route('/reports/gmach_totals')
@gemach_required
def report_gmach_totals():
    # Lifetime totals per category
    results = db.session.execute(db.text(
        """
        SELECT
            category,
            COUNT(*) AS n,
            SUM(COALESCE(amount_ils, 0)) AS sum_ils,
            SUM(COALESCE(amount_usd, 0)) AS sum_usd,
            MIN(transaction_date) AS first_date,
            MAX(transaction_date) AS last_date
        FROM gemach_transactions
        GROUP BY category
        ORDER BY category
        """
    )).fetchall()

    cat_label = {
        'הלו': 'הלוואות', 'פקד': 'פקדונות', 'תרו': 'תרומות',
        'תמי': 'תמיכות', 'הוצ': 'הוצאות',
    }
    rows = []
    for r in results:
        rows.append({
            'category':   cat_label.get(r.category, r.category) if r.category else '(ללא)',
            'n':          r.n,
            'sum_ils':    r.sum_ils or 0,
            'sum_usd':    r.sum_usd or 0,
            'first_date': r.first_date,
            'last_date':  r.last_date,
        })

    # Also: active loans + cancelled loans + members
    extras = [
        {'category': 'חברים פעילים',    'n': GemachMember.query.count(),
         'sum_ils': '', 'sum_usd': '', 'first_date': '', 'last_date': ''},
        {'category': 'הו״ק פעילות',     'n': GemachLoan.query.filter_by(status='p').count(),
         'sum_ils': '', 'sum_usd': '', 'first_date': '', 'last_date': ''},
        {'category': 'הו״ק בוטלו',      'n': GemachCancelledLoan.query.count(),
         'sum_ils': '', 'sum_usd': '', 'first_date': '', 'last_date': ''},
        {'category': 'פעולות הו״ק',     'n': GemachLoanTransaction.query.count(),
         'sum_ils': '', 'sum_usd': '', 'first_date': '', 'last_date': ''},
    ]
    rows.extend(extras)

    spec = ReportSpec(
        title='סיכומי גמ״ח',
        subtitle='Gmach Lifetime Totals',
        columns=[
            Column('category',   'קטגוריה',     width=1.5),
            Column('n',          'מס׳ רשומות',  width=0.8, align='center'),
            Column('sum_ils',    'סה״כ ש״ח',    width=1.2, align='left'),
            Column('sum_usd',    'סה״כ $',      width=1.2, align='left'),
            Column('first_date', 'תאריך ראשון', width=1.0, align='center'),
            Column('last_date',  'תאריך אחרון', width=1.0, align='center'),
        ],
        rows=rows,
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# 7. Address Labels  (תוויות כתובת — mailing list)
# ---------------------------------------------------------------------------
@gemach_bp.route('/reports/addresses')
@gemach_required
def report_addresses():
    classification = request.args.get('classification', '')

    q = GemachMember.query.filter(
        GemachMember.address.isnot(None),
        GemachMember.address != '',
    )
    if classification:
        q = q.filter(or_(
            GemachMember.tag1 == classification,
            GemachMember.tag2 == classification,
            GemachMember.tag3 == classification,
        ))
    q = q.order_by(GemachMember.last_name, GemachMember.first_name)
    members = q.all()

    rows = []
    for m in members:
        name = f'{m.title or ""} {m.full_name}'.strip()
        rows.append({
            'card_no':  m.gmach_card_no,
            'name':     name,
            'address':  m.address or '',
            'city':     m.city or '',
            'zip':      m.zip_code or '',
            'phone':    m.primary_phone or '',
        })

    spec = ReportSpec(
        title='תוויות כתובת — רשימת דיוור',
        subtitle='Mailing List / Address Labels',
        columns=[
            Column('card_no', 'כרטיס',  width=0.6, align='center'),
            Column('name',    'שם',     width=2.0),
            Column('address', 'כתובת',  width=2.2),
            Column('city',    'עיר',    width=1.0),
            Column('zip',     'מיקוד',  width=0.8, align='center'),
            Column('phone',   'טלפון',  width=1.0, align='center'),
        ],
        rows=rows,
        filters={'סיווג': classification or 'הכל'},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# 8. Masav Totals  (סיכומי מס״ב)
# ---------------------------------------------------------------------------
@gemach_bp.route('/reports/msv_totals')
@gemach_required
def report_msv_totals():
    """List Masav batches generated + per-batch totals.

    Reads from instance/masav_batches/*.json (one ticket per batch).
    """
    batches_dir = os.path.join(current_app.instance_path, 'masav_batches')
    rows = []
    tot_amount = Decimal('0')
    if os.path.isdir(batches_dir):
        for fn in sorted(os.listdir(batches_dir)):
            if not fn.endswith('.json'):
                continue
            path = os.path.join(batches_dir, fn)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
            except Exception:
                continue
            rows.append({
                'batch_id':     meta.get('batch_id') or fn.replace('.json', ''),
                'created_at':   meta.get('created_at'),
                'loan_count':   meta.get('loan_count', 0),
                'total_amount': Decimal(str(meta.get('total_amount', 0))),
                'status':       meta.get('status', 'draft'),
                'file_name':    meta.get('file_name', ''),
            })
            tot_amount += Decimal(str(meta.get('total_amount', 0)))

    spec = ReportSpec(
        title='סיכומי מס״ב',
        subtitle='Masav (direct debit) Batch Summary',
        columns=[
            Column('batch_id',     'מס׳ אצווה',   width=1.2, align='center'),
            Column('created_at',   'תאריך',       width=1.2, align='center'),
            Column('loan_count',   'הו״ק',        width=0.6, align='center'),
            Column('total_amount', 'סה״כ ש״ח',    width=1.2, align='left'),
            Column('status',       'סטטוס',       width=0.8, align='center'),
            Column('file_name',    'שם קובץ',     width=2.0),
        ],
        rows=rows,
        totals={'total_amount': tot_amount},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# Masav Collection  (direct-debit batch preparation)
# ---------------------------------------------------------------------------
@gemach_bp.route('/masav', methods=['GET', 'POST'])
@gemach_required
def masav_prep():
    """Prepare a Masav batch: select due loans, preview, generate file.

    In SANDBOX_MODE the file is written to instance/masav_batches/ but NEVER
    transmitted to the bank. The operator sees the exact file she would have
    sent.
    """
    # Pick active loans whose charge_day falls in the next 30 days.
    due_loans = GemachLoan.query.filter_by(status='p').order_by(
        GemachLoan.charge_day.nullslast()).limit(500).all()

    if request.method == 'POST':
        # Build the batch
        selected_ids = request.form.getlist('loan_id', type=int)
        loans = [l for l in due_loans if l.id in selected_ids] if selected_ids else due_loans
        import uuid
        batch_id = f'MSV-{datetime.utcnow():%Y%m%d%H%M%S}'
        total_amount = sum((Decimal(str(l.amount or 0)) for l in loans), Decimal('0'))

        batches_dir = os.path.join(current_app.instance_path, 'masav_batches')
        os.makedirs(batches_dir, exist_ok=True)

        # Write the Masav fixed-width file (standard Israeli bank format:
        # 70-char lines). This is a simplified approximation of the real
        # spec — the operator can still verify the structure is right.
        txt_path = os.path.join(batches_dir, f'{batch_id}.msv')
        with open(txt_path, 'w', encoding='ascii', errors='replace') as f:
            # Header line (type code '1' for header)
            f.write(f'1{batch_id:<20}{datetime.utcnow():%Y%m%d}'
                    f'{len(loans):08d}{int(total_amount * 100):012d}\n')
            # Detail lines
            for l in loans:
                bank = str(l.bank_code or 0).zfill(2)
                branch = str(l.branch_code or 0).zfill(3)
                account = str(l.account_number or 0).zfill(9)
                amount = int(Decimal(str(l.amount or 0)) * 100)
                f.write(f'2{bank}{branch}{account}{amount:012d}'
                        f'{l.gmach_num_hork or 0:08d}\n')
            # Trailer
            f.write(f'9{len(loans):08d}{int(total_amount * 100):012d}\n')

        # Write metadata sidecar (picked up by report_msv_totals)
        meta = {
            'batch_id':     batch_id,
            'created_at':   datetime.utcnow().isoformat(),
            'loan_count':   len(loans),
            'total_amount': str(total_amount),
            'status':       'generated-sandbox' if is_sandbox() else 'generated',
            'file_name':    f'{batch_id}.msv',
            'submitted':    False,
            'loan_ids':     [l.id for l in loans],
        }
        with open(os.path.join(batches_dir, f'{batch_id}.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        if is_sandbox():
            flash(f'[SANDBOX] אצווה {batch_id} נוצרה בהצלחה — {len(loans)} הו״ק, סה״כ ₪{total_amount:,.2f}. '
                  f'לא נשלחה לבנק (מצב הדגמה).', 'success')
        else:
            flash(f'אצווה {batch_id} נוצרה בהצלחה — {len(loans)} הו״ק, סה״כ ₪{total_amount:,.2f}.', 'success')
        return redirect(url_for('gemach.report_msv_totals'))

    return render_template('gemach/masav_prep.html',
                           loans=due_loans, sandbox=is_sandbox())


# ---------------------------------------------------------------------------
# Hash Export  (accounting integration)
# ---------------------------------------------------------------------------
@gemach_bp.route('/hash', methods=['GET', 'POST'])
@gemach_required
def hash_export():
    """Generate accounting export (CSV/fixed-width for her bookkeeping).

    In SANDBOX_MODE the file is written to instance/hash_exports/ but never
    uploaded to the external accounting system.
    """
    date_from = _parse_date(request.args.get('date_from')) or date.today().replace(day=1)
    date_to   = _parse_date(request.args.get('date_to')) or date.today()

    txns = GemachTransaction.query.filter(
        GemachTransaction.transaction_date >= date_from,
        GemachTransaction.transaction_date <= date_to,
    ).order_by(GemachTransaction.transaction_date).all()

    if request.method == 'POST':
        exports_dir = os.path.join(current_app.instance_path, 'hash_exports')
        os.makedirs(exports_dir, exist_ok=True)
        export_id = f'HASH-{datetime.utcnow():%Y%m%d%H%M%S}'

        # Write a simple CSV — one row per transaction
        import csv
        csv_path = os.path.join(exports_dir, f'{export_id}.csv')
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['date', 'category', 'member', 'card_no',
                        'amount_ils', 'amount_usd', 'description', 'method'])
            for t in txns:
                w.writerow([
                    t.transaction_date.isoformat() if t.transaction_date else '',
                    t.category or '',
                    t.member.full_name if t.member else '',
                    t.member.gmach_card_no if t.member else '',
                    t.amount_ils or 0,
                    t.amount_usd or 0,
                    t.description or '',
                    t.payment_method or '',
                ])

        meta = {
            'export_id':    export_id,
            'created_at':   datetime.utcnow().isoformat(),
            'date_from':    date_from.isoformat(),
            'date_to':      date_to.isoformat(),
            'row_count':    len(txns),
            'status':       'generated-sandbox' if is_sandbox() else 'generated',
            'file_name':    f'{export_id}.csv',
        }
        with open(os.path.join(exports_dir, f'{export_id}.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        if is_sandbox():
            flash(f'[SANDBOX] ייצוא {export_id} נוצר בהצלחה — {len(txns)} תנועות. '
                  f'לא הועלה לתוכנת חשבונאות (מצב הדגמה).', 'success')
        else:
            flash(f'ייצוא {export_id} נוצר בהצלחה — {len(txns)} תנועות.', 'success')
        return redirect(url_for('gemach.hash_export'))

    return render_template('gemach/hash_export.html',
                           txns=txns, date_from=date_from, date_to=date_to,
                           sandbox=is_sandbox())
