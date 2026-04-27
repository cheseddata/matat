import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

API_BASE_URL = 'https://api.yeshinvoice.co.il/api/user'

# Document type mapping
DOC_TYPES = {
    'receipt': 1,
    'tax_invoice': 2,
    'tax_invoice_receipt': 3,
}

# Currency mapping
CURRENCY_MAP = {
    'usd': 'USD',
    'ils': 'ILS',
    'eur': 'EUR',
    'gbp': 'GBP',
}


def get_yeshinvoice_config():
    """Get YeshInvoice config from database. Returns dict or None if not enabled."""
    from ..models.config_settings import ConfigSettings
    config = ConfigSettings.query.first()
    if not config or not config.yeshinvoice_enabled:
        return None
    if not config.yeshinvoice_user_key or not config.yeshinvoice_secret_key:
        return None
    return {
        'user_key': config.yeshinvoice_user_key,
        'secret_key': config.yeshinvoice_secret_key,
        'account_id': config.yeshinvoice_account_id,
        'default_doc_type': config.yeshinvoice_default_doc_type or 'receipt',
    }


def _api_request(endpoint, data, config):
    """Make authenticated API request to YeshInvoice."""
    data['UserKey'] = config['user_key']
    data['SecretKey'] = config['secret_key']

    url = f"{API_BASE_URL}/{endpoint}"
    try:
        response = requests.post(url, json=data, timeout=30)
        logger.info(f'YeshInvoice API {endpoint}: status={response.status_code}')
        if response.status_code == 200:
            result = response.json()
            # YeshInvoice returns success/error in the response body
            if result.get('Error'):
                logger.error(f'YeshInvoice API error: {result}')
                return {'success': False, 'error': result.get('ErrorMessage', str(result))}
            return {'success': True, 'data': result}
        else:
            logger.error(f'YeshInvoice API error: {response.status_code} {response.text}')
            return {'success': False, 'error': response.text}
    except requests.exceptions.Timeout:
        logger.error(f'YeshInvoice API timeout: {endpoint}')
        return {'success': False, 'error': 'Request timed out'}
    except requests.exceptions.ConnectionError:
        logger.error(f'YeshInvoice API connection error: {endpoint}')
        return {'success': False, 'error': 'Connection error'}
    except Exception as e:
        logger.error(f'YeshInvoice API exception: {e}')
        return {'success': False, 'error': str(e)}


def create_receipt(donation, donor, config=None):
    """Create a receipt/document in YeshInvoice for a donation.

    Args:
        donation: Donation model instance
        donor: Donor model instance
        config: Optional config dict (fetched from DB if not provided)

    Returns:
        dict with success, doc_id, doc_number, pdf_url or error
    """
    if config is None:
        config = get_yeshinvoice_config()
    if not config:
        return {'success': False, 'error': 'YeshInvoice not configured or not enabled'}

    # Map document type
    doc_type_key = config.get('default_doc_type', 'receipt')
    doc_type = DOC_TYPES.get(doc_type_key, 1)

    # Currency
    currency = CURRENCY_MAP.get((donation.currency or 'usd').lower(), 'USD')

    # Amount in dollars/shekels (convert from cents)
    amount = donation.amount / 100 if donation.amount else 0

    # Build customer name
    customer_name = f"{donor.first_name or ''} {donor.last_name or ''}".strip()
    if not customer_name:
        customer_name = donor.email or 'Anonymous Donor'

    # Build payload
    payload = {
        'DocumentType': doc_type,
        'CustomerName': customer_name,
        'EmailAddress': donor.email or '',
        'SendEmail': True,
        'IncludePDF': True,
        'CurrencyID': currency,
        'CustomKey': str(donor.id),
        'Items': [
            {
                'Quantity': 1,
                'UnitPrice': amount,
                'Name': 'Donation to Matat Mordechai',
            }
        ],
    }

    # Add optional fields
    if hasattr(donor, 'teudat_zehut') and donor.teudat_zehut:
        payload['NumberID'] = donor.teudat_zehut

    if hasattr(donor, 'phone') and donor.phone:
        payload['Phone'] = donor.phone

    if config.get('account_id'):
        payload['AccountID'] = config['account_id']

    # Add donation reference in remarks
    payload['Remarks'] = f"Donation #{donation.id}"
    if donation.receipt_number:
        payload['Remarks'] += f" (Receipt {donation.receipt_number})"

    result = _api_request('createInvoice', payload, config)

    if result['success']:
        data = result['data']
        doc_id = str(data.get('DocumentID', ''))
        doc_number = str(data.get('DocumentNumber', ''))
        pdf_url = data.get('PDFLink', '')

        # Update donation record
        from ..extensions import db
        donation.yeshinvoice_doc_id = doc_id
        donation.yeshinvoice_doc_number = doc_number
        donation.yeshinvoice_pdf_url = pdf_url
        db.session.commit()

        logger.info(f'YeshInvoice document created: id={doc_id}, number={doc_number}')
        return {
            'success': True,
            'doc_id': doc_id,
            'doc_number': doc_number,
            'pdf_url': pdf_url,
        }

    return result


def create_credit_note(donation, config=None):
    """Create a credit note (refund receipt) referencing the original document.

    Args:
        donation: Donation model instance (must have yeshinvoice_doc_id)
        config: Optional config dict

    Returns:
        dict with success, doc_id, doc_number, pdf_url or error
    """
    if config is None:
        config = get_yeshinvoice_config()
    if not config:
        return {'success': False, 'error': 'YeshInvoice not configured or not enabled'}

    if not donation.yeshinvoice_doc_id:
        return {'success': False, 'error': 'No original YeshInvoice document to reference'}

    # Refund amount in dollars/shekels
    refund_amount = (donation.refund_amount or donation.amount) / 100

    payload = {
        'DocumentType': 4,  # Credit note
        'OriginalDocumentID': donation.yeshinvoice_doc_id,
        'Items': [
            {
                'Quantity': 1,
                'UnitPrice': refund_amount,
                'Name': 'Refund - Donation to Matat Mordechai',
            }
        ],
        'SendEmail': True,
        'IncludePDF': True,
        'Remarks': f"Credit note for donation #{donation.id}",
    }

    if config.get('account_id'):
        payload['AccountID'] = config['account_id']

    result = _api_request('createInvoice', payload, config)

    if result['success']:
        data = result['data']
        logger.info(f'YeshInvoice credit note created: id={data.get("DocumentID")}')
        return {
            'success': True,
            'doc_id': str(data.get('DocumentID', '')),
            'doc_number': str(data.get('DocumentNumber', '')),
            'pdf_url': data.get('PDFLink', ''),
        }

    return result


def find_or_create_customer(donor, config=None):
    """NOT SUPPORTED on YeshInvoice's public API.

    The /api/user/ namespace exposes only `createInvoice`. Customer
    management lives in the internal /api/v1.1/ portal API which uses
    a different (login-session) auth flow we don't have access to.

    Documents created through `create_receipt()` will auto-create the
    customer on YeshInvoice's side based on the customer name + email
    we pass in the createInvoice payload, so this helper is a no-op.
    """
    return {'success': True, 'customer_id': None,
            'message': 'Customer auto-created on createInvoice; no separate API call needed.'}


def _legacy_find_or_create_customer(donor, config=None):
    """Find or create a customer in YeshInvoice.

    Args:
        donor: Donor model instance
        config: Optional config dict

    Returns:
        dict with success and customer_id or error
    """
    if config is None:
        config = get_yeshinvoice_config()
    if not config:
        return {'success': False, 'error': 'YeshInvoice not configured or not enabled'}

    customer_name = f"{donor.first_name or ''} {donor.last_name or ''}".strip()
    if not customer_name:
        customer_name = donor.email or 'Anonymous Donor'

    payload = {
        'CustomerName': customer_name,
        'EmailAddress': donor.email or '',
        'CustomKey': str(donor.id),
    }

    if hasattr(donor, 'teudat_zehut') and donor.teudat_zehut:
        payload['NumberID'] = donor.teudat_zehut

    if hasattr(donor, 'phone') and donor.phone:
        payload['Phone'] = donor.phone

    if config.get('account_id'):
        payload['AccountID'] = config['account_id']

    result = _api_request('createOrUpdateCustomer', payload, config)

    if result['success']:
        data = result['data']
        customer_id = str(data.get('CustomerID', ''))
        logger.info(f'YeshInvoice customer created/updated: id={customer_id}')
        return {
            'success': True,
            'customer_id': customer_id,
        }

    return result


def get_document(doc_id, config=None):
    """NOT SUPPORTED on YeshInvoice's public API.

    Document retrieval lives in /api/v1.1/ which uses login-session
    auth. The PDF link returned at creation time (Donation.yeshinvoice_pdf_url)
    is the only handle we have to the issued document.
    """
    return {'success': False,
            'error': 'YeshInvoice public API does not expose document lookup.'}


def _legacy_get_document(doc_id, config=None):
    """Get document details including PDF URL.

    Args:
        doc_id: YeshInvoice document ID
        config: Optional config dict

    Returns:
        dict with success and document data or error
    """
    if config is None:
        config = get_yeshinvoice_config()
    if not config:
        return {'success': False, 'error': 'YeshInvoice not configured or not enabled'}

    payload = {
        'DocumentID': doc_id,
    }

    if config.get('account_id'):
        payload['AccountID'] = config['account_id']

    result = _api_request('getDocument', payload, config)

    if result['success']:
        data = result['data']
        return {
            'success': True,
            'doc_id': str(data.get('DocumentID', '')),
            'doc_number': str(data.get('DocumentNumber', '')),
            'pdf_url': data.get('PDFLink', ''),
            'status': data.get('Status', ''),
            'total': data.get('Total', 0),
            'data': data,
        }

    return result


def test_connection(config=None):
    """Test YeshInvoice credentials.

    There is no dedicated "ping" endpoint on the public API, so we hit
    `createInvoice` with a deliberately empty payload. Two outcomes:

    - "מפתח SECRET KEY לא חוקי"  → keys are wrong (auth fail)
    - "אנא הזן שם הלקוח/בית העסק" → keys are GOOD (auth passed; we just
                                       didn't supply a customer name).

    Anything else is treated as failure.
    """
    if config is None:
        config = get_yeshinvoice_config()
    if not config:
        return {'success': False, 'error': 'YeshInvoice not configured or not enabled'}

    import requests
    url = f"{API_BASE_URL}/createInvoice"
    payload = {'UserKey': config['user_key'], 'SecretKey': config['secret_key']}
    try:
        r = requests.post(url, json=payload, timeout=15)
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'Connection error: {e}'}

    body = {}
    try: body = r.json()
    except Exception: pass
    err = (body.get('ErrorMessage') or '') if isinstance(body, dict) else ''

    # Auth-fail signature
    if 'SECRET KEY' in err.upper() or 'מפתח' in err and 'חוקי' in err:
        return {'success': False, 'error': 'Invalid YeshInvoice keys (auth rejected)'}
    # Auth-pass signature: API got past the key check and is asking for body fields
    if 'הלקוח' in err or 'בית העסק' in err or 'CustomerName' in err:
        return {
            'success': True,
            'message': 'Connected successfully — credentials accepted by YeshInvoice.',
        }

    # Any other response — surface the raw error
    return {'success': False, 'error': err or f'HTTP {r.status_code}: {r.text[:200]}'}
