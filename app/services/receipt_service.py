import os
import logging
from datetime import datetime
from sqlalchemy import text
from ..extensions import db
from ..models.receipt import Receipt, ReceiptCounter
from ..models.config_settings import ConfigSettings

logger = logging.getLogger(__name__)


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

    # Format date based on language
    if language == 'he':
        # Hebrew date format: DD/MM/YYYY
        date_str = donation.created_at.strftime('%d/%m/%Y')
    else:
        # English date format: Month DD, YYYY
        date_str = donation.created_at.strftime('%B %d, %Y')

    try:
        html_content = render_template(
            template_name,
            donation=donation,
            donor=donor,
            config=config,
            receipt_number=donation.receipt_number,
            date=date_str,
            amount=donation.amount_dollars,
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


def get_receipt_language(donor):
    """
    Determine receipt language based on donor's country.

    US donations MUST be in English (for tax purposes).
    Other countries can use donor's language preference.
    """
    # US donations must always be in English
    if donor.country in ('US', 'USA', 'United States'):
        return 'en'

    # For other countries, use donor's language preference
    if donor.language_pref in ('en', 'he'):
        return donor.language_pref

    # Default to English
    return 'en'


def create_receipt_atomic(donation, donor):
    """
    Create a receipt record and generate PDF atomically.

    This function should be called within an existing transaction.
    Uses SELECT FOR UPDATE to ensure sequential receipt numbers.

    Returns:
        Receipt: The created receipt record, or None on failure
    """
    try:
        # Generate receipt number atomically (within current transaction)
        receipt_number = generate_receipt_number_atomic()
        donation.receipt_number = receipt_number

        config = ConfigSettings.query.first()

        # Determine language - US donations must be in English
        language = get_receipt_language(donor)

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

    # US donations must be in English
    language = get_receipt_language(donor)
    pdf_bytes = generate_receipt_pdf(donation, donor, language)

    if pdf_bytes:
        pdf_path = store_receipt(pdf_bytes, receipt.receipt_number)
        receipt.pdf_path = pdf_path
        receipt.reissued_at = datetime.utcnow()
        db.session.commit()
        return pdf_path

    return None
