"""One-shot — create 5 draft emails in support@matatmordechai.org's
Exchange Drafts folder asking each Jewish content filter to whitelist
matatmordechai.org. Triggered by ticket #17 from mrosen (2026-06-17).

Run once:
    cd /var/www/matat && source venv/bin/activate && python tools/draft_filter_whitelist_letters.py

The drafts land in the mailbox's Drafts folder so MK can review/edit
each one in OWA / Outlook before sending. POST /users/{mailbox}/messages
creates the message in Drafts by default (saveToSentItems=False is the
default for /messages, unlike /sendMail).
"""
import requests
from app import create_app
from app.models.email_inbox_provider import EmailInboxProvider
from app.services.email.microsoft_graph_inbox import (
    MicrosoftGraphInbox, GRAPH_BASE_URL,
)


# Each tuple: (to_address, subject, html_body)
DRAFTS = [
    (
        'support@netspark.com',
        'Whitelist request — matatmordechai.org — nonprofit donation site',
        """<p>Dear Netspark Team,</p>
<p>We operate <strong>matatmordechai.org</strong>, the official donation site of <em>Matat Mordechai</em>, a registered 501(c)(3) nonprofit / Israeli ע"ר (amuta) that funds wedding assistance, kimcha d'pischa, and aid to needy families in Eretz Yisrael and the United States.</p>
<p>Several of our donors have reported that the site is currently blocked by the Netspark filter, preventing them from completing their donation. The site contains:</p>
<ul>
  <li>A homepage describing the organization's tzedakah activities</li>
  <li>A donation form (Stripe and Nedarim Plus for ILS)</li>
  <li>Tax-receipt download (Section 46 and IRS 501(c)(3))</li>
</ul>
<p>There is no advertising, no user-generated content, no social features, and no external links other than to our payment processors.</p>
<p>Please whitelist:</p>
<ul>
  <li><code>matatmordechai.org</code></li>
  <li><code>www.matatmordechai.org</code></li>
</ul>
<p>Thank you for the important work you do for our community.</p>
<p>Sincerely,<br>
<strong>Menachem Kantor</strong><br>
Matat Mordechai<br>
support@matatmordechai.org</p>""",
    ),
    (
        'office@rimon.net.il',
        'בקשת הוצאה מסינון — matatmordechai.org — אתר תרומות לעמותה',
        """<div dir="rtl">
<p>שלום רב,</p>
<p>אנו מפעילים את אתר התרומות הרשמי של עמותת <strong>מתת מרדכי</strong> (ע"ר), המסייעת לחתונות, קמחא דפסחא ומשפחות נזקקות בארץ ובחו"ל.</p>
<p>כמה מתורמינו דיווחו כי האתר חסום על-ידי מסנן רימון / ג'נטק. נבקש להוציא מסינון את הכתובת:</p>
<ul>
  <li><strong>matatmordechai.org</strong></li>
  <li><strong>www.matatmordechai.org</strong></li>
</ul>
<p>האתר מכיל אך ורק:</p>
<ul>
  <li>דף בית עם פרטי העמותה ופעילותה</li>
  <li>טופס תרומה (Stripe לדולרים, נדרים פלוס לשקלים)</li>
  <li>הורדת קבלות (טופס 46 / 501(c)(3))</li>
</ul>
<p>אין באתר פרסומות, תוכן גולשים, רשתות חברתיות או קישורים חיצוניים מלבד למעבדי התשלום.</p>
<p>תודה רבה על עבודתכם החשובה למען הציבור החרדי.</p>
<p>בברכה,<br>
<strong>מנחם קנטור</strong><br>
מתת מרדכי<br>
support@matatmordechai.org</p>
</div>""",
    ),
    (
        'info@meshimer.co.il',
        'בקשת הוצאה מסינון — אתר התרומות של עמותת מתת מרדכי',
        """<div dir="rtl">
<p>לכבוד צוות משמר,</p>
<p>אנו מפעילים את אתר התרומות הרשמי של עמותת <strong>מתת מרדכי</strong> (ע"ר), עמותה רשומה המסייעת לחתונות, קמחא דפסחא ומשפחות נזקקות. תורם דיווח כי האתר חסום למשתמשי משמר.</p>
<p>נבקש להוציא מרשימת הסינון:</p>
<ul>
  <li>matatmordechai.org</li>
  <li>www.matatmordechai.org</li>
</ul>
<p>תוכן האתר: דף עמותה, טופס תרומה, והורדת קבלות מס בלבד.</p>
<p>בברכת התורה,<br>
<strong>מנחם קנטור</strong><br>
מתת מרדכי<br>
support@matatmordechai.org</p>
</div>""",
    ),
    (
        'support@akeenu.com',
        'Whitelist request — matatmordechai.org — nonprofit donation site',
        """<p>Dear Akeenu Team,</p>
<p>Donors using Akeenu-filtered networks (yeshivas, Beis Yaakov schools, kollelim) have reported that <strong>matatmordechai.org</strong> is blocked. We are a registered nonprofit funding wedding assistance and kimcha d'pischa.</p>
<p>Please whitelist:</p>
<ul>
  <li>matatmordechai.org</li>
  <li>www.matatmordechai.org</li>
</ul>
<p>The site has no advertising, no user-generated content, no social features, and exists solely to accept tzedakah donations and serve tax receipts (Section 46 / 501(c)(3)).</p>
<p>Thank you,<br>
<strong>Menachem Kantor</strong><br>
Matat Mordechai<br>
support@matatmordechai.org</p>""",
    ),
    (
        'service@kanguru.co.il',
        'בקשת הוצאה מסינון — matatmordechai.org — אתר תרומות לעמותה',
        """<div dir="rtl">
<p>שלום רב,</p>
<p>אנו מפעילים את אתר התרומות הרשמי של עמותת <strong>מתת מרדכי</strong> (ע"ר). תורמים דיווחו כי האתר חסום על-ידי מסנן כנגורו.</p>
<p>נבקש להוציא מסינון את:</p>
<ul>
  <li><strong>matatmordechai.org</strong></li>
  <li><strong>www.matatmordechai.org</strong></li>
</ul>
<p>האתר מכיל דף עמותה, טופס תרומה, והורדת קבלות מס בלבד — ללא פרסומות, ללא תוכן גולשים, ללא קישורים חיצוניים מלבד מעבדי תשלום.</p>
<p>תודה רבה,<br>
<strong>מנחם קנטור</strong><br>
מתת מרדכי<br>
support@matatmordechai.org</p>
</div>""",
    ),
]


def create_draft(inbox, to_addr, subject, body_html):
    """POST to /users/{mailbox}/messages creates a draft in the Drafts
    folder (not Sent). Returns (ok, msg)."""
    token_resp = inbox._get_access_token()
    if 'error' in token_resp:
        return False, token_resp['error']

    url = f'{GRAPH_BASE_URL}/users/{inbox._mailbox()}/messages'
    headers = {
        'Authorization': f'Bearer {token_resp["access_token"]}',
        'Content-Type':  'application/json',
    }
    payload = {
        'subject':      subject,
        'body':         {'contentType': 'HTML', 'content': body_html},
        'toRecipients': [{'emailAddress': {'address': to_addr}}],
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.exceptions.RequestException as e:
        return False, f'network: {e}'

    if r.status_code in (200, 201):
        msg_id = r.json().get('id', '?')
        return True, f'draft created (id {msg_id[:24]}...)'
    return False, f'HTTP {r.status_code}: {r.text[:200]}'


def main():
    app = create_app()
    with app.app_context():
        row = (EmailInboxProvider.query
               .filter_by(code='msgraph', enabled=True, deleted_at=None)
               .first())
        if not row:
            print('No MSGraph mailbox configured. Aborting.')
            return

        inbox = MicrosoftGraphInbox(row)
        print(f'Mailbox: {inbox._mailbox()}\n')

        for to_addr, subject, body in DRAFTS:
            ok, msg = create_draft(inbox, to_addr, subject, body)
            tag = 'OK ' if ok else 'ERR'
            print(f'  [{tag}]  {to_addr:30s}  {msg}')


if __name__ == '__main__':
    main()
