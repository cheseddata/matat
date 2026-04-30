"""
Shva/Ashrait credit card processor.
Ported from ZTorm VBA Module_Ashrait + AshIska.

SOAP API: https://shvaams.nethost.co.il/EMVWeb/Prod/EMVRequest.asmx
Format: inputObj contains card data XML, globalObj is empty.
"""
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
import logging
from .base import BasePaymentProcessor

log = logging.getLogger(__name__)

# ISO currency codes used by Shva
CURRENCY_ISO = {'ILS': '376', 'USD': '840', 'EUR': '978', 'GBP': '826'}


class ShvaProcessor(BasePaymentProcessor):

    PROD_URL = 'https://shvaams.nethost.co.il/EMVWeb/Prod/EMVRequest.asmx'
    TEST_URL = 'https://shvaams.nethost.co.il/EMVWeb/Test/EMVRequest.asmx'

    def __init__(self, config=None):
        super().__init__(config)
        self.merchant_number = config.get('merchant_number', '2481062014') if config else '2481062014'
        self.username = config.get('username', 'MXRCX') if config else 'MXRCX'
        self.password = config.get('password', 'Z496089') if config else 'Z496089'
        self.is_test = config.get('test_mode', False) if config else False

    @property
    def code(self): return 'shva'
    @property
    def name(self): return 'Shva/Ashrait'
    @property
    def display_name_he(self): return 'שב"א / אשראית'
    @property
    def url(self): return self.TEST_URL if self.is_test else self.PROD_URL
    @property
    def supported_currencies(self): return ['ILS', 'USD', 'EUR', 'GBP']
    @property
    def supported_countries(self): return ['IL']

    def create_payment(self, amount, currency, card_data, donor_data=None, **kwargs):
        """Charge a credit card via Shva.
        amount: in agorot/cents
        card_data: {card_number, expiry (MMYY), cvv}
        """
        amount_agorot = int(amount)
        iso_currency = CURRENCY_ISO.get(currency.upper(), '376')
        installments = int(kwargs.get('installments', 1))

        card_number = card_data.get('card_number', '').replace('-', '').replace(' ', '')
        expiry_mmyy = card_data.get('expiry', '')  # User enters MMYY
        cvv = card_data.get('cvv', '')

        # Convert MMYY to YYMM for Shva
        if len(expiry_mmyy) == 4:
            expiry_yymm = expiry_mmyy[2:4] + expiry_mmyy[0:2]  # MMYY -> YYMM
        else:
            expiry_yymm = expiry_mmyy

        # Credit terms: 1=regular, 6=credit(equal), 8=installments(first different)
        if installments > 1:
            credit_terms = '8'
            first_payment = amount_agorot // installments + (amount_agorot % installments)
            fixed_payment = amount_agorot // installments
            num_payments = installments - 1
        else:
            credit_terms = '1'
            first_payment = 0
            fixed_payment = 0
            num_payments = 1

        # Build inputObj XML (matches VBA AshIska.OutString exactly)
        inner = (
            '<mti>100</mti>'
            '<panEntryMode>50</panEntryMode>'
            '<zData>00000000</zData>'
            '<tranType>01</tranType>'
            f'<clientInputPan>{card_number}</clientInputPan>'
            f'<expirationDate>{expiry_yymm}</expirationDate>'
            f'<amount>{amount_agorot}</amount>'
            f'<currency>{iso_currency}</currency>'
            f'<creditTerms>{credit_terms}</creditTerms>'
        )

        if installments > 1:
            inner += f'<firstPayment>{first_payment}</firstPayment>'
            inner += f'<notFirstPayment>{fixed_payment}</notFirstPayment>'
            inner += f'<noPayments>{num_payments}</noPayments>'

        if cvv:
            inner += f'<cvv2>{cvv}</cvv2>'

        if donor_data and donor_data.get('tz'):
            inner += f'<id>{donor_data["tz"]}</id>'

        inner += '<parameterJ>5</parameterJ>'  # J5 = full auth + capture

        try:
            response = self._call_soap('AshFull', inner)

            if not response:
                return {'success': False, 'error': 'No response from Shva', 'raw_response': None}

            # Get status from xmlStr response
            xml_str = response.get('xmlStr', '')
            result_dict = {}
            if xml_str:
                result_dict = self._parse_xml_fragment(xml_str)

            ash_status = (result_dict.get('ashStatus') or
                          response.get('AshFullResult', '-1'))

            # 0 = approved (J5 full), 777 = approved (J2 auth only), 42 = approved (check)
            success = str(ash_status) in ('0', '777', '42')
            ash_desc = result_dict.get('ashStatusDes', '')

            if not success:
                # Dump everything we got back. When ashStatus is set at the
                # envelope level (top-level AshFullResult) and xmlStr is
                # empty, the request was rejected pre-processing —
                # typically auth / terminal-config / currency.
                log.error(
                    f'Shva DECLINED — ashStatus={ash_status} ashStatusDes={ash_desc!r} '
                    f'parsed={result_dict} '
                    f'raw_xmlStr={xml_str[:600]!r} '
                    f'soap_response_keys={list(response.keys())} '
                    f'AshFullResult={response.get("AshFullResult")!r}'
                )

            return {
                'success': success,
                'transaction_id': result_dict.get('uid', ''),
                'confirmation': result_dict.get('authManpikNo', ''),
                'authorization_code': result_dict.get('authCodeManpik', ''),
                'card_name': result_dict.get('cardName', ''),
                'card_brand': result_dict.get('brand', ''),
                'solek': result_dict.get('solek', ''),
                'rrn': result_dict.get('rrn', ''),
                'ash_status': str(ash_status),
                'ash_status_desc': ash_desc,
                'error': None if success else f"Shva error {ash_status}: {ash_desc}",
                'raw_response': response,
            }
        except Exception as e:
            log.error(f"Shva create_payment error: {e}")
            return {'success': False, 'error': str(e), 'raw_response': None}

    def check_card(self, card_number):
        card_clean = card_number.replace('-', '').replace(' ', '')
        next_exp = datetime.now().strftime('%y%m')
        inner = (
            '<mti>100</mti><panEntryMode>50</panEntryMode>'
            f'<clientInputPan>{card_clean}</clientInputPan>'
            f'<expirationDate>{next_exp}</expirationDate>'
            '<amount>100</amount><currency>376</currency>'
            '<creditTerms>1</creditTerms><parameterJ>2</parameterJ>'
        )
        try:
            response = self._call_soap('AshFull', inner)
            xml_str = response.get('xmlStr', '')
            result_dict = self._parse_xml_fragment(xml_str) if xml_str else {}
            status = result_dict.get('ashStatus', '-1')
            return {'valid': str(status) != '447', 'card_name': result_dict.get('cardName', ''),
                    'status': status, 'message': result_dict.get('ashStatusDes', '')}
        except Exception as e:
            return {'valid': True, 'message': str(e)}

    def get_client_config(self):
        return {'processor': 'shva', 'name': self.name, 'name_he': self.display_name_he,
                'supported_currencies': self.supported_currencies,
                'requires_card_entry': True, 'supports_installments': True, 'max_installments': 36}

    def test_connection(self):
        try:
            response = self._call_soap('GetTerminalData', '')
            if response:
                return {'success': True, 'message': f'Connected. Terminal: {response.get("TerminalName", "OK")}'}
            return {'success': False, 'message': 'No response'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def estimate_fee(self, amount, currency):
        return int(amount * 0.01)

    def _call_soap(self, method, inner_data, timeout=60):
        """Call Shva SOAP API. Format matches VBA ZCNetLib.AshraitWS."""
        if inner_data:
            data_xml = f'<inputObj>{inner_data}</inputObj><globalObj />'
        else:
            data_xml = ''

        soap = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
            '<soap:Body>'
            f'<{method} xmlns="http://shva.co.il/xmlwebservices/">'
            f'<MerchantNumber>{self.merchant_number}</MerchantNumber>'
            f'<UserName>{self.username}</UserName>'
            f'<Password>{self.password}</Password>'
            f'{data_xml}'
            f'</{method}>'
            '</soap:Body>'
            '</soap:Envelope>'
        )

        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': f'http://shva.co.il/xmlwebservices/{method}',
        }

        # Log the inputObj inner XML (with the PAN masked) so we can
        # verify what we sent — TZ, currency, amount, etc.
        masked = soap
        try:
            import re as _re
            masked = _re.sub(r'(<clientInputPan>)\d+(?=</clientInputPan>)',
                             lambda m: m.group(1) + '**MASKED**', masked)
            masked = _re.sub(r'(<cvv2>)\d+(?=</cvv2>)',
                             lambda m: m.group(1) + '***', masked)
            masked = _re.sub(r'(<Password>)[^<]+(?=</Password>)',
                             lambda m: m.group(1) + '****', masked)
        except Exception:
            pass
        log.info(f"Shva {method} -> {self.url}")
        log.info(f"Shva REQUEST body: {masked[:1500]}")
        r = requests.post(self.url, data=soap.encode('utf-8'), headers=headers, timeout=timeout)
        log.info(f"Shva response: {r.status_code}")

        if r.status_code != 200:
            log.error(f"Shva error: {r.text[:500]}")
        r.raise_for_status()

        # Capture the full body for diagnostics — Shva sometimes rejects at
        # the envelope and never populates xmlStr, so we want to see the
        # raw response.
        log.info(f"Shva raw body ({len(r.text)} chars): {r.text[:2000]}")
        return self._parse_soap_response(r.text)

    def _parse_soap_response(self, xml_text):
        """Parse full SOAP response into dict."""
        result = {}
        try:
            root = ET.fromstring(xml_text)
            for elem in root.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if elem.text and elem.text.strip():
                    # Decode HTML entities in xmlStr
                    val = elem.text.strip()
                    if tag == 'xmlStr' or tag == 'TermDataXML':
                        val = val.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
                    result[tag] = val
        except ET.ParseError:
            result['raw'] = xml_text
        return result

    def _parse_xml_fragment(self, xml_str):
        """Parse the xmlStr value tag content into a flat dict."""
        result = {}
        # Wrap in root if needed
        if not xml_str.startswith('<'):
            return result
        try:
            wrapped = f'<root>{xml_str}</root>'
            root = ET.fromstring(wrapped)
            for elem in root.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if tag != 'root' and elem.text and elem.text.strip():
                    result[tag] = elem.text.strip()
        except:
            pass
        return result
