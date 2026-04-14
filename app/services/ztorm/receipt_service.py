"""
Receipt generation service - ported from ZTorm VBA Module_Kabalot.
Handles: create, cancel, fix, sequential numbering, PDF generation.
"""
import os
from datetime import date, datetime
from decimal import Decimal
from ...extensions import db
from ...models import Receipt, ReceiptCounter, Donation, Donor, Payment, Communication


def get_next_receipt_number(org_prefix='MM', fiscal_year=None):
    """Get next sequential receipt number atomically.
    Ported from VBA KabalotOld.GetKabalotRange.
    """
    if not fiscal_year:
        fiscal_year = date.today().year

    counter = ReceiptCounter.query.filter_by(
        org_prefix=org_prefix, fiscal_year=fiscal_year
    ).with_for_update().first()

    if not counter:
        counter = ReceiptCounter(
            org_prefix=org_prefix, fiscal_year=fiscal_year, last_sequence=0
        )
        db.session.add(counter)

    counter.last_sequence += 1
    db.session.add(counter)
    db.session.flush()

    return f"{org_prefix}-{fiscal_year}-{counter.last_sequence:05d}"


def create_receipt(donation_id, user=None):
    """Create a receipt for a donation.
    Ported from VBA Kabalot.PrepKabalot + UpdateKabalot.
    """
    donation = Donation.query.get(donation_id)
    if not donation:
        raise ValueError("Donation not found")

    donor = Donor.query.get(donation.donor_id)
    if not donor:
        raise ValueError("Donor not found")

    # Check if receipt already exists
    existing = Receipt.query.filter_by(donation_id=donation_id, is_cancelled=False).first()
    if existing:
        raise ValueError(f"Receipt already exists: {existing.receipt_number}")

    # Get receipt name and TZ
    name = donation.receipt_name or donor.receipt_name or donor.full_name
    tz = donation.receipt_tz or donor.receipt_tz or donor.teudat_zehut

    # Validate TZ if required
    if not donor.receipt_tz_not_required and not tz:
        raise ValueError("Donor TZ (Israeli ID) required for receipt")

    # Calculate total from paid payments
    payments = Payment.query.filter(
        Payment.donation_id == donation_id,
        Payment.status.in_(['ok', 'paid']),
        Payment.receipt_id.is_(None)
    ).all()

    if not payments:
        raise ValueError("No eligible payments for receipt")

    total_amount = sum(Decimal(str(p.amount or 0)) for p in payments)
    amount_cents = int(total_amount * 100)

    # Generate receipt number
    receipt_number = get_next_receipt_number()

    receipt = Receipt(
        donation_id=donation_id,
        donor_id=donor.id,
        receipt_number=receipt_number,
        receipt_type=donation.payment_method,
        receipt_date=date.today(),
        amount=amount_cents,
        currency=donation.currency or 'ILS',
        recipient_name=name,
        recipient_tz=str(tz) if tz else None,
        department_id=donation.department_id,
    )
    db.session.add(receipt)
    db.session.flush()

    # Link payments to receipt
    for p in payments:
        p.receipt_id = receipt.id
        db.session.add(p)

    # Update donation
    donation.receipt_number = receipt_number
    db.session.add(donation)

    # Log communication
    comm = Communication(
        donor_id=donor.id,
        donation_id=donation_id,
        receipt_id=receipt.id,
        comm_type='kabala',
        status='created',
        registration_date=date.today(),
    )
    db.session.add(comm)

    return receipt


def cancel_receipt(receipt_id, reason=None, user=None):
    """Cancel a receipt - creates mirror negative receipt.
    Ported from VBA Kabalot.CancelKabala.
    """
    receipt = Receipt.query.get(receipt_id)
    if not receipt:
        raise ValueError("Receipt not found")

    if receipt.is_cancelled:
        raise ValueError("Receipt already cancelled")

    # Mark original as cancelled
    receipt.is_cancelled = True
    db.session.add(receipt)

    # Create cancellation receipt (negative amount)
    cancel_number = get_next_receipt_number()
    cancel_receipt = Receipt(
        donation_id=receipt.donation_id,
        donor_id=receipt.donor_id,
        receipt_number=cancel_number,
        receipt_type=receipt.receipt_type,
        receipt_date=date.today(),
        amount=-receipt.amount,  # Negative
        currency=receipt.currency,
        recipient_name=receipt.recipient_name,
        recipient_tz=receipt.recipient_tz,
        cancel_receipt_id=receipt.id,
        notes=f"Cancellation of {receipt.receipt_number}: {reason or ''}",
        department_id=receipt.department_id,
    )
    db.session.add(cancel_receipt)

    # Unlink payments from original receipt
    payments = Payment.query.filter_by(receipt_id=receipt.id).all()
    for p in payments:
        p.receipt_id = None
        db.session.add(p)

    return cancel_receipt


def fix_receipt(receipt_id, new_name=None, new_tz=None, user=None):
    """Fix/correct a receipt - creates new receipt linked to original.
    Ported from VBA Kabalot.FixKabala.
    """
    receipt = Receipt.query.get(receipt_id)
    if not receipt:
        raise ValueError("Receipt not found")

    # Cancel original
    cancel_receipt(receipt_id, reason='Fix/correction', user=user)

    # Create corrected receipt
    fix_number = get_next_receipt_number()
    fixed = Receipt(
        donation_id=receipt.donation_id,
        donor_id=receipt.donor_id,
        receipt_number=fix_number,
        receipt_type=receipt.receipt_type,
        receipt_date=date.today(),
        amount=receipt.amount,
        currency=receipt.currency,
        recipient_name=new_name or receipt.recipient_name,
        recipient_tz=new_tz or receipt.recipient_tz,
        notes=f"Correction of {receipt.receipt_number}",
        department_id=receipt.department_id,
    )
    db.session.add(fixed)

    # Relink payments to new receipt
    payments = Payment.query.filter(
        Payment.donation_id == receipt.donation_id,
        Payment.status.in_(['ok', 'paid']),
        Payment.receipt_id.is_(None)
    ).all()
    for p in payments:
        p.receipt_id = fixed.id
        db.session.add(p)

    return fixed


def generate_receipt_pdf(receipt_id):
    """Generate PDF for a receipt.
    Uses WeasyPrint for Hebrew RTL support.
    """
    receipt = Receipt.query.get(receipt_id)
    if not receipt:
        return None

    donor = Donor.query.get(receipt.donor_id)
    donation = Donation.query.get(receipt.donation_id)

    # Build HTML for receipt
    amount_display = abs(receipt.amount) / 100
    currency_symbol = {'ILS': '₪', 'USD': '$', 'EUR': '€'}.get(
        (receipt.currency or 'ILS').upper(), '₪')

    is_cancellation = receipt.amount < 0

    html = f"""
    <html dir="rtl">
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; direction: rtl; padding: 40px; }}
            .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; }}
            .header h1 {{ color: #2F5597; margin: 0; }}
            .receipt-num {{ font-size: 18px; color: #666; }}
            .details {{ margin: 20px 0; }}
            .details td {{ padding: 4px 12px; font-size: 14px; }}
            .amount {{ font-size: 24px; font-weight: bold; color: #2F5597; text-align: center; margin: 20px 0; }}
            .footer {{ border-top: 1px solid #ccc; padding-top: 10px; font-size: 11px; color: #888; text-align: center; }}
            {''.join('.cancellation { color: red; }' if is_cancellation else '')}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>מתת מרדכי</h1>
            <p>קבלה על תרומה</p>
            <p class="receipt-num">מספר קבלה: {receipt.receipt_number}</p>
        </div>
        <table class="details">
            <tr><td>תאריך:</td><td>{receipt.receipt_date.strftime('%d/%m/%Y') if receipt.receipt_date else ''}</td></tr>
            <tr><td>שם:</td><td><strong>{receipt.recipient_name or ''}</strong></td></tr>
            <tr><td>ת.ז.:</td><td>{receipt.recipient_tz or ''}</td></tr>
            <tr><td>סוג תרומה:</td><td>{receipt.receipt_type or ''}</td></tr>
        </table>
        <div class="amount {'cancellation' if is_cancellation else ''}">
            {'ביטול - ' if is_cancellation else ''}סכום: {currency_symbol}{amount_display:,.2f}
        </div>
        <div class="footer">
            <p>תודה על תרומתכם!</p>
            <p>קבלה זו מהווה אישור לצורכי מס בהתאם לסעיף 46 לפקודת מס הכנסה</p>
        </div>
    </body>
    </html>
    """

    # Save PDF path
    receipts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'receipts')
    os.makedirs(receipts_dir, exist_ok=True)
    pdf_path = os.path.join(receipts_dir, f'{receipt.receipt_number}.pdf')

    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(pdf_path)
        receipt.pdf_path = pdf_path
        db.session.add(receipt)
        return pdf_path
    except ImportError:
        # WeasyPrint not installed - save HTML instead
        html_path = pdf_path.replace('.pdf', '.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        receipt.pdf_path = html_path
        db.session.add(receipt)
        return html_path


def batch_prepare_receipts(batch_id=None, donation_ids=None):
    """Prepare receipts for a batch of donations.
    Ported from VBA Kabalot.PrepKabalot.
    """
    results = {'created': [], 'errors': [], 'skipped': []}

    if donation_ids:
        donations = Donation.query.filter(Donation.id.in_(donation_ids)).all()
    elif batch_id:
        # Find donations from collection batch
        payment_ids = db.session.query(Payment.donation_id).filter_by(
            batch_id=batch_id
        ).distinct().all()
        donation_ids = [p[0] for p in payment_ids]
        donations = Donation.query.filter(Donation.id.in_(donation_ids)).all()
    else:
        # Find all donations with unreceipted paid payments
        donation_ids = db.session.query(Payment.donation_id).filter(
            Payment.status.in_(['ok', 'paid']),
            Payment.receipt_id.is_(None)
        ).distinct().all()
        donation_ids = [d[0] for d in donation_ids]
        donations = Donation.query.filter(Donation.id.in_(donation_ids)).all()

    for donation in donations:
        try:
            receipt = create_receipt(donation.id)
            results['created'].append({
                'donation_id': donation.id,
                'receipt_number': receipt.receipt_number,
                'amount': receipt.amount / 100,
            })
        except ValueError as e:
            error_msg = str(e)
            if 'already exists' in error_msg:
                results['skipped'].append({'donation_id': donation.id, 'reason': error_msg})
            else:
                results['errors'].append({'donation_id': donation.id, 'error': error_msg})

    return results
