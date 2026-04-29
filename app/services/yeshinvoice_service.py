import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

API_BASE_URL = 'https://api.yeshinvoice.co.il/api/v1'
# Verified live 2026-04-29: the working endpoint is
#   POST {API_BASE_URL}/createDocument
# /api/user/createInvoice returns the same Hebrew-error responses but
# never actually persists a document. Earlier integration work targeted
# /api/user/createInvoice — that was a dead end.

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
    """Make authenticated API request to YeshInvoice.

    Empirically the public API uses *both* auth channels at the same time:
    - **Body**: `UserKey` + `SecretKey` (capitalized). `createInvoice`
      enforces this; without these in the body it returns
      "חסר מפתח SECRET KEY" (missing SECRET KEY).
    - **Authorization header**: a JSON-encoded blob with lowercase
      `userkey` / `secret` keys. Their published doc panel shows this
      scheme — we send it too in case a future endpoint requires it.

    Sending both keeps every endpoint happy. Response shape:
      `{"Success": true,  "ReturnValue": ..., "ErrorMessage": null}`  → ok
      `{"Success": false, "ErrorMessage": "<hebrew>", ...}`           → app err
    """
    import json as _json
    body = dict(data or {})
    body['UserKey'] = config['user_key']
    body['SecretKey'] = config['secret_key']

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': _json.dumps({
            'secret':  config['secret_key'],
            'userkey': config['user_key'],
        }, separators=(',', ':')),
    }

    url = f"{API_BASE_URL}/{endpoint}"
    try:
        response = requests.post(url, json=body, headers=headers, timeout=30)
        logger.info(f'YeshInvoice API {endpoint}: status={response.status_code}')
        if response.status_code == 200:
            result = response.json()
            # YeshInvoice always returns 200 + Success boolean + ErrorMessage
            if isinstance(result, dict) and result.get('Success') is False:
                err = result.get('ErrorMessage') or str(result)
                logger.error(f'YeshInvoice API error: {err}')
                return {'success': False, 'error': err}
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
    """Create a receipt/kabala in YeshInvoice for a donation.

    Payload schema confirmed from the YeshInvoice docs panel
    (sample provided 2026-04-29). The structure has top-level
    metadata + a nested `Customer` object + a lowercase `items`
    array. Currency / language / source / status / docType are
    numeric IDs, not strings.

    Returns dict with success, doc_id, doc_number, pdf_url, or error.
    """
    from datetime import datetime as _dt

    if config is None:
        config = get_yeshinvoice_config()
    if not config:
        return {'success': False, 'error': 'YeshInvoice not configured or not enabled'}

    # Numeric IDs from the YeshInvoice schema example. ILS default since
    # this entire flow only fires for ILS donations.
    DOC_TYPE_RECEIPT = 11      # קבלה לתרומה (per YeshInvoice support 2026-04-29)
    CURRENCY_ID_ILS  = 2       # ILS in YeshInvoice's currency table
    LANG_ID_HE       = 359     # Hebrew
    SOURCE_TYPE_API  = 1       # API-issued
    STATUS_ID_ACTIVE = 2       # Active / issued
    VAT_TYPE_EXEMPT  = 2       # Donations are VAT-exempt

    amount = (donation.amount or 0) / 100  # cents → currency units
    now_str = _dt.utcnow().strftime('%Y-%m-%d %H:%M')

    # Customer name fallback chain
    customer_name = f"{donor.first_name or ''} {donor.last_name or ''}".strip()
    name_invoice = getattr(donor, 'company_name', None) or customer_name
    if not customer_name:
        customer_name = name_invoice or donor.email or 'תורם אנונימי'

    # Compose a single address string (YeshInvoice wants one Address field).
    addr_parts = [donor.address_line1, donor.address_line2,
                  donor.city, donor.state, donor.zip, donor.country]
    address = ', '.join(p for p in addr_parts if p)

    # Receipt line item — the donation itself.
    item_name = 'תרומה'
    if donation.receipt_number:
        item_name = f'תרומה (קבלה {donation.receipt_number})'

    payload = {
        'Title': f'תרומה — {customer_name}',
        'DocumentType': DOC_TYPE_RECEIPT,
        'CurrencyId':  CURRENCY_ID_ILS,
        'LangId':      LANG_ID_HE,
        'sourceType':  SOURCE_TYPE_API,
        'statusID':    STATUS_ID_ACTIVE,
        'DateCreated': now_str,
        'MaxDate':     now_str,
        'hideMaxDate': True,
        'SendEmail':   False,   # we send our own donor email
        'SendSMS':     False,
        'Customer': {
            'Name':        customer_name,
            'NameInvoice': name_invoice,
            'Address':     address,
            'Phone':       donor.phone or '',
        },
        'items': [
            {
                'Quantity': 1,
                'Price':    f'{amount:.2f}',
                'Name':     item_name,
                'vatType':  VAT_TYPE_EXEMPT,
            }
        ],
    }

    # Optional account scoping for multi-account customers
    if config.get('account_id'):
        payload['companeNameID'] = config['account_id']

    # Optional teudat-zehut for the donor (Israeli ID), kept under Customer
    # if present — matches how YeshInvoice expects "מזהה לקוח".
    tz = getattr(donor, 'teudat_zehut', None)
    if tz:
        payload['Customer']['NumberID'] = tz

    result = _api_request('createDocument', payload, config)

    if result['success']:
        # Response shape (verified live):
        #   {"Success": true, "ErrorMessage": "",
        #    "ReturnValue": {"id": 8320455, "docNumber": 30001,
        #                    "url": "https://yeshbe.co/...",
        #                    "pdfurl": "https://api.yeshinvoice.co.il/api/user/DownloadInvoice?key=...",
        #                    "signurl": null, "copypdfurl": ...}}
        data = result['data'] or {}
        rv = data.get('ReturnValue') or {}
        doc_id     = str(rv.get('id') or '')
        doc_number = str(rv.get('docNumber') or '')
        pdf_url    = rv.get('pdfurl') or rv.get('url') or ''

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
    """Issue a negative-receipt / credit document to void an original.

    Per YeshInvoice support (2026-04-29): "issued documents cannot be
    deleted, as deleting official documents is not allowed. If you need
    to cancel a specific receipt or invoice, you can issue a negative
    receipt (or credit document) to offset and cancel the original."

    So this function POSTs `createDocument` again with the *same* schema
    as `create_receipt`, but with a **negative** Price and a credit
    DocumentType. The donation's `yeshinvoice_doc_id` / `_doc_number`
    are referenced in the Title and items so the link to the original
    is visible on the credit doc.

    The DocumentType code (currently `4`) and any required reference
    field name (e.g. `RelatedDocumentId`) are unverified — needs a
    confirmation from YeshInvoice support before this is fully reliable.
    See `yeshinvoice_void_policy.md` in the repo root.
    """
    from datetime import datetime as _dt

    if config is None:
        config = get_yeshinvoice_config()
    if not config:
        return {'success': False, 'error': 'YeshInvoice not configured or not enabled'}
    if not donation.yeshinvoice_doc_id:
        return {'success': False, 'error': 'No original YeshInvoice document to reference'}

    # Same numeric IDs as the issuing path, only DocumentType + Price differ.
    DOC_TYPE_CREDIT  = 4       # credit document (TBC with YeshInvoice)
    CURRENCY_ID_ILS  = 2
    LANG_ID_HE       = 359
    SOURCE_TYPE_API  = 1
    STATUS_ID_ACTIVE = 2
    VAT_TYPE_EXEMPT  = 2

    refund_amount = (donation.refund_amount or donation.amount or 0) / 100
    now_str = _dt.utcnow().strftime('%Y-%m-%d %H:%M')
    orig_num = donation.yeshinvoice_doc_number or donation.yeshinvoice_doc_id

    payload = {
        'Title': f'ביטול קבלה {orig_num}',
        'DocumentType': DOC_TYPE_CREDIT,
        'CurrencyId':  CURRENCY_ID_ILS,
        'LangId':      LANG_ID_HE,
        'sourceType':  SOURCE_TYPE_API,
        'statusID':    STATUS_ID_ACTIVE,
        'DateCreated': now_str,
        'MaxDate':     now_str,
        'hideMaxDate': True,
        'SendEmail':   False,
        'SendSMS':     False,
        # Best-guess link-back field name; YeshInvoice may use a different one.
        'RelatedDocumentId': donation.yeshinvoice_doc_id,
        'OriginalDocumentID': donation.yeshinvoice_doc_id,  # belt-and-suspenders
        'Customer': {
            # We don't always have the donor here; minimal payload.
            'Name':        f'ביטול {orig_num}',
            'NameInvoice': f'ביטול {orig_num}',
            'Address':     '',
            'Phone':       '',
        },
        'items': [
            {
                'Quantity': 1,
                'Price':    f'-{refund_amount:.2f}',  # negative to offset
                'Name':     f'ביטול קבלה {orig_num} (תרומה #{donation.id})',
                'vatType':  VAT_TYPE_EXEMPT,
            }
        ],
    }

    if config.get('account_id'):
        payload['companeNameID'] = config['account_id']

    result = _api_request('createDocument', payload, config)

    if result['success']:
        data = result['data'] or {}
        rv = data.get('ReturnValue') or {}
        logger.info(f'YeshInvoice credit note created: id={rv.get("id")}')
        return {
            'success': True,
            'doc_id': str(rv.get('id') or ''),
            'doc_number': str(rv.get('docNumber') or ''),
            'pdf_url': rv.get('pdfurl') or rv.get('url') or '',
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
    url = f"{API_BASE_URL}/createDocument"
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
