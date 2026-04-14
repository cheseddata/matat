"""
Accounting service - ported from ZTorm VBA Module_Zicuim.
Handles: account allocations, credit/debit entries, journal entries.
"""
from datetime import date
from decimal import Decimal
from ...extensions import db
from ...models import Account, AccountAllocation, AccountingCredit, Payment


def create_allocation(donation_id, account_id, percentage, user=None):
    """Create an account allocation rule for a donation.
    Ported from VBA Zacaim creation logic.
    """
    allocation = AccountAllocation(
        donation_id=donation_id,
        account_id=account_id,
        percentage=Decimal(str(percentage)),
        is_active=True,
        entry_date=date.today(),
    )
    db.session.add(allocation)
    return allocation


def process_payment_credits(payment_id, user=None):
    """Generate accounting credit entries for a payment based on allocation rules.
    Ported from VBA Zicuim credit generation.
    """
    payment = Payment.query.get(payment_id)
    if not payment:
        return []

    # Get allocation rules for this donation
    allocations = AccountAllocation.query.filter_by(
        donation_id=payment.donation_id, is_active=True
    ).all()

    if not allocations:
        return []

    credits_created = []
    amount = Decimal(str(payment.amount or 0))

    for alloc in allocations:
        pct = Decimal(str(alloc.percentage or 0))
        credit_amount = (amount * pct / 100).quantize(Decimal('0.01'))

        if credit_amount == 0:
            continue

        credit = AccountingCredit(
            account_id=alloc.account_id,
            payment_id=payment_id,
            donation_id=payment.donation_id,
            entry_date=payment.payment_date or date.today(),
            value_date=payment.value_date or date.today(),
            amount=float(credit_amount),
            currency=payment.currency or 'ILS',
            entry_type='zicui',
            user=user,
        )
        db.session.add(credit)
        credits_created.append(credit)

    return credits_created


def get_account_balance(account_id, from_date=None, to_date=None):
    """Get account balance for a period."""
    query = AccountingCredit.query.filter_by(account_id=account_id)
    if from_date:
        query = query.filter(AccountingCredit.entry_date >= from_date)
    if to_date:
        query = query.filter(AccountingCredit.entry_date <= to_date)

    total = db.session.query(db.func.sum(AccountingCredit.amount)).filter(
        AccountingCredit.account_id == account_id
    )
    if from_date:
        total = total.filter(AccountingCredit.entry_date >= from_date)
    if to_date:
        total = total.filter(AccountingCredit.entry_date <= to_date)

    return float(total.scalar() or 0)


def get_account_statement(account_id, from_date=None, to_date=None):
    """Get account statement with running balance."""
    query = AccountingCredit.query.filter_by(account_id=account_id)
    if from_date:
        query = query.filter(AccountingCredit.entry_date >= from_date)
    if to_date:
        query = query.filter(AccountingCredit.entry_date <= to_date)

    entries = query.order_by(AccountingCredit.entry_date).all()

    running_balance = Decimal('0')
    statement = []
    for entry in entries:
        running_balance += Decimal(str(entry.amount))
        statement.append({
            'date': entry.entry_date,
            'amount': entry.amount,
            'balance': float(running_balance),
            'type': entry.entry_type,
            'details': entry.details,
        })

    return statement
