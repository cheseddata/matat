import os
import logging
from datetime import datetime
from sqlalchemy import text
from ..extensions import db
from ..models.receipt import Receipt, ReceiptCounter
from ..models.config_settings import ConfigSettings

logger = logging.getLogger(__name__)


def _amount_to_words(amount):
    """Render a dollar amount like 'One Hundred Twenty-Three Dollars and 45/100'.
    Used on the printed receipt's 'In Words' line.
    """
    try:
        from num2words import num2words
    except ImportError:
        # Fallback — no num2words installed; just show numeric string.
        return f"{amount:.2f} Dollars"

    try:
        whole = int(amount)
        cents = int(round((float(amount) - whole) * 100))
        words = num2words(whole, lang='en').title()
        unit = "Dollar" if whole == 1 else "Dollars"
        return f"{words} {unit} and {cents:02d}/100"
    except Exception:
        return f"{amount:.2f} Dollars"


def generate_receipt_number_atomic():
    """
    Generate atomic sequential receipt number using SELECT FOR UPDATE.

    This ensures no duplicate receipt numbers even under concurrent requests.
    The entire operation runs within a transaction with row-level locking.

    Pattern from Section 6: Atomic Receipt Counter Logic
    """
    config = ConfigSettings.query.first()
    org_prefix = config.org_prefix if config else 'MM'
    current_year = datetime.now().year

    # Use SELECT FOR UPDATE to lock the row during the transaction
    counter = ReceiptCounter.query.filter_by(
        org_prefix=org_prefix,
        fiscal_year=current_year
    ).with_for_update().first()

    if counter:
        counter.last_sequence += 1
        sequence = counter.last_sequence
    else:
        # First receipt of the year - create new counter
        # Use INSERT with ON DUPLICATE KEY for race condition safety
        counter = ReceiptCounter(
            org_prefix=org_prefix,
            fiscal_year=current_year,
            last_sequence=1
        )
        db.session.add(counter)
        sequence = 1

    # Flush to ensure sequence is assigned before generating number
    db.session.flush()

    receipt_number = f"{org_prefix}-{current_year}-{sequence:05d}"
    logger.info(f"Generated receipt number: {receipt_number}")

    return receipt_number


def generate_receipt_pdf(donation, donor, language='en'):
    """
    Generate receipt PDF using WeasyPrint.

    Supports English (LTR) and Hebrew (RTL) with the Assistant font.
    """
    try:
        from weasyprint import HTML
        from flask import render_template, current_app
    except ImportError as e:
        logger.error(f"WeasyPrint import failed: {e}")
        return None

    # Validate language
    if language not in ('en', 'he'):
        language = 'en'

    config = ConfigSettings.query.first()

    template_name = f'pdf/receipt_{language}.html'

    # Receipt date — bottom-of-page "issue date". This is when the
    # donation was first entered into our system (donation.created_at).
    # The actual *payment* date (check date, charge date, Zelle
    # transaction date) is shown separately in the transaction-details
    # table later in the template; do NOT mix the two — that would tell
    # the donor we issued the receipt on a date weeks before we actually
    # received their check.
    receipt_date = donation.created_at

    if language == 'he':
        date_str = receipt_date.strftime('%d/%m/%Y')   # DD/MM/YYYY
    else:
        date_str = receipt_date.strftime('%B %d, %Y')  # Month DD, YYYY

    # Amount in words (English only — Hebrew receipts also use English numerals here).
    amount_in_words = _amount_to_words(donation.amount_dollars)

    # Pull check / card details out of processor_metadata so the
    # template can render a dedicated transaction-details box and the
    # uploaded check / card-slip image (if any).
    meta = donation.processor_metadata or {}
    if isinstance(meta, str):
        import json
        try: meta = json.loads(meta)
        except Exception: meta = {}

    pay_label_date = meta.get('payment_date') or ''
    if pay_label_date and len(pay_label_date) >= 10 and pay_label_date[4] == '-':
        try:
            from datetime import datetime as _dt
            pay_label_date = _dt.strptime(pay_label_date[:10], '%Y-%m-%d').strftime('%b %d, %Y')
        except Exception:
            pass

    payment_processor = (donation.payment_processor or '').lower()
    is_card = payment_processor in ('card', 'manual_card', 'credit_card')

    # Checks / Zelle: the "number" column shows the check or reference number.
    # Cards: the "number" column shows the masked PAN or last-4 digits.
    if is_card:
        ref_number = (donation.payment_method_last4
                      or donation.processor_confirmation
                      or meta.get('reference')
                      or '')
        if ref_number and not ref_number.startswith('•'):
            ref_number = f'•••• {ref_number}' if len(ref_number) <= 6 else ref_number
        ref_label = 'Card Number'
    else:
        ref_number = donation.processor_confirmation or meta.get('reference') or ''
        ref_label = 'Check Number' if payment_processor == 'check' else 'Reference'

    image_path = meta.get('image_path') or None

    try:
        html_content = render_template(
            template_name,
            donation=donation,
            donor=donor,
            config=config,
            receipt_number=donation.receipt_number,
            date=date_str,
            amount=donation.amount_dollars,
            amount_in_words=amount_in_words,
            payment_processor=payment_processor,
            is_card_payment=is_card,
            tx_date=pay_label_date,
            tx_ref_number=ref_number,
            tx_ref_label=ref_label,
            tx_image_path=image_path,
            tax_id=config.tax_id if config else 'XX-XXXXXXX',
            org_name=config.org_name if config else 'Matat Mordechai'
        )

        # Generate PDF with base_url for font loading
        base_url = current_app.root_path
        pdf = HTML(string=html_content, base_url=base_url).write_pdf()

        return pdf

    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        return None


def store_receipt(pdf_bytes, receipt_number):
    """Store receipt PDF to disk in the receipts directory."""
    receipts_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'receipts'
    )
    os.makedirs(receipts_dir, exist_ok=True)

    # Sanitize receipt number for filename
    safe_name = receipt_number.replace('/', '-').replace('\\', '-')
    filename = f"{safe_name}.pdf"
    filepath = os.path.join(receipts_dir, filename)

    with open(filepath, 'wb') as f:
        f.write(pdf_bytes)

    logger.info(f"Receipt PDF stored: {filepath}")
    return filepath


def get_receipt_language(donor, donation=None):
    """
    Determine receipt language for the PDF.

    Currency is the strongest signal: USD donations MUST always be in
    English (for tax purposes), regardless of any other field. The donor's
    `country` is operator-typed and unreliable (we have seen 'USD',
    'United States of America', etc. saved into it).

    For non-USD donations we look at country first, then `language_pref`,
    then default to English.
    """
    # Currency override — USD is always English.
    if donation is not None:
        currency = (getattr(donation, 'currency', None) or '').upper()
        if currency == 'USD':
            return 'en'

    # US donations must always be in English
    if donor.country in ('US', 'USA', 'United States'):
        return 'en'

    # For other countries, use donor's language preference
    if donor.language_pref in ('en', 'he'):
        return donor.language_pref

    # Default to English
    return 'en'


def create_receipt_atomic(donation, donor, override_number=None):
    """
    Create a receipt record and generate PDF atomically.

    This function should be called within an existing transaction.
    Uses SELECT FOR UPDATE to ensure sequential receipt numbers.

    If ``override_number`` is supplied, that exact receipt number is used and
    the sequential counter is *not* incremented. Useful when an operator is
    backfilling a donation against an existing paper receipt or migrating
    from a legacy system. Caller is responsible for format validation; this
    function only enforces uniqueness.

    Returns:
        Receipt: The created receipt record, or None on failure
    """
    try:
        if override_number:
            override_number = override_number.strip()
            if Receipt.query.filter_by(receipt_number=override_number).first():
                raise ValueError(f'Receipt number {override_number} is already in use.')
            receipt_number = override_number
        else:
            # Generate receipt number atomically (within current transaction)
            receipt_number = generate_receipt_number_atomic()
        donation.receipt_number = receipt_number

        config = ConfigSettings.query.first()

        # Determine language - USD always English; otherwise donor.country / language_pref
        language = get_receipt_language(donor, donation=donation)

        # Generate PDF (outside of critical transaction section)
        pdf_bytes = generate_receipt_pdf(donation, donor, language)
        pdf_path = None
        if pdf_bytes:
            pdf_path = store_receipt(pdf_bytes, receipt_number)

        # Create receipt record
        receipt = Receipt(
            donation_id=donation.id,
            receipt_number=receipt_number,
            donor_id=donor.id,
            amount=donation.amount,
            tax_id_used=config.tax_id if config else None,
            pdf_path=pdf_path
        )
        db.session.add(receipt)

        # Flush to get receipt ID, but don't commit - let caller handle transaction
        db.session.flush()

        logger.info(f"Receipt created: {receipt_number} for donation {donation.id}")
        return receipt

    except Exception as e:
        logger.error(f"Receipt creation failed for donation {donation.id}: {e}")
        # Don't rollback here - let caller handle transaction
        raise


def create_receipt(donation, donor):
    """
    Create a receipt with its own transaction (for standalone calls).

    For webhook integration, use create_receipt_atomic within the existing transaction.
    """
    try:
        receipt = create_receipt_atomic(donation, donor)
        db.session.commit()
        return receipt
    except Exception as e:
        db.session.rollback()
        logger.error(f"Receipt transaction failed: {e}")
        return None


def get_receipt_by_number(receipt_number):
    """Lookup receipt by number."""
    return Receipt.query.filter_by(receipt_number=receipt_number).first()


def get_receipt_by_donation(donation_id):
    """Lookup receipt by donation ID."""
    return Receipt.query.filter_by(donation_id=donation_id).first()


def get_receipt_pdf_path(receipt_number):
    """Get the PDF path for a receipt if it exists on disk."""
    receipt = get_receipt_by_number(receipt_number)
    if receipt and receipt.pdf_path and os.path.exists(receipt.pdf_path):
        return receipt.pdf_path
    return None


def regenerate_receipt_pdf(receipt):
    """
    Regenerate the PDF for an existing receipt.

    Useful for reissuing receipts with updated templates.
    """
    from ..models.donation import Donation
    from ..models.donor import Donor

    donation = Donation.query.get(receipt.donation_id)
    donor = Donor.query.get(receipt.donor_id)

    if not donation or not donor:
        logger.error(f"Cannot regenerate receipt {receipt.receipt_number}: missing donation or donor")
        return None

    # USD donations always English; otherwise donor.country / language_pref
    language = get_receipt_language(donor, donation=donation)
    pdf_bytes = generate_receipt_pdf(donation, donor, language)

    if pdf_bytes:
        pdf_path = store_receipt(pdf_bytes, receipt.receipt_number)
        receipt.pdf_path = pdf_path
        receipt.reissued_at = datetime.utcnow()
        db.session.commit()
        return pdf_path

    return None
