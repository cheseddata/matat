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
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'name')

    q = GemachMember.query
    if search:
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
    return render_template('gemach/members.html', members=paged, search=search, sort=sort)


@gemach_bp.route('/members/<int:member_id>')
@gemach_required
def member_detail(member_id):
    member = GemachMember.query.get_or_404(member_id)
    tab = request.args.get('tab', 'overview')

    loans = member.loans.order_by(GemachLoan.created_at.desc()).all()
    transactions = list(reversed(
        member.transactions.order_by(GemachTransaction.transaction_date.desc()).limit(100).all()
    ))
    memorials = member.memorials.all()

    # Linked Donor (if any)
    linked_donor = member.donor

    return render_template('gemach/member_detail.html',
                           member=member, tab=tab,
                           loans=loans, transactions=transactions,
                           memorials=memorials, linked_donor=linked_donor)


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
    q = q.order_by(GemachLoan.start_date.desc().nullslast())

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
