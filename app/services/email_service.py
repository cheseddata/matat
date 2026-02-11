import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
from ..extensions import db
from ..models.message import MessageQueue
from ..models.config_settings import ConfigSettings

# BCC address for all outgoing emails
BCC_EMAIL = 'support@matatmordechai.org'


def get_email_config():
    """Get email configuration from database."""
    config = ConfigSettings.query.first()

    # Check for Mailtrap API token first
    if config and config.mailtrap_token:
        return {
            'provider': 'mailtrap',
            'token': config.mailtrap_token,
            'from_name': config.email_from_name or 'Matat Mordechai',
            'from_address': config.email_from_address or 'noreply@matatmordechai.org'
        }

    # Check for SMTP config
    if config and config.smtp_host:
        return {
            'provider': 'smtp',
            'host': config.smtp_host,
            'port': config.smtp_port or 587,
            'username': config.smtp_username,
            'password': config.smtp_password,
            'use_tls': config.smtp_use_tls if config.smtp_use_tls is not None else True,
            'from_name': config.email_from_name or 'Matat Mordechai',
            'from_address': config.email_from_address or config.smtp_username
        }

    # Fallback to environment variables
    return {
        'provider': os.environ.get('MAIL_PROVIDER', 'sendgrid'),
        'from_address': os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@matatmordechai.org')
    }


def send_email(to, subject, html_body, text_body=None, attachments=None,
               message_type='general', related_donation_id=None, related_link_id=None):
    """Send email and log to message queue."""
    email_config = get_email_config()
    provider = email_config.get('provider', 'sendgrid')

    # Log to message queue
    message = MessageQueue(
        channel='email',
        recipient_address=to,
        message_type=message_type,
        subject=subject,
        body_html=html_body,
        body_text=text_body,
        attachment_path=attachments[0] if attachments else None,
        related_donation_id=related_donation_id,
        related_link_id=related_link_id,
        provider=provider,
        status='queued'
    )
    db.session.add(message)
    db.session.commit()

    # Try to send
    try:
        if provider == 'mailtrap':
            success = _send_mailtrap(to, subject, html_body, text_body, attachments, email_config)
        elif provider == 'smtp':
            success = _send_smtp(to, subject, html_body, text_body, attachments, email_config)
        elif provider == 'sendgrid':
            success = _send_sendgrid(to, subject, html_body, text_body, attachments)
        else:
            success = False

        if success:
            message.status = 'sent'
            message.sent_at = datetime.utcnow()
        else:
            message.status = 'failed'
            message.error_message = 'Provider not configured or send failed'

        db.session.commit()
        return success
    except Exception as e:
        message.status = 'failed'
        message.error_message = str(e)
        db.session.commit()
        return False


def _send_smtp(to, subject, html_body, text_body=None, attachments=None, config=None):
    """Send email via SMTP."""
    if not config or not config.get('host'):
        return False

    try:
        msg = MIMEMultipart('mixed')
        msg['From'] = f"{config.get('from_name', 'Matat Mordechai')} <{config.get('from_address')}>"
        msg['To'] = to
        msg['Bcc'] = BCC_EMAIL
        msg['Subject'] = subject

        # Recipients include BCC
        recipients = [to, BCC_EMAIL]

        # Create alternative part for text/html
        alt_part = MIMEMultipart('alternative')

        if text_body:
            alt_part.attach(MIMEText(text_body, 'plain', 'utf-8'))
        if html_body:
            alt_part.attach(MIMEText(html_body, 'html', 'utf-8'))

        msg.attach(alt_part)

        # Add attachments
        if attachments:
            for filepath in attachments:
                with open(filepath, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(filepath))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(filepath)}"'
                msg.attach(part)

        # Connect and send
        if config.get('use_tls', True):
            server = smtplib.SMTP(config['host'], config['port'])
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(config['host'], config['port'])

        if config.get('username') and config.get('password'):
            server.login(config['username'], config['password'])

        server.sendmail(config['from_address'], recipients, msg.as_string())
        server.quit()
        return True

    except Exception as e:
        print(f"SMTP error: {e}")
        return False


def _send_mailtrap(to, subject, html_body, text_body=None, attachments=None, config=None):
    """Send email via Mailtrap Email Sending API."""
    import requests
    import base64

    if not config or not config.get('token'):
        return False

    try:
        url = "https://send.api.mailtrap.io/api/send"
        headers = {
            "Authorization": f"Bearer {config['token']}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": {
                "email": config.get('from_address', 'noreply@matatmordechai.org'),
                "name": config.get('from_name', 'Matat Mordechai')
            },
            "to": [{"email": to}],
            "bcc": [{"email": BCC_EMAIL}],
            "subject": subject,
            "html": html_body
        }

        if text_body:
            payload["text"] = text_body

        # Add attachments
        if attachments:
            payload["attachments"] = []
            for filepath in attachments:
                with open(filepath, 'rb') as f:
                    data = f.read()
                encoded = base64.b64encode(data).decode()
                payload["attachments"].append({
                    "content": encoded,
                    "filename": os.path.basename(filepath),
                    "type": "application/pdf",
                    "disposition": "attachment"
                })

        response = requests.post(url, json=payload, headers=headers)
        return response.status_code in [200, 201, 202]

    except Exception as e:
        print(f"Mailtrap error: {e}")
        return False


def _send_sendgrid(to, subject, html_body, text_body=None, attachments=None):
    """Send via SendGrid."""
    api_key = os.environ.get('SENDGRID_API_KEY')
    from_email = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@matatmordechai.org')
    
    if not api_key or api_key == 'SG.placeholder':
        return False
    
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition, Bcc
        import base64

        message = Mail(
            from_email=from_email,
            to_emails=to,
            subject=subject,
            html_content=html_body,
            plain_text_content=text_body
        )

        # Add BCC
        message.add_bcc(Bcc(BCC_EMAIL))

        # Add attachments
        if attachments:
            for filepath in attachments:
                with open(filepath, 'rb') as f:
                    data = f.read()
                encoded = base64.b64encode(data).decode()
                
                attachment = Attachment()
                attachment.file_content = FileContent(encoded)
                attachment.file_name = FileName(os.path.basename(filepath))
                attachment.file_type = FileType('application/pdf')
                attachment.disposition = Disposition('attachment')
                message.add_attachment(attachment)
        
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"SendGrid error: {e}")
        return False


def send_receipt_email(donor, donation, receipt, language=None):
    """Send receipt email to donor with PDF attachment."""
    from flask import render_template

    # Determine language
    lang = language or donor.language_pref or 'en'
    if lang not in ('en', 'he'):
        lang = 'en'

    # Set subject based on language
    if lang == 'he':
        subject = f"קבלה על תרומה - מתת מרדכי (#{receipt.receipt_number})"
    else:
        subject = f"Your Tax-Deductible Receipt - Matat Mordechai (#{receipt.receipt_number})"

    html_body = render_template(
        f'emails/receipt_{lang}.html',
        donor=donor,
        donation=donation,
        receipt=receipt,
        amount=donation.amount_dollars
    )

    # Attach PDF if available
    attachments = [receipt.pdf_path] if receipt.pdf_path and os.path.exists(receipt.pdf_path) else None

    success = send_email(
        to=donor.email,
        subject=subject,
        html_body=html_body,
        attachments=attachments,
        message_type='receipt',
        related_donation_id=donation.id
    )

    if success:
        receipt.email_sent_to = donor.email
        receipt.sent_at = datetime.utcnow()
        donation.receipt_sent = True
        donation.receipt_sent_at = datetime.utcnow()
        db.session.commit()

    return success


def send_donation_link_email(donor_email, donor_name, link, salesperson=None, language='en'):
    """Send donation link email to donor."""
    from flask import render_template

    # Validate language
    lang = language if language in ('en', 'he') else 'en'

    # Set subject based on language
    if lang == 'he':
        subject = "קישור לתרומה - מתת מרדכי"
    else:
        subject = "Donation Link - Matat Mordechai"

    html_body = render_template(
        f'emails/donation_link_{lang}.html',
        donor_name=donor_name,
        donation_url=link.full_url,
        preset_amount=link.preset_amount_dollars,
        salesperson=salesperson
    )

    return send_email(
        to=donor_email,
        subject=subject,
        html_body=html_body,
        message_type='donation_link',
        related_link_id=link.id
    )


def send_sms(to, message, message_type='general', related_link_id=None):
    """Send SMS message (placeholder for Twilio integration)."""
    provider = os.environ.get('SMS_PROVIDER', 'twilio')

    # Log to message queue
    msg = MessageQueue(
        channel='sms',
        recipient_address=to,
        message_type=message_type,
        body_text=message,
        related_link_id=related_link_id,
        provider=provider,
        status='queued'
    )
    db.session.add(msg)
    db.session.commit()

    # Try to send via Twilio
    try:
        success = _send_twilio_sms(to, message)
        if success:
            msg.status = 'sent'
            msg.sent_at = datetime.utcnow()
        else:
            msg.status = 'failed'
            msg.error_message = 'SMS provider not configured'
        db.session.commit()
        return success
    except Exception as e:
        msg.status = 'failed'
        msg.error_message = str(e)
        db.session.commit()
        return False


def _send_twilio_sms(to, message):
    """Send SMS via Twilio."""
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_number = os.environ.get('TWILIO_PHONE_NUMBER')

    if not account_sid or not auth_token or not from_number:
        return False

    if account_sid == 'placeholder':
        return False

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=message,
            from_=from_number,
            to=to
        )
        return True
    except Exception as e:
        print(f"Twilio error: {e}")
        return False


def send_donation_link_sms(phone, donor_name, link, salesperson=None, language='en'):
    """Send donation link via SMS."""
    if language == 'he':
        if salesperson:
            message = f"שלום {donor_name or ''}, {salesperson.full_name} שלח/ה לך קישור לתרומה: {link.full_url}"
        else:
            message = f"שלום {donor_name or ''}, הנה הקישור לתרומה שלך: {link.full_url}"
    else:
        if salesperson:
            message = f"Hi {donor_name or 'there'}, {salesperson.full_name} shared a donation link with you: {link.full_url}"
        else:
            message = f"Hi {donor_name or 'there'}, here's your donation link: {link.full_url}"

    return send_sms(
        to=phone,
        message=message,
        message_type='donation_link',
        related_link_id=link.id
    )
