"""
Payment management service - ported from ZTorm VBA.
Handles: add, edit, delete, move, returns (hazarot), recalculation.
"""
from datetime import date, datetime
from decimal import Decimal
from ...extensions import db
from ...models import Payment, Donation, DonationEvent
from .donation_service import recalculate_donation, recalculate_agreement, log_donation_event


def add_payment(donation_id, amount, currency='ILS', method='cash',
                payment_date=None, value_date=None, check_bank=None,
                check_branch=None, check_account=None, check_number=None,
                reference=None, notes=None, user=None):
    """Add a new payment to a donation.
    Ported from VBA Form_Tashlum New.
    """
    donation = Donation.query.get(donation_id)
    if not donation:
        raise ValueError("Donation not found")

    if not payment_date:
        payment_date = date.today()
    if not value_date:
        value_date = payment_date

    # Determine status based on date
    status = 'ok'
    if method == 'check' and payment_date > date.today():
        status = 'ready'  # Future-dated check

    payment = Payment(
        donation_id=donation_id,
        amount=Decimal(str(amount)),
        currency=currency.upper(),
        payment_date=payment_date,
        value_date=value_date,
        status=status,
        method=method,
        reference=reference,
        notes=notes,
        check_bank=check_bank,
        check_branch=check_branch,
        check_account=check_account,
        check_number=check_number,
    )

    # Calculate NIS equivalent
    if currency.upper() == 'ILS':
        payment.amount_nis = payment.amount
    elif currency.upper() == 'USD':
        payment.usd_equivalent = payment.amount
        # TODO: Get exchange rate from Shearim table
        payment.amount_nis = payment.amount * Decimal('3.6')  # Approximate

    db.session.add(payment)
    db.session.flush()

    # Recalculate
    recalculate_donation(donation_id)
    if donation.agreement_id:
        recalculate_agreement(donation.agreement_id)

    log_donation_event(donation_id, 'payment_added',
                       new_value=f'{currency} {amount}', user=user)

    return payment


def edit_payment(payment_id, amount=None, currency=None, payment_date=None,
                 value_date=None, status=None, method=None, notes=None, user=None):
    """Edit an existing payment.
    Ported from VBA Form_Tashlum Edit.
    """
    payment = Payment.query.get(payment_id)
    if not payment:
        raise ValueError("Payment not found")

    old_amount = payment.amount

    if amount is not None:
        payment.amount = Decimal(str(amount))
    if currency is not None:
        payment.currency = currency.upper()
    if payment_date is not None:
        payment.payment_date = payment_date
    if value_date is not None:
        payment.value_date = value_date
    if status is not None:
        old_status = payment.status
        payment.status = status
        if old_status != status:
            log_donation_event(payment.donation_id, 'payment_status_change',
                               old_value=old_status, new_value=status, user=user)
    if method is not None:
        payment.method = method
    if notes is not None:
        payment.notes = notes

    # Recalculate NIS
    if payment.currency == 'ILS':
        payment.amount_nis = payment.amount
    elif payment.currency == 'USD':
        payment.usd_equivalent = payment.amount

    db.session.add(payment)
    recalculate_donation(payment.donation_id)

    donation = Donation.query.get(payment.donation_id)
    if donation and donation.agreement_id:
        recalculate_agreement(donation.agreement_id)

    return payment


def delete_payment(payment_id, user=None):
    """Delete a payment.
    Ported from VBA Form_Tashlumim delete logic.
    """
    payment = Payment.query.get(payment_id)
    if not payment:
        raise ValueError("Payment not found")

    # Check if payment has a receipt
    if payment.receipt_id:
        raise ValueError("Cannot delete payment with an existing receipt")

    donation_id = payment.donation_id
    donation = Donation.query.get(donation_id)

    log_donation_event(donation_id, 'payment_deleted',
                       old_value=f'{payment.currency} {payment.amount}', user=user)

    db.session.delete(payment)
    recalculate_donation(donation_id)

    if donation and donation.agreement_id:
        recalculate_agreement(donation.agreement_id)


def process_return(payment_id, reason=None, reason_code=None, user=None):
    """Process a bank return (hazara).
    Ported from VBA Hork.MakeHazara.
    """
    payment = Payment.query.get(payment_id)
    if not payment:
        raise ValueError("Payment not found")

    old_status = payment.status
    payment.status = 'returned'
    payment.reason = reason

    # For unlimited standing orders, generate replacement future payment
    donation = Donation.query.get(payment.donation_id)
    if donation and donation.payment_method == 'hork':
        so = donation.standing_order
        if so and so.total_payments is None:
            # Unlimited - add replacement payment
            new_payment = Payment(
                donation_id=donation.id,
                amount=payment.amount,
                currency=payment.currency,
                payment_date=_add_months(payment.payment_date, 1),
                value_date=_add_months(payment.value_date, 1),
                status='ready',
                method='hork',
            )
            db.session.add(new_payment)
        elif so and so.total_payments:
            # Limited - decrement count
            so.current_count = max(0, (so.current_count or 0) - 1)

    log_donation_event(payment.donation_id, 'payment_returned',
                       old_value=old_status, new_value='returned',
                       description=reason, user=user)

    db.session.add(payment)
    recalculate_donation(payment.donation_id)

    return payment


def undo_return(payment_id, user=None):
    """Undo a bank return (reverse hazara).
    Ported from VBA Hork.UndoHazara.
    """
    payment = Payment.query.get(payment_id)
    if not payment or payment.status != 'returned':
        raise ValueError("Payment not found or not returned")

    payment.status = 'ok'
    payment.reason = None

    log_donation_event(payment.donation_id, 'return_undone', user=user)

    db.session.add(payment)
    recalculate_donation(payment.donation_id)

    return payment


def move_payment(payment_id, target_donation_id, user=None):
    """Move a payment to a different donation.
    Ported from VBA Form_Tashlum Transfer.
    """
    payment = Payment.query.get(payment_id)
    if not payment:
        raise ValueError("Payment not found")

    old_donation_id = payment.donation_id
    payment.donation_id = target_donation_id

    log_donation_event(old_donation_id, 'payment_moved_out',
                       new_value=str(target_donation_id), user=user)
    log_donation_event(target_donation_id, 'payment_moved_in',
                       old_value=str(old_donation_id), user=user)

    db.session.add(payment)
    recalculate_donation(old_donation_id)
    recalculate_donation(target_donation_id)

    # Recalculate agreements
    old_donation = Donation.query.get(old_donation_id)
    new_donation = Donation.query.get(target_donation_id)
    if old_donation and old_donation.agreement_id:
        recalculate_agreement(old_donation.agreement_id)
    if new_donation and new_donation.agreement_id:
        recalculate_agreement(new_donation.agreement_id)

    return payment


def _add_months(d, months):
    """Add months to a date."""
    if not d:
        return date.today()
    import calendar
    month = d.month + months
    year = d.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
