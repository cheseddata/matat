import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
from ..extensions import db
from ..models.message import MessageQueue
from ..models.config_settings import ConfigSettings

logger = logging.getLogger(__name__)

# BCC address for all outgoing emails
BCC_EMAIL = 'support@matatmordechai.org'


def get_email_config():
    """Get email configuration from database."""
    config = ConfigSettings.query.first()

    if not config:
        # Fallback to environment variables
        return {
            'provider': os.environ.get('MAIL_PROVIDER', 'sendgrid'),
            'from_address': os.environ.get('MAIL_DEFAULT_SENDER', 'support@matatmordechai.org')
        }

    # Use configured email provider
    provider = config.email_provider or 'mailtrap'

    # ActiveTrail
    if provider == 'activetrail' and config.activetrail_api_key:
        return {
            'provider': 'activetrail',
            'api_key': config.activetrail_api_key,
            'profile_id': config.activetrail_profile_id,  # Sending profile ID
            'group_id': config.activetrail_group_id,  # Group to add contacts to
            'classification': config.activetrail_classification or 'Matat Mordechai',  # Branding/classification
            'from_name': config.activetrail_from_name or config.email_from_name or 'Matat Mordechai',
            'from_address': config.activetrail_from_email or config.email_from_address or 'support@matatmordechai.org'
        }

    # Mailtrap
    if provider == 'mailtrap' and config.mailtrap_token:
        return {
            'provider': 'mailtrap',
            'token': config.mailtrap_token,
            'from_name': config.email_from_name or 'Matat Mordechai',
            'from_address': config.email_from_address or 'support@matatmordechai.org'
        }

    # SMTP
    if provider == 'smtp' and config.smtp_host:
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

    # Fallback - try any available provider
    if config.activetrail_api_key:
        return {
            'provider': 'activetrail',
            'api_key': config.activetrail_api_key,
            'from_name': config.activetrail_from_name or config.email_from_name or 'Matat Mordechai',
            'from_address': config.activetrail_from_email or config.email_from_address or 'support@matatmordechai.org'
        }
    if config.mailtrap_token:
        return {
            'provider': 'mailtrap',
            'token': config.mailtrap_token,
            'from_name': config.email_from_name or 'Matat Mordechai',
            'from_address': config.email_from_address or 'support@matatmordechai.org'
        }
    if config.smtp_host:
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

    # Final fallback to environment variables
    return {
        'provider': os.environ.get('MAIL_PROVIDER', 'sendgrid'),
        'from_address': os.environ.get('MAIL_DEFAULT_SENDER', 'support@matatmordechai.org')
    }


def send_email(to, subject, html_body, text_body=None, attachments=None,
               message_type='general', related_donation_id=None, related_link_id=None):
    """Send email and log to message queue."""
    logger.info(f'send_email: to={to}, subject={subject[:50]}..., type={message_type}')

    # SANDBOX_MODE short-circuit: log the email to the queue but never hit a
    # real provider.
    from ..utils.sandbox import is_sandbox, sandbox_email_success
    if is_sandbox():
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
            provider='sandbox',
            status='sent',
            sent_at=datetime.utcnow(),
        )
        db.session.add(message)
        db.session.commit()
        return sandbox_email_success(to=to, subject=subject)

    email_config = get_email_config()
    provider = email_config.get('provider', 'sendgrid')
    logger.info(f'Email provider: {provider}')

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
    message_id = message.id  # Store for passing to provider

    # Try to send
    try:
        if provider == 'activetrail':
            result = _send_activetrail(to, subject, html_body, text_body, attachments, email_config, message_id)
            success = result.get('success', False) if isinstance(result, dict) else result
            if success and isinstance(result, dict) and result.get('message_id'):
                message.provider_message_id = result['message_id']
        elif provider == 'mailtrap':
            result = _send_mailtrap(to, subject, html_body, text_body, attachments, email_config, message_id)
            success = result.get('success', False) if isinstance(result, dict) else result
            if success and isinstance(result, dict) and result.get('message_ids'):
                message.provider_message_id = ','.join(result['message_ids'])
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


def _send_mailtrap(to, subject, html_body, text_body=None, attachments=None, config=None, internal_message_id=None):
    """Send email via Mailtrap Email Sending API with tracking enabled."""
    import requests
    import base64

    logger.info(f'_send_mailtrap: sending to {to}')

    if not config or not config.get('token'):
        logger.error('Mailtrap: No token configured')
        return {'success': False}

    try:
        url = "https://send.api.mailtrap.io/api/send"
        headers = {
            "Authorization": f"Bearer {config['token']}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": {
                "email": config.get('from_address', 'support@matatmordechai.org'),
                "name": config.get('from_name', 'Matat Mordechai')
            },
            "to": [{"email": to}],
            "bcc": [{"email": BCC_EMAIL}],
            "subject": subject,
            "html": html_body,
            # Enable tracking
            "custom_variables": {
                "internal_message_id": str(internal_message_id) if internal_message_id else ""
            }
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

        logger.info(f'Mailtrap: Sending request to API...')
        response = requests.post(url, json=payload, headers=headers)
        logger.info(f'Mailtrap: Response status={response.status_code}')

        if response.status_code not in [200, 201, 202]:
            logger.error(f'Mailtrap: Failed with status {response.status_code}, response: {response.text}')
            return {'success': False}

        # Parse response to get message IDs
        try:
            resp_data = response.json()
            message_ids = resp_data.get('message_ids', [])
            logger.info(f'Mailtrap: Email sent successfully to {to}, message_ids={message_ids}')
            return {'success': True, 'message_ids': message_ids}
        except:
            logger.info(f'Mailtrap: Email sent successfully to {to}')
            return {'success': True, 'message_ids': []}

    except Exception as e:
        logger.error(f'Mailtrap error: {str(e)}')
        return {'success': False}


def _send_sendgrid(to, subject, html_body, text_body=None, attachments=None):
    """Send via SendGrid."""
    api_key = os.environ.get('SENDGRID_API_KEY')
    from_email = os.environ.get('MAIL_DEFAULT_SENDER', 'support@matatmordechai.org')

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


def _add_to_activetrail_group(email, group_id, config):
    """Add a contact to an ActiveTrail group."""
    import requests

    try:
        url = "https://webapi.mymarketing.co.il/api/contacts/Import"
        headers = {
            "Authorization": config['api_key'],
            "Content-Type": "application/json"
        }
        payload = {
            "group": group_id,
            "contacts": [{"email": email}]
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            logger.info(f'ActiveTrail: Added {email} to group {group_id}')
        else:
            logger.warning(f'ActiveTrail: Failed to add {email} to group: {response.text}')
    except Exception as e:
        logger.warning(f'ActiveTrail: Error adding to group: {e}')


def _send_activetrail(to, subject, html_body, text_body=None, attachments=None, config=None, internal_message_id=None):
    """Send email via ActiveTrail Operational Message API."""
    import requests

    logger.info(f'_send_activetrail: sending to {to}')

    if not config or not config.get('api_key'):
        logger.error('ActiveTrail: No API key configured')
        return {'success': False}

    try:
        # ActiveTrail Operational Message API endpoint
        url = "https://webapi.mymarketing.co.il/api/OperationalMessage/Message"

        headers = {
            "Authorization": config['api_key'],
            "Content-Type": "application/json"
        }

        # Build the email payload per ActiveTrail's API format
        payload = {
            "email_package": [
                {
                    "email": to,
                    "pairs": []  # Can be used for template variables
                }
            ],
            "details": {
                "name": f"Matat Email - {subject[:50]}",
                "subject": subject,
                "user_profile_id": config.get('profile_id'),  # Sender profile ID
                "user_profile_fromname": config.get('from_name', 'Matat Mordechai'),
                "classification": config.get('classification', 'Matat Mordechai')  # Company branding
            },
            "design": {
                "content": html_body,
                "body_part_format": 1  # HTML format
            },
            "bcc": {
                "bcc_emails": [BCC_EMAIL]
            }
        }

        logger.info(f'ActiveTrail: Sending request to API...')
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        logger.info(f'ActiveTrail: Response status={response.status_code}')

        if response.status_code not in [200, 201, 202]:
            logger.error(f'ActiveTrail: Failed with status {response.status_code}, response: {response.text}')
            return {'success': False, 'error': response.text}

        # Parse response - ActiveTrail returns {"campaign_id": 123, "email_send": 1}
        try:
            resp_data = response.json()
            campaign_id = resp_data.get('campaign_id', '')
            email_count = resp_data.get('email_send', 0)
            logger.info(f'ActiveTrail: Email sent successfully to {to}, campaign_id={campaign_id}, emails_sent={email_count}')

            # Add contact to Matat Mordechai group if configured
            group_id = config.get('group_id')
            if group_id:
                _add_to_activetrail_group(to, group_id, config)

            return {'success': True, 'message_id': str(campaign_id)}
        except:
            logger.info(f'ActiveTrail: Email sent successfully to {to}')
            return {'success': True, 'message_id': ''}

    except requests.exceptions.Timeout:
        logger.error('ActiveTrail: Request timed out')
        return {'success': False, 'error': 'timeout'}
    except Exception as e:
        logger.error(f'ActiveTrail error: {str(e)}')
        return {'success': False, 'error': str(e)}


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


def send_custom_donation_link_email(donor_email, subject, body_text, link, language='en', attachment_path=None):
    """Send donation link email with custom content and optional attachment."""
    # Convert plain text body to HTML with proper formatting
    # Escape HTML and convert newlines to <br>
    import html
    escaped_body = html.escape(body_text)
    formatted_body = escaped_body.replace('\n', '<br>')

    # Determine button text based on language
    if language == 'he':
        button_text = "לתרום עכשיו"
        link_fallback = "אם הכפתור לא עובד, העתק והדבק את הקישור הבא בדפדפן שלך:"
        tax_notice = "תרומתך מוכרת לצורכי מס בהתאם לחוק. תקבל קבלה רשמית לאחר עיבוד התרומה."
        thanks = "תודה על נדיבותך!"
    else:
        button_text = "Donate Now"
        link_fallback = "If the button above doesn't work, copy and paste this link into your browser:"
        tax_notice = "Your donation is tax-deductible to the extent allowed by law. You will receive an official receipt via email after your donation is processed."
        thanks = "Thank you for your generosity!"

    html_body = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
    <div style="background: white; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #2c3e50; margin: 0;">Matat Mordechai</h1>
            <p style="color: #666; margin: 5px 0 0 0;">מתת מרדכי</p>
        </div>

        <div style="font-size: 16px; color: #333; line-height: 1.6;">
            {formatted_body}
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{link.full_url}"
               style="display: inline-block; padding: 15px 40px; background: #27ae60; color: white; text-decoration: none; border-radius: 8px; font-size: 18px; font-weight: 600;">
                {button_text}
            </a>
        </div>

        <p style="font-size: 14px; color: #666; line-height: 1.6;">
            {link_fallback}
        </p>
        <p style="font-size: 14px; color: #3498db; word-break: break-all;">
            {link.full_url}
        </p>

        <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">

        <p style="font-size: 14px; color: #666; line-height: 1.6;">
            {tax_notice}
        </p>

        <p style="font-size: 14px; color: #666; margin-top: 20px;">
            {thanks}
        </p>

        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; text-align: center;">
            <p style="font-size: 12px; color: #999; margin: 0;">
                Matat Mordechai is a registered 501(c)(3) nonprofit organization.
            </p>
        </div>
    </div>
</body>
</html>'''

    # Build attachments list
    attachments = None
    if attachment_path and os.path.exists(attachment_path):
        attachments = [attachment_path]

    return send_email(
        to=donor_email,
        subject=subject,
        html_body=html_body,
        text_body=body_text,
        attachments=attachments,
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
