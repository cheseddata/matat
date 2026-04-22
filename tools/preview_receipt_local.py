"""Render the donation-receipt PDF locally via headless Chrome.

Motivation: WeasyPrint on Windows needs GTK DLLs that aren't installed
here. Chrome is already present, and its `--print-to-pdf` renders our
template faithfully (same CSS engine our users see).

Output:  F:\\matat_git\\preview.pdf        (the PDF)
         F:\\matat_git\\app\\static\\preview.pdf  (same file, served by Flask
                                                  so the in-editor preview
                                                  tab can refresh to it)

Usage:  venv\\Scripts\\python tools\\preview_receipt_local.py [lang] [amount]
        lang    defaults to 'en'
        amount  defaults to 180.00
"""
import os
import sys
import subprocess
import tempfile
from datetime import datetime

# --- Resolve paths ---------------------------------------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STATIC_IMG = os.path.join(ROOT, 'app', 'static', 'img').replace('\\', '/')
STATIC_DIR = os.path.join(ROOT, 'app', 'static').replace('\\', '/')
TEMPLATE_DIR = os.path.join(ROOT, 'app', 'templates', 'pdf')

lang = sys.argv[1] if len(sys.argv) > 1 else 'en'
amount = float(sys.argv[2]) if len(sys.argv) > 2 else 180.00

# --- Mock donor/donation/receipt (duck-typed, no DB) -----------------
class O:  # generic bag of attributes
    def __init__(self, **kw): self.__dict__.update(kw)

donor = O(
    full_name='Menachem Kantor',
    email='mkantor@mkantor.com',
    address_line1='4B Cannas Dr',
    address_line2=None,
    address=None,
    city='Lakewood',
    state='New Jersey',
    zip_code='08701',
    country='US',
    language_pref='en',
)
donation = O(
    amount=amount,
    amount_dollars=amount,
    currency='USD',
    status='succeeded',
    donation_type='one_time',
    payment_method='Credit Card',
    payment_method_type='card',
    payment_method_brand='visa',
    payment_method_last4='4242',
    stripe_payment_intent_id='pi_preview',
    stripe_charge_id='ch_preview',
    bank_name=None,
    created_at=datetime.utcnow(),
    receipt_number='MM-2026-PREVIEW',
)
config = O(
    org_name='Matat Mordechai',
    org_prefix='MM',
    org_address='',
    org_city='',
    org_state='',
    org_zip='',
    org_phone='',
    tax_id='20-4266983',
)

# --- Amount to words (mirror receipt_service._amount_to_words) -------
try:
    from num2words import num2words
    whole = int(amount)
    cents = int(round((amount - whole) * 100))
    words = num2words(whole, lang='en').title()
    unit = 'Dollar' if whole == 1 else 'Dollars'
    amount_in_words = f"{words} {unit} and {cents:02d}/100"
except Exception:
    amount_in_words = f"{amount:.2f} Dollars"

# --- Render template via Jinja2 --------------------------------------
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)
template_name = f'receipt_{lang}.html'
template = env.get_template(template_name)

html = template.render(
    donation=donation,
    donor=donor,
    config=config,
    receipt_number=donation.receipt_number,
    date=donation.created_at.strftime('%B %d, %Y'),
    amount=amount,
    amount_in_words=amount_in_words,
    tax_id=config.tax_id,
    org_name=config.org_name,
)

# Rewrite the server-only font & background image paths to local ones.
html = html.replace(
    'file:///var/www/matat/app/static/img/',
    f'file:///{STATIC_IMG}/',
)
html = html.replace(
    'file:///var/www/matat/app/static/fonts/',
    f'file:///{STATIC_DIR}/fonts/',
)

# --- Write HTML to a temp file, shoot it through Chrome --------------
tmp_html = tempfile.NamedTemporaryFile(
    mode='w', encoding='utf-8', suffix='.html', delete=False,
)
tmp_html.write(html)
tmp_html.close()

out_pdf = os.path.join(ROOT, 'preview.pdf')
static_pdf = os.path.join(ROOT, 'app', 'static', 'preview.pdf')

chrome = r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
if not os.path.exists(chrome):
    chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

cmd = [
    chrome,
    '--headless=new',
    '--disable-gpu',
    '--no-pdf-header-footer',
    '--print-to-pdf-no-header',
    '--no-margins',
    f'--print-to-pdf={out_pdf}',
    'file:///' + tmp_html.name.replace('\\', '/'),
]
print('>', ' '.join(cmd))
subprocess.run(cmd, check=True)

# Copy into /static so Flask preview can refresh to it.
import shutil
shutil.copyfile(out_pdf, static_pdf)

os.unlink(tmp_html.name)
print(f'wrote {out_pdf} ({os.path.getsize(out_pdf)} bytes)')
print(f'wrote {static_pdf}')
