"""Gemach blueprint routes — charitable fund management.

All routes require the user to have role 'admin' or 'gemach_user'.
"""
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import current_user
from sqlalchemy import or_, func
from datetime import datetime

from ...extensions import db
from ...models import (
    GemachMember, GemachLoan, GemachLoanTransaction, GemachTransaction,
    GemachCancelledLoan, GemachInstitution, GemachCancellationReason,
    GemachTransactionType, GemachHashAccount, GemachMemorial,
    Donor,
)
from ...utils.decorators import gemach_required
from . import gemach_bp


# ============================================================
# Switchboard (Main Menu)
# ============================================================
@gemach_bp.route('/')
@gemach_required
def switchboard():
    stats = {
        'members': GemachMember.query.count(),
        'active_loans': GemachLoan.query.filter_by(status='p').count(),
        'cancelled_loans': GemachCancelledLoan.query.count(),
        'loan_transactions': GemachLoanTransaction.query.count(),
        'transactions': GemachTransaction.query.count(),
    }
    return render_template('gemach/switchboard.html', stats=stats)


# ============================================================
# Members (Haverim)
# ============================================================
@gemach_bp.route('/members')
@gemach_required
def members():
    """Access-style haverim search dialog.

    Supports three structured search fields (card# / first / last) AND
    the legacy ?q= free-text search (kept so saved links still work).
    """
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()      # legacy catch-all
    s_card = request.args.get('card', '').strip()
    s_first = request.args.get('first', '').strip()
    s_last = request.args.get('last', '').strip()
    sort = request.args.get('sort', 'name')

    q = GemachMember.query

    # Three-field search (Access-style)
    if s_card:
        if s_card.isdigit():
            q = q.filter(GemachMember.gmach_card_no == int(s_card))
        else:
            q = q.filter(GemachMember.gmach_card_no == -1)  # force 0 rows
    if s_first:
        q = q.filter(GemachMember.first_name.ilike(f'{s_first}%'))
    if s_last:
        q = q.filter(GemachMember.last_name.ilike(f'{s_last}%'))

    # Legacy free-text (phone / TZ / any name)
    if search and not (s_card or s_first or s_last):
        pat = f'{search}%'
        q = q.filter(or_(
            GemachMember.last_name.ilike(pat),
            GemachMember.first_name.ilike(pat),
            GemachMember.phone.ilike(f'%{search}%'),
            GemachMember.teudat_zehut.ilike(pat),
            GemachMember.gmach_card_no == (int(search) if search.isdigit() else -1),
        ))

    if sort == 'card_no':
        q = q.order_by(GemachMember.gmach_card_no)
    else:
        q = q.order_by(GemachMember.last_name, GemachMember.first_name)

    paged = q.paginate(page=page, per_page=50)

    # Interactive search: the page JS re-fetches this route with ?partial=1
    # and swaps in just the grid/pager block, so each keystroke feels live.
    if request.args.get('partial'):
        return render_template('gemach/_members_results.html',
                               members=paged,
                               s_card=s_card, s_first=s_first, s_last=s_last)

    return render_template('gemach/members.html',
                           members=paged, search=search, sort=sort,
                           s_card=s_card, s_first=s_first, s_last=s_last)


@gemach_bp.route('/members/<int:member_id>')
@gemach_required
def member_detail(member_id):
    member = GemachMember.query.get_or_404(member_id)
    tab = request.args.get('tab', '1')  # Access-style: 1/2/3/4/5

    # Tab 3 (הו״ק): loans grid
    loans = member.loans.order_by(GemachLoan.start_date.desc()).all()

    # Tab 4 (תנועות): general transactions, oldest first within the last 200
    transactions = list(reversed(
        member.transactions.order_by(GemachTransaction.transaction_date.desc()).limit(200).all()
    ))

    # Tab 5 (מעקב):
    #   RIGHT grid = general transactions for this member (deposits,
    #     donations, supports). Same source as tab 4 but summarized.
    #   LEFT grid  = loan payments (Peulot) for any of this member's loans.
    loan_payments = (
        GemachLoanTransaction.query
        .join(GemachLoan, GemachLoanTransaction.loan_id == GemachLoan.id)
        .filter(GemachLoan.member_id == member.id)
        .order_by(GemachLoanTransaction.transaction_date.desc())
        .limit(200).all()
    )

    # Totals by category for the bottom bar on tab 5.
    cat_totals = {'תמי': 0.0, 'תרו': 0.0, 'פקד': 0.0, 'הלו': 0.0}
    rows = db.session.query(
        GemachTransaction.category,
        func.sum(GemachTransaction.amount_ils),
    ).filter(
        GemachTransaction.member_id == member.id,
        GemachTransaction.category.in_(list(cat_totals.keys())),
    ).group_by(GemachTransaction.category).all()
    for cat, s in rows:
        cat_totals[cat] = float(s or 0)

    # Record navigator (previous / next by card_no, plus record #).
    total_members = GemachMember.query.count()
    # Compute 1-based ordinal by counting members with smaller card_no.
    record_number = GemachMember.query.filter(
        GemachMember.gmach_card_no < (member.gmach_card_no or 0)
    ).count() + 1
    prev_m = GemachMember.query.filter(
        GemachMember.gmach_card_no < (member.gmach_card_no or 0)
    ).order_by(GemachMember.gmach_card_no.desc()).first()
    next_m = GemachMember.query.filter(
        GemachMember.gmach_card_no > (member.gmach_card_no or 0)
    ).order_by(GemachMember.gmach_card_no.asc()).first()

    memorials = member.memorials.all()
    linked_donor = member.donor

    return render_template(
        'gemach/member_detail.html',
        member=member, tab=tab,
        loans=loans, transactions=transactions,
        loan_payments=loan_payments, cat_totals=cat_totals,
        memorials=memorials, linked_donor=linked_donor,
        record_number=record_number, total_members=total_members,
        prev_member_id=prev_m.id if prev_m else None,
        next_member_id=next_m.id if next_m else None,
    )


# ============================================================
# Loans (Hork)
# ============================================================
@gemach_bp.route('/loans')
@gemach_required
def loans():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    institution_id = request.args.get('institution_id', type=int)
    search = request.args.get('q', '').strip()

    # Explicit join on the borrower FK (member_id), since GemachLoan has TWO FKs
    # to GemachMember (member_id and beneficiary_member_id). The default join
    # raises AmbiguousForeignKeysError without this disambiguation.
    q = GemachLoan.query.join(GemachMember, GemachLoan.member_id == GemachMember.id)
    if status:
        q = q.filter(GemachLoan.status == status)
    if institution_id:
        q = q.filter(GemachLoan.institution_id == institution_id)
    if search:
        pat = f'%{search}%'
        digits = int(search) if search.isdigit() else -1
        q = q.filter(or_(
            GemachMember.last_name.ilike(pat),
            GemachMember.first_name.ilike(pat),
            GemachMember.teudat_zehut.ilike(pat),
            GemachMember.gmach_card_no == digits,
            GemachLoan.gmach_num_hork == digits,
            GemachLoan.account_number.ilike(pat),
        ))
    q = q.order_by(GemachLoan.start_date.desc())

    paged = q.paginate(page=page, per_page=50)
    institutions = GemachInstitution.query.order_by(GemachInstitution.name).all()
    return render_template('gemach/loans.html', loans=paged, status=status,
                           institution_id=institution_id, institutions=institutions,
                           search=search)


@gemach_bp.route('/loans/<int:loan_id>')
@gemach_required
def loan_detail(loan_id):
    loan = GemachLoan.query.get_or_404(loan_id)
    transactions = loan.transactions.order_by(GemachLoanTransaction.transaction_date.desc()).all()
    return render_template('gemach/loan_detail.html', loan=loan, transactions=transactions)


# ============================================================
# Transactions (Tnuot)
# ============================================================
@gemach_bp.route('/transactions')
@gemach_required
def transactions():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')

    # Same ambiguity as loans: GemachTransaction has two FKs to members
    # (member_id and beneficiary_member_id). Join on member_id explicitly.
    q = GemachTransaction.query.join(GemachMember, GemachTransaction.member_id == GemachMember.id)
    if category:
        q = q.filter(GemachTransaction.category == category)
    q = q.order_by(GemachTransaction.transaction_date.desc())

    paged = q.paginate(page=page, per_page=100)
    return render_template('gemach/transactions.html', transactions=paged, category=category)


# ============================================================
# Reports (stub — real reports require Peulot/Tnuot import)
# ============================================================
@gemach_bp.route('/reports')
@gemach_required
def reports():
    return render_template('gemach/reports.html')


# ============================================================
# Access-style submenus (תכניות / תחזוקה / עזרה)
# Mirror the original Access nested menu structure.
# ============================================================
@gemach_bp.route('/progs')
@gemach_required
def progs_menu():
    """תכניות — Programs submenu: Masav, Hash, Access-Sync."""
    return render_template('gemach/menu_progs.html')


@gemach_bp.route('/maint')
@gemach_required
def maint_menu():
    """תחזוקה — Maintenance submenu: institutions, lookup tables, users."""
    return render_template('gemach/menu_maint.html')


@gemach_bp.route('/help')
@gemach_required
def help_page():
    """עזרה — Help / about page."""
    return render_template('gemach/help.html')


# ============================================================
# API / AJAX
# ============================================================
@gemach_bp.route('/api/members/search')
@gemach_required
def api_member_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])

    pat = f'{q}%'
    results = GemachMember.query.filter(or_(
        GemachMember.last_name.ilike(pat),
        GemachMember.first_name.ilike(pat),
        GemachMember.phone.ilike(f'%{q}%'),
        GemachMember.teudat_zehut.ilike(pat),
    )).limit(20).all()

    return jsonify([{
        'id': m.id,
        'card_no': m.gmach_card_no,
        'name': m.full_name,
        'phone': m.primary_phone,
        'tz': m.teudat_zehut or '',
        'city': m.city or '',
    } for m in results])
