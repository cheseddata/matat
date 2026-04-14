"""
EZCount API integration for Israeli tax receipts (Section 46).
Ported from ZTorm VBA Module_Kabalot + EZCount COM DLL.

API Key: 3766c7b037ae4f78cc93eaa23a33b89c1739c2d9b4928d2c4ba152337b9227fa
Prefix: Z2
"""
import requests
import json
import logging
from datetime import date, datetime

log = logging.getLogger(__name__)

EZCOUNT_API_URL = 'https://api.ezcount.co.il/api'
API_KEY = '3766c7b037ae4f78cc93eaa23a33b89c1739c2d9b4928d2c4ba152337b9227fa'
DOC_PREFIX = 'Z2'


def create_receipt(donor_name, donor_tz, donor_email, amount, currency='ILS',
                   payment_method='credit', description=None, donor_address=None,
                   donor_city=None, receipt_date=None):
    """Create a receipt via EZCount API.

    Returns dict with: success, doc_number, doc_id, pdf_url, tax_allocation_num, error
    """
    if not receipt_date:
        receipt_date = date.today()

    # Build payment info based on method
    payment_type = _get_payment_type(payment_method)

    # Amount in shekels (not agorot)
    if isinstance(amount, int) and amount > 1000:
        # Likely in agorot/cents, convert
        amount_shekel = amount / 100
    else:
        amount_shekel = float(amount)

    payload = {
        'api_key': API_KEY,
        'type': 400,  # 400 = קבלה על תרומה (donation receipt for amutot/nonprofits)
        'description': description or 'תרומה',
        'customer_name': donor_name,
        'customer_id': str(donor_tz) if donor_tz else '',
        'customer_email': donor_email or '',
        'customer_address': donor_address or '',
        'customer_city': donor_city or '',
        'payment': [{
            'payment_type': payment_type,
            'payment': amount_shekel,
        }],
        'item': [{
            'details': description or 'תרומה',
            'amount': '1',
            'price': amount_shekel,
        }],
        'price_total': amount_shekel,
        'currency_code': _get_currency_code(currency),
        'comment': '',
        'document_date': receipt_date.strftime('%Y-%m-%d'),
        'dont_send_email': 1,  # We send email ourselves via Mailtrap
    }

    log.info(f"EZCount create receipt: {donor_name}, {amount_shekel} {currency}")

    try:
        response = requests.post(
            f'{EZCOUNT_API_URL}/createDoc',
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        log.info(f"EZCount response: {json.dumps(data, ensure_ascii=False)[:500]}")

        if data.get('success'):
            result = {
                'success': True,
                'doc_number': data.get('doc_number', ''),
                'doc_id': data.get('doc_uuid', data.get('id', '')),
                'pdf_url': data.get('pdf_link', data.get('doc_url', '')),
                'tax_allocation_num': data.get('tax_allocation_num', ''),
                'error': None,
                'raw_response': data,
            }
            log.info(f"EZCount receipt created: doc={result['doc_number']}, pdf={result['pdf_url']}")
            return result
        else:
            error_msg = data.get('errMsg', data.get('error', 'Unknown error'))
            log.error(f"EZCount error: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'raw_response': data,
            }

    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'EZCount API timeout'}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': 'Cannot connect to EZCount API'}
    except Exception as e:
        log.error(f"EZCount error: {e}")
        return {'success': False, 'error': str(e)}


def create_credit_note(original_doc_number, donor_name, donor_tz, amount,
                       currency='ILS', reason='ביטול'):
    """Create a cancellation receipt (credit note) via EZCount.
    Used when cancelling an existing receipt.
    """
    amount_shekel = amount / 100 if isinstance(amount, int) and amount > 1000 else float(amount)

    payload = {
        'api_key': API_KEY,
        'type': 330,  # 330 = זיכוי (credit note)
        'description': f'ביטול קבלה {original_doc_number}: {reason}',
        'customer_name': donor_name,
        'customer_id': str(donor_tz) if donor_tz else '',
        'item': [{
            'details': f'ביטול קבלה {original_doc_number}',
            'amount': '1',
            'price': amount_shekel,
        }],
        'price_total': amount_shekel,
        'currency_code': _get_currency_code(currency),
        'dont_send_email': 1,
    }

    try:
        response = requests.post(f'{EZCOUNT_API_URL}/createDoc', json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get('success'):
            return {
                'success': True,
                'doc_number': data.get('doc_number', ''),
                'pdf_url': data.get('pdf_link', ''),
            }
        return {'success': False, 'error': data.get('errMsg', 'Unknown')}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def download_receipt_pdf(pdf_url, save_path):
    """Download receipt PDF from EZCount."""
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return save_path
    except Exception as e:
        log.error(f"Failed to download PDF: {e}")
        return None


def get_tax_allocation(doc_id):
    """Get tax allocation number for a receipt.
    Called after receipt creation to get the tax authority number.
    """
    payload = {
        'api_key': API_KEY,
        'doc_uuid': doc_id,
    }

    try:
        response = requests.post(f'{EZCOUNT_API_URL}/getTaxAllocation', json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return {
            'success': data.get('success', False),
            'tax_allocation_num': data.get('tax_allocation_num', ''),
            'error': data.get('errMsg', None),
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def test_connection():
    """Test EZCount API connectivity."""
    payload = {
        'api_key': API_KEY,
    }
    try:
        response = requests.post(f'{EZCOUNT_API_URL}/user', json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('success'):
            return {
                'success': True,
                'message': f"Connected to EZCount. Account: {data.get('user_name', 'OK')}",
                'data': data,
            }
        return {'success': False, 'message': data.get('errMsg', 'Unknown error')}
    except Exception as e:
        return {'success': False, 'message': str(e)}


def _get_payment_type(method):
    """Map payment method to EZCount payment type code."""
    # EZCount payment types:
    # 1=cash, 2=check, 3=credit card, 4=bank transfer, 5=other
    payment_map = {
        'credit': 3,
        'ashp': 3,
        'cash': 1,
        'check': 2,
        'hork': 4,  # standing order = bank transfer
        'hafkada': 4,
        'transfer': 4,
    }
    return payment_map.get(method, 5)


def _get_currency_code(currency):
    """Map currency to EZCount currency code."""
    # EZCount: ILS=1, USD=2, EUR=3, GBP=4
    currency_map = {
        'ILS': 'ILS',
        'USD': 'USD',
        'EUR': 'EUR',
        'GBP': 'GBP',
    }
    return currency_map.get(currency.upper(), 'ILS')
