"""
Donation lifecycle service - ported from ZTorm VBA Module_Trumot.
Handles: create, activate, cancel, complete, recalculate, delete.
"""
from datetime import date, timedelta
from decimal import Decimal
from ...extensions import db
from ...models import (
    Donation, Payment, Agreement, DonationEvent,
    StandingOrder, CreditCardRecurring
)


def recalculate_donation(donation_id):
    """Recalculate donation summary fields from payment records.
    Ported from VBA Trumot.RecalcTruma.
    """
    donation = Donation.query.get(donation_id)
    if not donation:
        return

    payments = Payment.query.filter_by(donation_id=donation_id).all()

    paid_nis = Decimal('0')
    paid_usd = Decimal('0')
    expected_nis = Decimal('0')
    expected_usd = Decimal('0')
    first_date = None
    last_date = None
    last_paid = None

    for p in payments:
        amt = Decimal(str(p.amount or 0))
        currency = (p.currency or 'ILS').upper()

        if p.status in ('ok', 'paid'):
            if currency == 'ILS':
                paid_nis += amt
            elif currency == 'USD':
                paid_usd += amt
            if p.payment_date:
                if not last_paid or p.payment_date > last_paid:
                    last_paid = p.payment_date
        elif p.status == 'ready':
            if currency == 'ILS':
                expected_nis += amt
            elif currency == 'USD':
                expected_usd += amt

        if p.payment_date or p.value_date:
            d = p.payment_date or p.value_date
            if not first_date or d < first_date:
                first_date = d
            if not last_date or d > last_date:
                last_date = d

    donation.paid_nis = float(paid_nis)
    donation.paid_usd = float(paid_usd)
    donation.expected_nis = float(expected_nis)
    donation.expected_usd = float(expected_usd)
    donation.first_payment_date = first_date
    donation.last_payment_date = last_date
    donation.last_paid_date = last_paid

    # Update amount in cents
    if donation.currency == 'ILS':
        donation.amount = int(paid_nis * 100)
    elif donation.currency == 'USD':
        donation.amount = int(paid_usd * 100)

    db.session.add(donation)
    return donation


def recalculate_agreement(agreement_id):
    """Recalculate agreement totals from linked donations.
    Ported from VBA Trumot.RecalcHescem.
    """
    agreement = Agreement.query.get(agreement_id)
    if not agreement:
        return

    paid = Decimal('0')
    expected = Decimal('0')

    for d in agreement.donations.filter(Donation.deleted_at.is_(None)):
        paid += Decimal(str(d.paid_nis or 0))
        expected += Decimal(str(d.expected_nis or 0))

    agreement.paid_amount = float(paid)
    agreement.expected_amount = float(expected)
    db.session.add(agreement)
    return agreement


def activate_donation(donation_id, start_date=None, user=None):
    """Activate a donation - generate payment schedule.
    Ported from VBA Trumot.MakePeulotHorkAshp / MakePeulotCredit.
    """
    donation = Donation.query.get(donation_id)
    if not donation:
        raise ValueError("Donation not found")

    if donation.status not in ('new', 'pending'):
        raise ValueError(f"Cannot activate donation with status '{donation.status}'")

    if not start_date:
        start_date = date.today()

    donation.status = 'active'
    donation.entry_date = date.today()

    # Generate payment schedule based on method
    method = donation.payment_method or 'cash'
    num_payments = 12  # Default: 12 months ahead

    if method in ('hork', 'credit', 'ashp'):
        so = donation.standing_order or donation.credit_card_recurring
        if so:
            if so.total_payments:
                num_payments = so.total_payments
            collection_day = so.collection_day or 1
            amount = float(so.amount or donation.amount_display)
        else:
            collection_day = 1
            amount = donation.amount_display

        # Generate future payments
        for i in range(num_payments):
            month_offset = i
            pay_date = _next_collection_date(start_date, collection_day, month_offset)

            payment = Payment(
                donation_id=donation_id,
                amount=amount,
                currency=donation.currency,
                payment_date=pay_date,
                value_date=pay_date,
                status='ready',
                method=method,
            )
            db.session.add(payment)

    # Log event
    log_donation_event(donation_id, 'activation',
                       old_value='new', new_value='active', user=user)

    db.session.add(donation)
    recalculate_donation(donation_id)

    if donation.agreement_id:
        recalculate_agreement(donation.agreement_id)

    return donation


def cancel_donation(donation_id, reason=None, reason_code=None, user=None):
    """Cancel a donation.
    Ported from VBA Trumot.BitulTruma.
    """
    donation = Donation.query.get(donation_id)
    if not donation:
        raise ValueError("Donation not found")

    old_status = donation.status
    donation.status = 'cancelled'
    donation.cancellation_date = date.today()
    donation.cancellation_reason = reason
    donation.cancellation_code = reason_code

    # Delete future (ready) payments
    future_payments = Payment.query.filter_by(
        donation_id=donation_id, status='ready'
    ).all()
    for p in future_payments:
        db.session.delete(p)

    # Log event
    log_donation_event(donation_id, 'cancellation',
                       old_value=old_status, new_value='cancelled',
                       user=user)

    db.session.add(donation)
    recalculate_donation(donation_id)

    if donation.agreement_id:
        recalculate_agreement(donation.agreement_id)

    return donation


def complete_donation(donation_id, user=None):
    """Mark donation as completed.
    Ported from VBA - status transition to 'siem'.
    """
    donation = Donation.query.get(donation_id)
    if not donation:
        raise ValueError("Donation not found")

    old_status = donation.status
    donation.status = 'completed'

    # Delete remaining ready payments
    Payment.query.filter_by(donation_id=donation_id, status='ready').delete()

    log_donation_event(donation_id, 'completion',
                       old_value=old_status, new_value='completed', user=user)

    db.session.add(donation)
    recalculate_donation(donation_id)

    if donation.agreement_id:
        recalculate_agreement(donation.agreement_id)

    return donation


def delete_donation(donation_id, user=None):
    """Soft-delete a donation (with safety checks).
    Ported from VBA Data.DeleteTruma + CanDeleteTruma.
    """
    donation = Donation.query.get(donation_id)
    if not donation:
        raise ValueError("Donation not found")

    # Check if can delete
    from ...models import Receipt
    has_receipts = Receipt.query.filter_by(donation_id=donation_id).count() > 0
    if has_receipts:
        raise ValueError("Cannot delete donation with existing receipts")

    has_paid_payments = Payment.query.filter(
        Payment.donation_id == donation_id,
        Payment.status.in_(['ok', 'paid'])
    ).count() > 0
    if has_paid_payments:
        raise ValueError("Cannot delete donation with paid payments")

    # Soft delete
    from datetime import datetime
    donation.deleted_at = datetime.utcnow()

    # Delete ready payments
    Payment.query.filter_by(donation_id=donation_id, status='ready').delete()

    log_donation_event(donation_id, 'deletion', user=user)

    db.session.add(donation)

    if donation.agreement_id:
        recalculate_agreement(donation.agreement_id)

    return donation


def log_donation_event(donation_id, event_type, old_value=None,
                       new_value=None, description=None, user=None):
    """Log a donation event for audit trail.
    Ported from VBA TrumotEruim inserts.
    """
    event = DonationEvent(
        donation_id=donation_id,
        event_type=event_type,
        event_date=date.today(),
        old_value=str(old_value) if old_value else None,
        new_value=str(new_value) if new_value else None,
        description=description,
        user=user,
    )
    db.session.add(event)
    return event


def _next_collection_date(start_date, day_of_month, months_ahead):
    """Calculate next collection date for a given day of month.
    Ported from VBA Hork.NextDateHiuv.
    """
    month = start_date.month + months_ahead
    year = start_date.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1

    # Clamp day to max days in month
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    day = min(day_of_month, max_day)

    return date(year, month, day)
