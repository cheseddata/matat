"""
Email service - sends via Mailtrap API.
Mailtrap token from server: bf3f6a4c7312f3a620b7411f931aa922
"""
import os
import json
import base64
import requests
from datetime import datetime
from ...extensions import db
from ...models import Communication

MAILTRAP_TOKEN = 'bf3f6a4c7312f3a620b7411f931aa922'
MAILTRAP_API_URL = 'https://send.api.mailtrap.io/api/send'
FROM_EMAIL = 'support@matatmordechai.org'
FROM_NAME = 'מתת מרדכי - Matat Mordechai'
BCC_EMAIL = 'support@matatmordechai.org'


def send_receipt_email(donor, receipt, pdf_path=None):
    """Send receipt email to donor via Mailtrap."""
    if not donor.email:
        return _log_email(donor.id, receipt.donation_id, receipt.id,
                          'receipt', 'NoEmail', 'Donor has no email address')

    amount_display = abs(receipt.amount) / 100
    currency_symbol = {'ILS': '₪', 'USD': '$', 'EUR': '€'}.get(
        (receipt.currency or 'ILS').upper(), '₪')

    subject = f"קבלה מספר {receipt.receipt_number} - מתת מרדכי"

    body_html = f"""
    <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #2F5597; color: white; padding: 16px; text-align: center;">
            <h2 style="margin: 0;">מתת מרדכי</h2>
            <p style="margin: 4px 0;">קבלה על תרומה</p>
        </div>
        <div style="padding: 20px; background: #f9f9f9;">
            <p>שלום {donor.display_name},</p>
            <p>תודה רבה על תרומתכם!</p>
            <p>מצורפת קבלה מספר <strong>{receipt.receipt_number}</strong>.</p>
            <table style="margin: 16px 0; border-collapse: collapse;">
                <tr><td style="padding: 4px 12px; border: 1px solid #ddd;"><strong>סכום:</strong></td>
                    <td style="padding: 4px 12px; border: 1px solid #ddd;">{currency_symbol}{amount_display:,.2f}</td></tr>
                <tr><td style="padding: 4px 12px; border: 1px solid #ddd;"><strong>תאריך:</strong></td>
                    <td style="padding: 4px 12px; border: 1px solid #ddd;">{receipt.receipt_date.strftime('%d/%m/%Y') if receipt.receipt_date else ''}</td></tr>
                <tr><td style="padding: 4px 12px; border: 1px solid #ddd;"><strong>מספר קבלה:</strong></td>
                    <td style="padding: 4px 12px; border: 1px solid #ddd;">{receipt.receipt_number}</td></tr>
            </table>
            <p style="color: #666; font-size: 12px;">קבלה זו מהווה אישור לצורכי מס בהתאם לסעיף 46 לפקודת מס הכנסה</p>
        </div>
        <div style="background: #eee; padding: 12px; text-align: center; font-size: 11px; color: #888;">
            מתת מרדכי | 868 East 26th Street, Brooklyn, NY 11210
        </div>
    </div>
    """

    # Build Mailtrap payload
    payload = {
        'from': {'email': FROM_EMAIL, 'name': FROM_NAME},
        'to': [{'email': donor.email, 'name': donor.display_name}],
        'bcc': [{'email': BCC_EMAIL}],
        'subject': subject,
        'html': body_html,
        'category': 'receipt',
    }

    # Attach PDF if exists
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            file_data = base64.b64encode(f.read()).decode()
        filename = os.path.basename(pdf_path)
        content_type = 'application/pdf' if filename.endswith('.pdf') else 'text/html'
        payload['attachments'] = [{
            'filename': filename,
            'content': file_data,
            'type': content_type,
        }]

    try:
        response = requests.post(
            MAILTRAP_API_URL,
            headers={
                'Authorization': f'Bearer {MAILTRAP_TOKEN}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        return _log_email(donor.id, receipt.donation_id, receipt.id,
                          'receipt', 'sent',
                          f'Sent via Mailtrap to {donor.email}')
    except Exception as e:
        return _log_email(donor.id, receipt.donation_id, receipt.id,
                          'receipt', 'error',
                          f'Mailtrap send failed: {str(e)}')


def send_donation_thank_you(donor, donation):
    """Send thank you email after donation via Mailtrap."""
    if not donor.email:
        return _log_email(donor.id, donation.id, None,
                          'thank_you', 'NoEmail', 'No email')

    amount_display = donation.amount_display
    currency_symbol = donation.currency_symbol

    subject = "תודה על תרומתכם - מתת מרדכי | Thank you for your donation"

    body_html = f"""
    <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #2F5597; color: white; padding: 16px; text-align: center;">
            <h2 style="margin: 0;">מתת מרדכי</h2>
        </div>
        <div style="padding: 20px; background: #f9f9f9;">
            <p>שלום {donor.display_name},</p>
            <p>תודה רבה על תרומתכם בסך <strong>{currency_symbol}{amount_display:,.2f}</strong>!</p>
            <p>תרומתכם תסייע רבות לפעילות העמותה.</p>
            <p>בברכה,<br>מתת מרדכי</p>
        </div>
    </div>
    """

    payload = {
        'from': {'email': FROM_EMAIL, 'name': FROM_NAME},
        'to': [{'email': donor.email, 'name': donor.display_name}],
        'bcc': [{'email': BCC_EMAIL}],
        'subject': subject,
        'html': body_html,
        'category': 'thank_you',
    }

    try:
        response = requests.post(
            MAILTRAP_API_URL,
            headers={
                'Authorization': f'Bearer {MAILTRAP_TOKEN}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return _log_email(donor.id, donation.id, None,
                          'thank_you', 'sent',
                          f'Sent via Mailtrap to {donor.email}')
    except Exception as e:
        return _log_email(donor.id, donation.id, None,
                          'thank_you', 'error',
                          f'Mailtrap send failed: {str(e)}')


def _log_email(donor_id, donation_id, receipt_id, comm_type, status, notes):
    """Log email to communications table."""
    comm = Communication(
        donor_id=donor_id,
        donation_id=donation_id,
        receipt_id=receipt_id,
        comm_type=comm_type,
        status=status,
        registration_date=datetime.utcnow().date(),
        execution_date=datetime.utcnow().date() if status == 'sent' else None,
        notes=notes,
    )
    db.session.add(comm)
    return comm
