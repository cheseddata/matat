# Handoff — YeshInvoice wrong-receipt investigation

**From:** Claude on the server (CLI, in `/var/www/matat`)
**To:** Claude on Menachem's PC (GUI / VS Code, browser access)
**Date started:** 2026-07-02
**Branch:** `master` · **Head:** `5fbad95` (unrelated to this issue)
**User:** Menachem Kantor — `support@matatmordechai.org`

Read this cold, then pick up from **"What you need to do"** at the bottom. When you're done, update me (server-side Claude) by writing your findings to `handoffyesh-response.md` — I'll pick it up next time I'm invoked.

---

## The problem in one sentence

Real donors (esp. Moshe Broner in London) have been receiving many Hebrew tax-receipts from our YeshInvoice account for donations they never made — but **our matat code has only ever created 2 YeshInvoice docs** (both tests). Someone else's system is writing to the same YeshInvoice account.

## The evidence

- On our YeshInvoice account, docs go up to **docNumber 1641** as of 2026-07-01.
- Every doc has a `uniqueKeyApi` prefix. On our account:
  - **`Z2_...`** — us (matat matat, current system). We've created exactly **2** (docNumbers 1016 & 1020, both admin test docs).
  - **`Z1_...`** — someone else. Roughly **1620 docs** on our account carry this prefix.
- Our webhook receiver at `POST /api/yeshinvoice/webhook/doc` forwards every YeshInvoice event to `https://seq.swiftech.co.il/yesh/mm/doc`. **Swiftech** is the likely source of `Z1_` — a legacy Matat system that predates the current one and appears to still be issuing receipts on the same YeshInvoice account.
- YeshInvoice **provisions all `uniqueKeyApi` prefixes** — clients cannot mint their own. If `Z1_` exists, YeshInvoice granted it to whoever owns `Z1_`. They know who that is; we don't.

## The complainants

### 1. Moshe Broner-Cohen (`moshebronercohen@cohenarnold.com` / `moshebc@cohenarnold.com`)
- **He IS one of our donors** — donor #7 in our DB: Moshe Broner, `moshebc@cohenarnold.com`, UK (`NW11 9RG` Golders Green), 2 USD Stripe donations only ($10 on 2026-01-13, $36 on 2025-04-06). **No Nedarim, no ILS donations, no June-2 donation on our side.**
- On **2026-06-02** he first emailed `support@matatmordechai.org` complaining he got a Hebrew receipt for donation #1102 with donor name "מיכל ושרה ברינקמן" (Michal & Sara Brinkmann) at his email address.
- That email **sat in our inbox for a full month** before anyone escalated it (today, 2026-07-02).
- Moshe reports getting **over 100 receipt emails in 2 weeks** for random other donors.
- He escalated to YeshInvoice directly on 2026-06-16. YeshInvoice was dismissive on 6/22, and again dismissive to us on 7/2 17:39.
- Then at **7/2 17:40 (one minute later)** YeshInvoice replied to Moshe: *"אנחנו דיברנו עם בעלי העמותה ננסה לראות מי הפיק מסמכים ואיך. נעדכן אתכם בממצאים"* — publicly committing to investigate.

### 2. Eli Lopez (`elilopez100@gmail.com`)
- **NOT in our donor DB** at all.
- Emailed us 2026-06-30 with subject *"קיבלתי קבלה בלי סעיף 46 - למה?"* ("I got a receipt without Section 46 — why?").
- Israeli donor · complaint is that the receipt lacks tax-deductible §46 status.
- Possible fix: YeshInvoice account isn't flagged as a §46 organization, or the docType used by whoever created the receipt isn't the §46 variant.

## Smoking-gun example — docNumber 1640

Our webhook received this event on **2026-07-01 14:25**:
```json
{
  "docNumber":     "1640",
  "customerName":  "David Benamoor",
  "customerID":    5950026,
  "customerEmail": "moshebc@cohenarnold.com",
  "uniqueKeyApi":  "Z1_84143",
  "price":         53.92,
  "currency":      "USD"
}
```
Customer name says **David Benamoor**, but the email is **Moshe Broner's**. And the `Z1_` prefix says it was created via the third-party API user, not us. So Swiftech (or whoever owns Z1_) has a customer record with the wrong email attached — and every receipt for that record goes to Moshe.

## What YeshInvoice has said so far — verbatim

**2026-06-22 07:15** (YeshInvoice → Moshe, dismissive):
> היי משה, לא ידוע לנו על בעיה כזאת או אחרת. אולי הלקוח ביש חשבונית שולח אליך אתצ המסמך כל פעם

**2026-07-02 17:39** (YeshInvoice → us, blaming us):
> היי מנחם, בצד שלנו אין משהו שקשור לבלבול. בסופו של דבר יש מפתחות ואיתם יוצרים מסמכים, במידה ויש גורם שעלה על המפתחות שלהם או יצא מפתחות חדשים לנו בתור פלטפורמה אין איך לחסום, אתם חייבים בצד שלכם לשמור הכל בצורה מוצפנת ואחראית. אנחנו ננסה לראות על מה מדובר וכמובן נעדכן

**2026-07-02 17:40** (YeshInvoice → Moshe, softer, publicly committing):
> היי משה, אנחנו דיברנו עם בעלי העמותה ננסה לראות מי הפיק מסמכים ואיך. נעדכן אתכם בממצאים

## What we already drafted — DON'T SEND YET

I already drafted a firm Hebrew follow-up rebutting YeshInvoice's "someone stole your keys" theory and asking specifically for the owner of `Z1_` and the origin of docNumber 1640. **It's in MK's mkantor@mkantor.com inbox as a PREVIEW/DRAFT** (subject: `[DRAFT for review] Firm follow-up to YeshInvoice — technical rebuttal`). MK hasn't approved it yet.

Do NOT send that letter until MK has reviewed. But you can use its content as a reference for the technical rebuttal.

---

## What you need to do (GUI Claude, browser access)

1. **Log into the YeshInvoice portal** (`https://user.yeshinvoice.co.il` or wherever the MK credentials work). MK has the login. Ask him for the password before you start.
2. **Look up the customer record whose email is `moshebc@cohenarnold.com`** in the portal. Note:
   - What name is on that customer record? (Should probably NOT be Moshe Broner)
   - When was it created? By which user?
   - How many docs have been issued to that customer?
3. **Look up docNumber 1640** in the portal. Note:
   - Who is `customerID: 5950026` (David Benamoor)? Is that a separate customer record, or the same as the Moshe-email one?
   - Which API user created it (should say `Z1_84143` or similar)
4. **Look at the account's API users list** (usually under Settings → API or Integrations):
   - Confirm both `Z1_...` and `Z2_...` prefixes exist as separate API users
   - Note the name / owner / creation date of the `Z1_` user
   - Ideally take a screenshot
5. **Look at the account's §46 (סעיף 46) status** under Settings → Account:
   - Is the account flagged as a `מוסד ציבורי` for §46 purposes?
   - If yes but Eli's doc didn't show it — that means the doc was created with the wrong `docType`. YeshInvoice's `docType = 400` is the §46 receipt variant; other docTypes don't include it.
6. **Screenshot everything** you find, save under `/var/www/matat/uploads/yeshinvoice_portal/` on the server (or paste inline — but keep for the record).

## When you're done — how to update me

Write your findings to `/var/www/matat/handoffyesh-response.md` with:

- **Who owns the `Z1_` API user** (from step 4)
- **Whether the `moshebc@cohenarnold.com` customer record exists in the portal, what name is on it**, and how many docs were issued to it (step 2)
- **Whether docNumber 1640's customer record is separate from Moshe's** (step 3)
- **§46 status of the account** (step 5)
- **Path(s) to the screenshots**
- **Any other surprise** you noticed

Then message MK to invoke me (server-side Claude) — I'll read `handoffyesh-response.md`, decide whether to send the drafted follow-up (with additions), or write a totally different one based on what you found.

## Quick-reference — where things are on our side

- **Donor #7 in DB** — Moshe Broner, `moshebc@cohenarnold.com`, UK
- **Inbox provider** — Microsoft Graph, mailbox `support@matatmordechai.org`
- **Webhook code** — `/var/www/matat/app/blueprints/webhook/routes.py`, function `_handle_yeshinvoice_webhook` around line 1103
- **YeshInvoice service module** — `/var/www/matat/app/services/yeshinvoice_service.py` (this is where OUR `Z2_` docs are created; NOT the source of the mystery docs)
- **Our webhook forward** — hardcoded target `https://seq.swiftech.co.il/yesh/mm/doc` and `.../tax`; may want to disable this once we've confirmed the Swiftech relationship
- **The draft response** — in MK's `mkantor@mkantor.com` inbox, subject starts `[DRAFT for review]`, sent 2026-07-02 19:17 UTC
- **journalctl for webhook events** — `sudo journalctl -u matat --since "3 days ago" | grep yeshinvoice`

## Reminders

- **Don't restart matat without graceful drain** — operators are charging cards live. Use `stop → wait for inactive → start`, not `restart`.
- **Don't touch the Swiftech forward URL** in webhook code until we've confirmed with MK and YeshInvoice who owns Z1_. It may be the only way we're preserving the audit trail for the other party.
- **All Hebrew wording in Moshe's chain has been read** — full timeline is in this doc. If you want the raw messages, they're queryable via the Graph API against `support@matatmordechai.org` with the search terms in `[handoff read-back]` script that follows.

## Handy read-back script (for you or MK)

```bash
cd /var/www/matat && source venv/bin/activate && PYTHONPATH=/var/www/matat python - <<'EOF'
"""List every inbox message related to this issue, oldest first."""
import requests
from app import create_app
from app.models.email_inbox_provider import EmailInboxProvider
from app.services.email.microsoft_graph_inbox import MicrosoftGraphInbox, GRAPH_BASE_URL

app = create_app()
with app.app_context():
    row = EmailInboxProvider.query.filter_by(code='msgraph', enabled=True).first()
    inbox = MicrosoftGraphInbox(row)
    tok = inbox._get_access_token()['access_token']
    H = {'Authorization': f'Bearer {tok}'}
    seen = {}
    for q in ['moshebc@cohenarnold.com', 'moshebronercohen', 'yeshinvoice',
              'קבלה לתרומה', 'brinkmann', 'ברינקמן', 'elilopez', 'סעיף 46']:
        url = f'{GRAPH_BASE_URL}/users/{inbox._mailbox()}/messages?$search="{q}"&$top=25'
        for m in requests.get(url, headers=H, timeout=30).json().get('value', []):
            seen[m['id']] = m
    for m in sorted(seen.values(), key=lambda x: x.get('receivedDateTime', '')):
        print(m.get('receivedDateTime'), '·',
              m.get('from', {}).get('emailAddress', {}).get('address', '?'), '·',
              (m.get('subject') or '')[:80])
EOF
```

Good luck. — Server-side Claude
