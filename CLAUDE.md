# Matat Mordechai Implementation Guide

## Claude Workflow (IMPORTANT)
**Before every git commit, you MUST:**
1. Update the **Changelog** section at the bottom of this file with a summary of changes
2. Update any relevant sections if new features/models/routes were added
3. Include the date (format: YYYY-MM-DD) and brief bullet points of what changed

This ensures all changes are documented for future sessions.

## Tech Stack
- **Backend:** Flask (Python 3.x)
- **Database:** MySQL (using SQLAlchemy with Alembic migrations)
- **PDFs:** WeasyPrint (for Hebrew RTL support)
- **Payments:** Multi-processor system (Stripe, Nedarim Plus) with table-driven routing
- **Email:** Mailtrap API (production), SendGrid (fallback), SMTP (fallback)
- **SMS:** Twilio
- **Web Server:** Gunicorn (port 5050) behind Caddy reverse proxy
- **Server:** 178.128.83.220 (DigitalOcean SGP1), deployed at `/var/www/matat`
- **Database Admin:** Adminer at `db.matatmordechai.org` via Caddy + PHP-FPM

## Application Structure
```
app/
├── blueprints/
│   ├── admin/       # Admin dashboard, salespersons, donations, donors, campaigns, receipts, settings
│   ├── auth/        # Login, logout, password management
│   ├── claude/      # Claude session tracking, screenshot uploads, ttyd terminal
│   ├── donate/      # Public donation pages
│   ├── salesperson/ # Salesperson dashboard, phone entry, links, commissions
│   ├── upload/      # File upload tool for migrations
│   ├── webhook/     # Stripe webhook handlers
│   └── ztorm/       # ZTorm Portal (Access-lookalike donation management)
├── models/          # SQLAlchemy models
├── services/        # Business logic (payment/, email, pdf, receipts)
│   ├── ztorm/       # ZTorm business logic (donation, payment, receipt, accounting, validation, email, ezcount)
│   └── payment/     # Payment processors (shva, base, router)
├── templates/       # Jinja2 templates
├── i18n/           # Translation files (en.json, he.json)
└── utils/          # Helpers (i18n, etc.)
```

## Coding Standards
- **Structure:** Use the Blueprint pattern for all modules.
- **Soft Deletes:** Use `deleted_at` timestamp for all primary models. Never hard-delete.
- **Money:** Always store amounts in cents (integers) to match Stripe's API.
- **I18n:** Use JSON files in `app/i18n/` for all UI strings. Use `{{ t('key.subkey') }}` in templates.
- **Receipts:** Generation must be atomic using a DB transaction and the `receipt_counter` table.
- **Test Mode:** Donors created during Stripe test mode have `test=True` flag.

## Key Features
- **Admin Dashboard:** Overview stats, salesperson management, commission processing
- **Donor Management:** List/search donors, view donation history, toggle test/real status
- **Donor Linking:** Link existing donors to donation links via external_id field
- **Donation Tracking:** All donations linked to salesperson referral codes
- **Receipt System:** Auto-generated PDF receipts with sequential numbering, email delivery
- **Commission System:** Automatic calculation based on salesperson tier, bulk payment
- **Email Templates:** Custom email templates for donation links (EN/HE, global or personal)
- **Language Toggle:** Cookie-based EN/HE switching on all pages
- **Email BCC:** All outgoing emails BCC'd to support@matatmordechai.org
- **Claude Session Tracking:** Track Claude coding sessions with screenshots and notes
- **File Upload Tool:** Token-protected upload page for migration files

## Critical Commands
- **Start Server:** `sudo systemctl start matat`
- **Restart Server:** `sudo systemctl restart matat`
- **Check Status:** `sudo systemctl status matat`
- **View Logs:** `sudo journalctl -u matat -f`
- **Reload Caddy:** `sudo systemctl reload caddy`
- **Migrations:** `flask db migrate -m "description"` followed by `flask db upgrade`
- **Seeding:** `python seed.py` to create initial admin and config
- **Import Donors:** `flask import-donors unified_payments.csv` (creates Donor records)
- **Import Donations:** `flask import-donations unified_payments.csv` (imports full donation history)
- **RTL:** Hebrew templates must include `dir="rtl"` and use the 'Assistant' font.
- **Stripe Payments:** Card element always uses `locale: 'en'` for English-only payment forms.

## Environment Variables
```
DATABASE_URL=mysql+pymysql://user:pass@localhost/matat
SECRET_KEY=<random-secret>
STRIPE_PUBLISHABLE_KEY_LIVE=pk_live_xxx
STRIPE_SECRET_KEY_LIVE=sk_live_xxx
STRIPE_PUBLISHABLE_KEY_TEST=pk_test_xxx
STRIPE_SECRET_KEY_TEST=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

## Database Settings (ConfigSettings table)
- `stripe_mode`: 'test' or 'live'
- `mailtrap_token`: Mailtrap API token for email sending
- `smtp_host`, `smtp_port`, etc.: SMTP fallback settings
- `email_from_name`, `email_from_address`: Sender info

## Production URLs
- Main site: https://matatmordechai.org
- Admin: https://matatmordechai.org/admin
- Donation page: https://matatmordechai.org/donate
- Database admin: https://db.matatmordechai.org

## Important Notes
- **Site URL:** Use matatmordechai.org (NOT donate.matatmordechai.org)
- **Email BCC:** All outgoing emails automatically BCC'd to support@matatmordechai.org
- **Language Toggle:** Cookie-based, accessible on all authenticated pages
- **Translation Files:** `app/i18n/en.json` and `app/i18n/he.json` contain all UI strings
- **Stripe Card Element:** Always displayed in English regardless of page language

## Claude Session Tracking (`/claude`)
Web interface for managing Claude coding sessions with embedded terminal.

**Routes:**
- `/claude` - Main chat interface with embedded ttyd terminal
- `/claude/sessions` - List all sessions
- `/claude/session/<id>` - View session details
- `/claude/config` - Admin config (tmux session selection)
- `/claude/screenshot/upload` - Upload/paste screenshots

**Models:**
- `ClaudeSession` - Tracks sessions (user, start/end time, purpose, notes)
- `ClaudeScreenshot` - Screenshots uploaded during sessions
- `ClaudeConfig` - Key-value config storage

**Services:**
- `matat.service` - Gunicorn on port 5050 (3 workers, 120s timeout)
- `ttyd-matat.service` - ttyd on port 7681 with `--base-path /help`, attaching to tmux session `matat`
- `caddy.service` - Reverse proxy with auto-HTTPS

**Widget:**
- Floating chat widget included on all admin pages via `components/claude_widget.html`
- Features: minimize/maximize, drag to move, screenshot paste (Ctrl+V), resize

## File Upload Tool (`/upload`)
Token-protected file upload page for migration files (Access databases, spreadsheets, etc.).

**Access:** Token required (`matat2026`)
**Location:** Files saved to `/var/www/matat/uploads/`
**Allowed types:** .accdb, .mdb, .xlsx, .csv, .sql, .zip, .pdf, .py, etc. (max 500MB)

## Email Templates
Custom email templates for donation link emails.

**Model:** `EmailTemplate`
- `name` - Template name
- `language` - 'en' or 'he'
- `subject` - Email subject line
- `body` - Email body (supports placeholders)
- `is_global` - Available to all salespersons if true
- `created_by` - User who created the template

## Donor Linking
Link existing donors to donation links using external_id.

**Donor Model Extensions:**
- `external_id` - External reference ID for linking
- `find_by_external_id()` - Class method to find donors by external ID
- `merge_with()` - Method to merge duplicate donor records

## Multi-Processor Payment System
Table-driven payment routing supporting 8 processors. Designed for multi-platform deployment where each client enables different processors.

**Models:**
- `PaymentProcessor` - Processor configuration (code, credentials, currencies, countries, fees)
- `PaymentRoutingRule` - Rules for routing payments (by currency, country, amount, donation type)

**Service Package:** `app/services/payment/`
```
payment/
├── __init__.py              # Exports all processors
├── base.py                  # Abstract BasePaymentProcessor class
├── router.py                # PaymentRouter and route_payment()
├── stripe_processor.py      # Stripe (international)
├── nedarim_processor.py     # Nedarim Plus (Israeli nonprofits)
├── cardcom_processor.py     # CardCom (auto Section 46 receipts!)
├── grow_processor.py        # Grow/Meshulam (most popular Israel)
├── tranzila_processor.py    # Tranzila (oldest Israel gateway)
├── payme_processor.py       # PayMe (modern, hosted fields)
├── icount_processor.py      # iCount (payment + invoicing)
├── easycard_processor.py    # EasyCard (PCI Level 1)
├── donorsfund_processor.py  # The Donors Fund (DAF)
├── matbia_processor.py      # Matbia charity cards
└── chariot_processor.py     # Chariot/DAFpay (1,151+ DAF providers)
```

**Credit Card Processors:**

| Code | Name | Best For | Key Features |
|------|------|----------|--------------|
| `stripe` | Stripe | International | Stripe Elements, USD/EUR/ILS, recurring |
| `nedarim` | Nedarim Plus | Israeli nonprofits | iframe PostMessage, Bit, standing orders |
| `cardcom` | CardCom | Israeli nonprofits | **Auto Section 46 receipts**, webhook is GET! |
| `grow` | Grow/Meshulam | Israel general | Most popular, Bit/Apple/Google Pay, form-data NOT JSON |
| `tranzila` | Tranzila | Established | Oldest, handshake verification, J4/J5 modes |
| `payme` | PayMe | Modern apps | Hosted fields, amounts in agorot |
| `icount` | iCount | Accounting | Payment + invoicing combined |
| `easycard` | EasyCard | High security | PCI Level 1, Bit, Google Pay |

**DAF / Charity Card Processors:**

| Code | Name | Best For | Key Features |
|------|------|----------|--------------|
| `donors_fund` | The Donors Fund | Jewish DAF | Username+PIN or Card+CVV, 2.9% fee |
| `matbia` | Matbia | Orthodox community | NFC charity cards, recurring schedules |
| `chariot` | DAFpay (Chariot) | Universal DAF | **1,151+ providers**: OJC, JCF, Fidelity, Schwab |

**DAF Important Notes:**
- DAF donations do NOT generate tax receipts (donor has receipt from DAF provider)
- Send thank-you acknowledgment only, NOT a tax receipt
- `is_daf_donation=True` and `daf_provider` fields track DAF source

**Donation Model Extensions (generic for all processors):**
- `payment_processor` - Which processor: 'stripe', 'nedarim', 'cardcom', etc.
- `processor_transaction_id` - Generic transaction ID
- `processor_confirmation` - Authorization/confirmation code
- `processor_token` - Saved payment token for recurring
- `processor_recurring_id` - Recurring/subscription/keva ID
- `processor_fee` / `processor_fee_currency` - Processing fee
- `processor_metadata` - JSON for processor-specific data
- `processor_receipt_url` - External receipt URL (CardCom, iCount)
- `routing_reason` - Why this processor was selected
- `donor_country` - Donor's country for routing

**Routing Logic:**
1. Check routing rules in priority order (lower = higher priority)
2. Fall back to best available processor based on currency/country
3. ILS currency or IL country prefers Israeli processors
4. Default to Stripe if no match

**BasePaymentProcessor Interface:**
```python
create_payment()      # Create payment/intent
get_client_config()   # Frontend config (iframe URL, publishable key)
process_webhook()     # Verify and parse webhook
refund()              # Process refund
get_transaction()     # Retrieve transaction details
charge_token()        # Charge saved token (recurring)
supports_currency()   # Check currency support
supports_country()    # Check country support
estimate_fee()        # Estimate processing fee
```

**Seeding:** `python seed_processors.py` creates default processors and routing rules

**Current Status:**
- Stripe (enabled) - Ready
- Nedarim Plus (enabled) - MosadId 7007385, API sync every 10min, iframe auth issue pending
- CardCom (disabled) - Awaiting credentials
- Grow (disabled) - Awaiting credentials
- Tranzila (disabled) - Awaiting credentials
- PayMe (disabled) - Awaiting credentials
- iCount (disabled) - Awaiting credentials
- EasyCard (disabled) - Awaiting credentials
- The Donors Fund (disabled) - Awaiting validation_token from support@thedonorsfund.org
- Matbia (disabled) - Awaiting API key from developers.matbia.org
- Chariot/DAFpay (disabled) - Awaiting API key from givechariot.com

**Important Notes:**
- CardCom webhook is GET (not POST!)
- Grow requires approveTransaction() after webhook
- Grow uses form-data NOT JSON
- PayMe amounts are in agorot (smallest unit)
- iCount rate limit: 30 requests/minute
- Nedarim webhook IP: 18.194.219.73
- **DAF donations: Send thank-you email only, NOT a tax receipt** (donor has receipt from DAF)

---

## Changelog

### 2026-04-28 (Weddings nav link: localized to חתונות)
- Added `nav.weddings` translation key (`Weddings` / `חתונות`) to both `en.json` and `he.json`. Both nav-link occurrences in `base.html` (admin and salesperson menus) now use `{{ t('nav.weddings') }}` so Hebrew users see "💍 חתונות" instead of the hardcoded English.

### 2026-04-28 (login: apply user.language_pref as cookie; help widget answers in Hebrew)
- **Bug**: the lang resolver in `app/utils/i18n.py` checks `?lang= → cookie → user.language_pref → 'en'` in that order. So a stale `lang=en` cookie from a prior browser session beat the user's stored `language_pref='he'`, and Hebrew-speaking operators (Sara Gehrlitz `matatmor@gmail.com`) kept landing on the English UI.
- **Fix**: `auth.login` now writes `resp.set_cookie('lang', user.language_pref, max_age=1y, samesite=Lax)` on every successful login. The cookie is overwritten on each fresh login so each user's first page after sign-in matches their profile preference. The user can still flip via the lang-toggle without losing the override.
- **Help widget** (`/claude/chat/send`): system prompt now embeds a `LANGUAGE:` directive derived from `current_user.language_pref`. For `'he'` users the assistant is instructed to **reply in Hebrew** while keeping system feature names (Donations, ZTorm, Reissue, etc.) in English so the user can match the on-screen button. CLAUDE.md docs themselves remain English.
- Note: the cookie is set fresh at login, so existing logged-in sessions with a stale cookie pick up the change after their next login (or after a manual lang-toggle click).

### 2026-04-28 (wedding tracker; user-allowlist nav scoping; print/export tooling)

**New `Wedding` model + `/weddings` blueprint** — replaces an unstructured
Word-doc list of upcoming weddings the org is helping fund (`Assisting the
needy for their weddings` is one of the receipt fund categories):
- Fields: hebrew_date (free-text — `א׳ סיון`, `כ"ה אדר א'`, etc.), optional
  gregorian_date (sort key only — not displayed), groom_name, bride_name,
  hall_name, phone, contact_name, notes, hidden flag, soft delete, audit
  columns. Two migrations: `b1c4a8e2d9f7_add_weddings_table.py` and
  `c7e2d4a9f1b3_weddings_hidden_flag.py`.
- Blueprint at `/weddings`: list (oldest gregorian first; undated rows
  fall to the bottom in entry order), add, edit, hide/unhide,
  soft-delete. Hebrew-RTL templates throughout.
- Toolbar: **Print/PDF**, **Word (.doc)**, **Excel (CSV with UTF-8 BOM)**,
  + a "הצג מוסתרות" checkbox so the operator can revisit hidden rows.
  Print page has a one-click landscape/portrait toggle. Default print
  layout: portrait, 10.5pt body. Landscape: 13pt body — sized for
  elderly-readable output without manual zoom.
- Bulk-loaded the operator's existing list (24 weddings, sample seeded
  via `bulk_weddings.py` — heuristically split contact name from phone).

**User-allowlist nav scoping** (template + blueprint guard):
- The `Weddings` nav-link is hidden — and the `/weddings/*` routes return
  403 — for any user whose `username` isn't in
  `{'admin', 'ggoldblum', 'matatmor@gmail.com'}`. The set is hardcoded in
  both `templates/base.html` and `weddings/routes.py:_WEDDING_USERNAMES`
  so a single source-of-truth update touches both. Easier than adding a
  permission row for one screen used by 3 people.

**User update**: salesperson `0527639985` renamed to
`matatmor@gmail.com` (שרה גהרליץ) with a new password and
`language_pref='he'`. `is_temp_password` cleared.

**VS Code Remote Tunnel setup doc** (`tools/setup_vscode_tunnel.md`) —
step-by-step instructions for the operator-side Claude to install the
VS Code CLI as a Windows service so the dev (this side) can drive
Claude Code on the operator's PC from any browser via
`https://vscode.dev/tunnel/matat-operator` without disturbing the
operator's Access workflow.

### 2026-04-27 (Reissue: choose YeshInvoice vs Matat email at click time)
- **Reissue** now prompts the operator twice:
  1. "Reissue receipt for {email}?" — Cancel aborts.
  2. "Send via YeshInvoice? OK = YeshInvoice; Cancel = Matat email."
- Server route `POST /admin/donations/<id>/reissue-receipt?via=yesh|matat`:
  - `via=yesh` → calls `yeshinvoice_service.create_receipt(donation, donor)`. Will fail today with a Hebrew validation error until the `createInvoice` payload schema is corrected (still blocked on the YeshInvoice doc panel). Will JSON-error with the API's response so the operator sees what went wrong.
  - `via=matat` (default) → regenerates the local PDF and emails via Mailtrap. **Bypasses the Israel-resident country gate** (`override_country_gate=True`) so an IL donor who never received their Israeli kabala can still get a Matat-branded receipt.
- New `send_receipt_email(..., override_country_gate=False)` arg. Default behaviour unchanged for every other caller (webhook, salesperson resend, etc.); only the Reissue → Matat path passes True.

### 2026-04-27 (Reissue button on donations list)
- New `POST /admin/donations/<id>/reissue-receipt` (login_required, both admin and salesperson can hit it). Forces `regenerate_receipt_pdf(receipt)` from the current template, then `send_receipt_email`. Creates the receipt row first if the donation predates our system. Returns JSON `{success, message, receipt_number}` or `{error}`.
- Orange **"Reissue"** button next to the green **"Resend"** on every row of `/admin/donations`. Use case: donors whose receipts were originally produced on a different platform now need a Matat-branded receipt with the current template (zip code, transaction box, embedded check image, etc.). Resend ships the cached PDF; Reissue rewrites it.
- Confirmation prompt names the donor email; success flips the button to "Sent!" for 2 s. Disabled when the donor has no email on file.

### 2026-04-27 (zip code on receipt; bottom-date = issue date; bulk regen)

**Bug — every US receipt was missing its ZIP code**:
- `receipt_en.html` and `admin/donation_detail.html` both referenced
  `donor.zip_code`, but the `Donor` model field is `donor.zip` (no underscore).
  Jinja silently rendered an empty string for an undefined attribute, so for
  *every* US receipt rendered to date the City line was missing the ZIP.
  Fixed both templates to read `donor.zip` with a `donor.zip_code` fallback
  in case anything else relies on the alias.

**Bug — bottom-of-page date was the check date, not the issue date**:
- An earlier well-intentioned fix made `generate_receipt_pdf` use
  `processor_metadata['payment_date']` as the receipt date when present,
  to avoid a separate "today's date" bug. But the receipt now ALSO has a
  transaction-details box that explicitly shows the check / charge / Zelle
  date in its own column — so the bottom-of-page date was duplicating that
  value, telling the donor the receipt was issued weeks before we actually
  received it (e.g. Khal Beis Aba's receipt was bottom-dated Mar 23 / check
  date but we entered it Apr 22).
- Reverted: `receipt_date = donation.created_at` (the entry/issue
  timestamp). The actual payment date stays in the transaction box.

**Bulk regeneration of past US receipts**:
- New `tools/bulk_regen_us_receipts.py` walks every Receipt whose
  donor.country is US-ish (`US`, `USA`, `United States`, …, plus null /
  empty), re-renders the PDF in place via `regenerate_receipt_pdf`, and
  rewrites stale `pdf_path` values left over from the old `/root/matat/`
  server location. **Does not email**. Supports `--dry-run`.
- Run twice today: once to pick up the zip-code fix, once to pick up the
  bottom-date fix. 86 receipts regenerated each pass, 0 failures.

**Retroactive image attach for donation #981 (Khal Beis Aba)**:
- The original donation was entered without the check image. Today the
  operator re-supplied it; uploaded to
  `/var/www/matat/uploads/check_images/check_2084_kehalbeisaba.jpg`,
  patched into `donation #981.processor_metadata.image_path`, PDF re-
  rendered. Receipt now shows the embedded check under the transaction-
  details table, captioned "A copy of your check is provided below for
  your records."

### 2026-04-27 (receipts: country-based routing + transaction box + image embed; YeshInvoice: real API endpoint discovered)

**Receipt template (`receipt_en.html`)** — restored two sections that an earlier merge stripped:
- **Transaction-details box** below "In Words": three columns —
  *date* / *check #-or-card #-or-reference* / *amount*. Headers swap based on `payment_processor`:
  `DATE OF CHECK` / `DATE OF CHARGE` / `TRANSACTION DATE` and `CHECK NUMBER` / `CARD NUMBER` / `REFERENCE`.
  For card payments, the number column shows `•••• 1234` (last-4 mask).
- **Uploaded image embed** with caption: any check photo / Zelle screenshot / card-receipt slip uploaded
  through Admin → New Check Donation now appears under the table on the receipt PDF, with a
  context-appropriate caption ("A copy of your check / Zelle transaction / card receipt is provided
  below for your records.").
- **`#f_company` finally has CSS positioning** AND only renders when `donor.company_name` differs from
  `donor.full_name|trim`. Previously the bare `<div>` had no `top/left` so it floated to (0,0)
  outside the artwork — visible as a duplicate "Khal Beis Aba" in the page's top-left margin.

**Manual-donation form (`new_check_donation.html` + `routes.py`)**:
- **Currency picker** (USD / ILS) — was hardcoded to `usd`. Donations entered as ILS persist as ILS.
- **Country dropdown** replaces the free-text input. Top of list: Israel, USA, UK, Canada (where our
  donors live). Then a curated alphabetical list of ~40 other countries plus an "Other / not listed"
  fallback. JS auto-flips country to match currency (ILS → IL, USD → US) but only when the operator
  hasn't manually overridden — `lastAutoCountry` tracks the previous default.
- **Card last-4** is captured: when `payment_method == 'credit_card'`, we read `card_brand` and
  `card_last4` from the form (or, as a fallback, parse digits out of the reference field) and store
  them on `donation.payment_method_type / brand / last4` so the receipt template renders
  "Credit Card ending in 1234".

**Receipt routing (`email_service.py send_receipt_email`)**:
- **Country-based**, replacing the older USD-only currency gate. Logic: if
  `donor.country in ('IL','ISRAEL','ISR','ISRA')` → skip the matatmordechai.org email (Israeli donors
  get their kabala through YeshInvoice). **Everyone else** — US, UK, Canada, rest of world — gets the
  US 501(c)(3) receipt email.
- Bonus fix: BCC now deduplicates against the To: address. Previously, sending TO
  `support@matatmordechai.org` failed at Mailtrap with `"address ... is not unique in the request"`
  because the same address was auto-BCC'd. Fixed in the Mailtrap-payload builder.

**YeshInvoice service (`yeshinvoice_service.py`) — base URL & endpoint corrections**:
- **Real public API endpoint** (discovered by reading `https://user.yeshinvoice.co.il/api/doc`): base
  URL is `https://api.yeshinvoice.co.il/api/user/`, NOT `/api/v1/`. The single public action is
  `createInvoice`. The `/api/v1/createDocument`, `/api/v1/getAccountInfo`, and
  `/api/v1/createOrUpdateCustomer` we were calling don't exist.
- **`API_BASE_URL`** updated, **`createDocument` → `createInvoice`** in `create_receipt`.
- **`test_connection()`** rewritten: there is no dedicated ping endpoint, so we send `createInvoice`
  with body `{UserKey, SecretKey}` only and read the Hebrew error message —
  `"מפתח SECRET KEY לא חוקי"` ⇒ auth failed; `"אנא הזן שם הלקוח/בית העסק"` ⇒ auth passed (it's now
  asking for a customer name). Verified working with real keys.
- **`find_or_create_customer()` and `get_document()` stubbed** — the public API doesn't expose these
  endpoints. Customers are auto-created on `createInvoice` based on the customer fields we send;
  document retrieval requires the internal `/api/v1.1/` API which uses login-session auth we don't
  have.
- **NOT YET WIRED** to the live ILS donation flow. To complete: copy the full `createInvoice` body
  from the YeshInvoice docs (`Documents → Create Document` panel) and rewrite `create_receipt()` to
  send all required fields. The `CustomerName` field name we tried doesn't work — needs the real
  field name from the docs.

**Receipt PDF preview tooling**:
- `tools/preview_receipt_local.py` (Windows) — renders the receipt template via headless Chrome
  (`--print-to-pdf`) so the editor can iterate on layout without WeasyPrint/GTK on Windows.
  Output: `F:/matat_git/preview.pdf` and `app/static/preview.pdf`. Test mode via argv:
  `python tools/preview_receipt_local.py en 1000 check` (or `zelle`, or `card`).
- `tools/render_receipt_preview.py` (server-side) — same idea but via WeasyPrint, for confirming
  the live render matches the local preview before deploying.

### 2026-04-27 (receipt date honors the operator-entered payment date)
- **Bug**: the manual donation form has a "Check date / Charge date / Transaction date" field that saves to `donation.processor_metadata['payment_date']` (ISO YYYY-MM-DD) — but `generate_receipt_pdf` ignored it and printed `donation.created_at` (the timestamp the operator filled in the form). Receipts came out dated "today" instead of the actual payment date.
- **Fix**: `generate_receipt_pdf` now reads `processor_metadata.payment_date` first; falls back to `created_at` when missing or malformed. Works for both EN (`Month DD, YYYY`) and HE (`DD/MM/YYYY`) formats. Regenerated PDFs for the three most recent manual donations.

### 2026-04-27 (PDF receipt language follows currency, not country)
- **Bug**: an operator typed `USD` into the manual-donation form's Country field. `get_receipt_language()` did not recognise `'USD'` as a US country, so it fell through to the donor's `language_pref='he'` and generated the receipt **PDF** in Hebrew. The email body was already English (post the earlier currency-gate fix), but the attached PDF was Hebrew — donor received a wrong-language receipt.
- **Fix**: `get_receipt_language(donor, donation=None)` now treats currency as the strongest signal — `donation.currency == 'USD'` always returns `'en'`, regardless of `donor.country` or `donor.language_pref`. Both callers (`create_receipt_atomic`, `regenerate_receipt_pdf`) pass `donation=`.
- Patched the affected donor's record (`country: 'USD' -> 'US'`) and regenerated the PDF for receipt MM-2026-00388.

### 2026-04-27 (manual-donation form: Credit Card option, recording-only)
- New `Credit Card` option added to the Payment-method dropdown on `/admin/donations/new-check`. **Records** an off-platform charge (terminal / mobile reader) — does **not** run a live charge.
- Seeded a new `manual_card` PaymentProcessor (priority 12, between Shva and Stripe), so manual CC entries get their own tab and don't get conflated with real Stripe transactions.
- When the operator picks "Credit Card", a yellow panel reveals: Card brand (Visa / MC / Amex / Discover / Other) and Last 4 digits. The existing **Reference** field relabels to "Transaction / authorization #" and the **Date** field to "Charge date".
- Server: maps `payment_method='credit_card'` → `payment_processor='manual_card'` and writes `payment_method_type='card'` + `payment_method_brand` + `payment_method_last4`. The receipt templates already render this as **"Credit Card ending in 1234"** thanks to the existing `payment_method_type == 'card'` branch.
- Translations: ~14 new keys under `manual_donation.*` in both `en.json` and `he.json` (method label, brand options, last-4, auth code hints).

### 2026-04-27 (manual-donation form: full Hebrew translation + RTL)
- Added `nav.manual_donation` and a complete `manual_donation.*` block (~50 keys) to both `app/i18n/en.json` and `app/i18n/he.json`. Includes title/subtitle, donor-lookup placeholder & hint, donor section, full mailing-address section, payment section (method, amount, check #/Zelle reference, dates, memo), receipt-number override, image upload + paste, BCC, extra attachments, save/cancel.
- `app/templates/admin/new_check_donation.html`: replaced every hardcoded English label/placeholder/hint with `t('manual_donation.*')`. Page wrapper gets `dir="rtl"` when `lang == 'he'`. Method-swap JS now reads strings from a `window.MD_I18N` block injected by Jinja so the dynamic relabeling (Check↔Zelle) is also localized.
- Salesperson nav and admin "+ Manual Donation" button now use `t('nav.manual_donation')` so they read "+ צ'ק / Zelle" in Hebrew, "+ Check / Zelle" in English.

### 2026-04-27 (open charging flows to salespersons)
- `/admin/donations/new-check` and `/admin/api/donors/search` switched from `@admin_required` → `@login_required`. Salespersons can now record check/Zelle donations and use the donor lookup.
- The form auto-credits the salesperson on submit when filled by a salesperson (`salesperson_id = current_user.id`); admins still default to no salesperson.
- Cancel link and post-submit redirect now route to `/salesperson/my-donations` for salespersons (avoiding a 403 on `/admin/donations`).
- Nav: added "+ Check / Zelle" link in the salesperson menu (alongside Donations / Send Link / Phone Entry / ZTorm).
- Note: the existing CC charging endpoints (`/salesperson/phone-entry` for Stripe, `/ztorm/charge` for Shva) were already login-gated for any role; only the manual donation form was admin-only.

### 2026-04-22 (check image: paste from clipboard + live preview)
- **Manual-donation form — check-image upload** accepts clipboard images now: click in the upload box and press Ctrl/Cmd+V, or click the green **"Paste from clipboard"** button (uses the async Clipboard API; HTTPS-only).
- Pasted blobs are wrapped in a `File` and assigned to the `check_image` input via a `DataTransfer`, so the server POST path is unchanged.
- A thumbnail preview now appears under the input as soon as a file is selected or pasted, so the operator can verify the right image before submit.
- Global paste listener is scoped: if the user is typing in another input, their paste is not hijacked.

### 2026-04-22 (USD receipt emails always in English)
- **Bug**: `send_receipt_email` defaulted the email body language to `donor.language_pref`, so a USD receipt addressed to a donor with `language_pref='he'` shipped the email in Hebrew even though the PDF itself (which keys off `donor.country`) was in English.
- **Fix**: the currency gate at the top of the function already guarantees only USD donations reach the body-rendering step; after it, language defaults to `'en'` unconditionally. An explicit `language=` arg from a test caller can still force Hebrew.

### 2026-04-22 (manual donation: optional BCC)
- **`send_email(..., extra_bcc=None)`** and **`send_receipt_email(..., extra_bcc=None)`**: optional list of BCC addresses added alongside the fixed `support@matatmordechai.org` audit copy.
- Plumbed through all four providers: `_send_smtp`, `_send_mailtrap`, `_send_sendgrid`, `_send_activetrail`. Each dedupes against the audit address so the BCC list never has duplicates.
- **Manual-donation form**: new "BCC (optional)" text input. Accepts comma- (or semicolon-) separated addresses. Invalid entries are silently skipped; the rest are attached to the outgoing receipt email. The input group dims when "Email the receipt" is off. Success flash now summarises attachment count and BCC list.

### 2026-04-22 (manual donation: extra attachments for the receipt email)
- **`send_receipt_email(..., extra_attachments=None)`**: new optional list of filesystem paths. Each existing path is appended to the receipt PDF when building the outgoing email. Downstream (`send_email`, `_send_smtp`, `_send_mailtrap`, `_send_activetrail`) already accepted multi-attachment lists, so no changes required there.
- **Manual-donation form**: new multi-file input "Attach file(s) to the email" right below the "Email the receipt" checkbox. Files are saved to `/var/www/matat/uploads/email_attachments/<donor_id>_<rand>_<name>`, collected into the donation's `processor_metadata.email_attachments` for audit, and forwarded to `send_receipt_email` as `extra_attachments`.
- The attachment group visually dims when the "Email the receipt" box is unchecked (JS `syncAttachDim()`), and the success flash reports attachment count.

### 2026-04-22 (company-only donations render company as primary receipt name)
- `Donor.receipt_primary_name` property: returns `full_name` when a personal name exists, else falls back to `company_name`. `Donor.has_personal_name` returns `True` only when first/last are non-empty.
- All four receipt templates now use `donor.receipt_primary_name` for the top name line. The second company line renders only when the donor has *both* a personal name and a company — so company-only donations don't duplicate the name.
- Manual-donation form: first/last-name inputs are no longer `required`. Validation now demands either (first AND last) OR a company name; hint text explains the combinations. Donor creation uses empty strings for missing first/last (columns are NOT NULL).

### 2026-04-22 (donor: company_name + receipt display)
- New `Donor.company_name` column (`VARCHAR(200)`, nullable). Migrations `41a1612f978f` (gemach head, back-applied) → `963024d69d5c` (merge) → `3561cad40c40` (add_company_name_to_donors).
- Manual-donation form (`/admin/donations/new-check`): added "Company name" field under the last-name row; included in the donor lookup API and auto-filled when picking an existing donor; shown on the lookup dropdown as a sub-line.
- All four receipt templates now render the company line under the donor's name when present: PDF EN (`<div class="fld" id="f_company">`), PDF HE (`<div class="info-label">:חברה</div>`), admin print, salesperson print.

### 2026-04-22 (manual donation: optional custom receipt number)
- **`create_receipt_atomic(donation, donor, override_number=None)`**: new optional arg; when supplied, uses that exact receipt number and does **not** increment the sequential counter. Raises `ValueError` if the number is already in use. Use case: backfilling paper receipts or matching a legacy system while running both systems in parallel.
- **Manual donation form** (`/admin/donations/new-check`): new "Receipt number (optional)" input. Blank = next auto-generated number (default), else the typed value is used verbatim.
- Duplicate number returns the operator to the form with a flash error; the donation is rolled back.

### 2026-04-22 (receipt payment-method: "Credit Card ending in 1234" for card donations)
- Changed all four receipt templates to render card donations as **"Credit Card ending in 1234"** instead of the brand name ("Visa ending in 1234"). ACH bank donations read **"ACH ending in 1234"**.
- Regenerated 83 stored PDFs for existing card donations so their files match the new wording.

### 2026-04-22 (receipt payment-method: show Check / Zelle instead of "Credit Card")
- **Fix**: receipts rendered as "Credit Card" for manual donations because four templates hardcoded that label for the `payment_method_type is null` branch:
  - `app/templates/pdf/receipt_en.html`, `pdf/receipt_he.html` (PDF)
  - `app/templates/admin/receipt_print.html`, `salesperson/receipt_print.html` (print views)
- Added explicit branches in all four: `payment_processor == 'check'` → "Check #<ref>", `'zelle'` → "Zelle (ref …)", falling back to the existing card/ACH/default logic for legacy donations.
- Regenerated PDFs for all existing `check` / `zelle` donations so their stored receipt files match the new label.

### 2026-04-22 (manual-donation form: donor lookup + address fields)
- **Donor lookup added at the top of `/admin/donations/new-check`** — live search as you type (2+ chars) against name / email / phone; picking a match pre-fills every donor field (name, email, phone, full mailing address). A "clear" link and a green "selected" badge show the pick state.
- **Full mailing address** fields added to match the receipt layout: `address_line1`, `address_line2`, `city`, `state`, `zip`, `country` (default US). Saved directly onto the `Donor` record — so the receipt renders the right address.
- **Backend**: new JSON endpoint `/admin/api/donors/search?q=...` returns up to 15 matches. The `new_check_donation` POST handler now accepts `donor_id` (from the picker), prefers it for donor matching, and updates donor name + address on save (never overwrites an existing real email).

### 2026-04-22 (manual-donation form: Check + Zelle + image upload)
- **Form simplified and broadened** at `/admin/donations/new-check`:
  - Removed Teudat Zehut and currency picker (always USD)
  - Added payment-method dropdown: **Check** or **Zelle**; reference-# and date labels relabel dynamically
  - Optional **image upload** (check photo / Zelle screenshot); files saved to `/var/www/matat/uploads/check_images/`, path stored in `processor_metadata.image_path`
  - Submit sets `payment_processor='check'` or `'zelle'` and redirects back to the matching processor tab
- Seeded `zelle` as an enabled PaymentProcessor (priority 16), so a Zelle tab auto-renders beside Check
- Button on `/admin/donations` renamed from "+ Check Donation" to "+ Manual Donation"

### 2026-04-22 (check-donation tab)
- **Check donation tab + entry form:**
  - Seeded `check` as an enabled PaymentProcessor (priority 15), so a **Check** tab auto-renders in the donations-page processor row
  - New route `/admin/donations/new-check` (GET/POST) with form for donor (name/email/phone/TZ), amount/currency, check # and date, memo
  - Reuses existing donor by email → name; falls back to a new donor (generates a placeholder email if none supplied)
  - Stores the check number in `processor_confirmation` and check_date / memo in `processor_metadata` JSON
  - Issues a receipt via `create_receipt_atomic` in the same transaction; "Email receipt now" checkbox optionally fires `send_receipt_email`
  - "+ Check Donation" button added to `/admin/donations`

### 2026-04-22 (ticket 4 — interactive members search)
- **Ticket 4 fix on `/gemach/members`** (operator feedback: "I put in 3321 but it did not show up anything I want the search to be interactive"): all three חיפוש-dialog fields (מס׳ כרטיס / שם פרטי / שם משפחה) now filter the grid live as the operator types — no Enter, no reload. Debounced 180 ms, last-request-wins, URL reflects current filters via `history.replaceState` so refresh / bookmark still works.
- **How it's wired:**
  - Results block (grid + action bar + pager) extracted to `app/templates/gemach/_members_results.html`.
  - `members()` in `app/blueprints/gemach/routes.py` returns that partial when `?partial=1`, else the full page.
  - `app/templates/gemach/members.html` wraps the results in `<div id="hs-results">` and has a ~30-line inline `<script>` that fetches the partial on each keystroke and swaps `innerHTML`.
- **Branch:** `fix/interactive-members-search` (off master) so the user can merge cleanly from the dev laptop; not on `operator-feedback-widget` because this fix applies everywhere, not just the operator PC.

### 2026-04-19 (ticket 3 — loans search + Access-sync UI + detail polish)
- **Ticket 3 fix on `/gemach/loans`** (operator feedback): free-text search bar (matches last_name, first_name, teudat_zehut, gmach_card_no, gmach_num_hork, or account_number); new `מס׳ כרטיס` column showing each loan's borrowing member card number; search preserved across pagination.
- **Gemach Access-sync UI**: new `/gemach/sync-access` page (`app/blueprints/gemach/sync.py` + `app/templates/gemach/sync_access.html`) runs `sync_live_data.bat` in a background thread, streams live output via polling, persists each run to `instance/sync_logs/<timestamp>_<ok|fail>.log`, and shows history. Switchboard gained tile #7 "סנכרון נתונים מ-Access".
- **Member detail polish** (`app/templates/gemach/member_detail.html`, `routes.py`): format transaction dates as DD/MM/YYYY; display oldest-first inside the most-recent-100 window.

### 2026-04-19 (operator-PC polish)
- **Sandbox auto-login** (`/sandbox-login` in `app/blueprints/auth/routes.py`): new route, gated on `is_sandbox()` so it returns 404 in production. Logs in the `admin` user, sets `lang=he` cookie, redirects to `/gemach/` — lets the non-technical operator double-click the desktop shortcut and land directly on the Hebrew Gemach switchboard with no login screen.
- **Desktop launcher target change** (`desktop.py`): opens `/sandbox-login` instead of `/login` so the auto-login + language + landing page happen on startup.
- **start.bat close behavior:** replaced `pause` at end of `start.bat` with `timeout /t 5 /nobreak` so the console window auto-closes 5s after the app exits (no keypress required).
- **Claude ttyd widget hidden in sandbox:** `app/templates/base.html`, `gemach_base.html`, `ztorm_base.html` now wrap `components/claude_widget.html` in `{% if not sandbox_mode %}`. The operator PC has no ttyd service, so that widget was 404-ing on `/help`. Only the orange "Report issue" feedback widget (`components/feedback_widget.html`) is shown in sandbox mode.
- **Icon asset:** `app/static/matat.ico` — multi-resolution (16/24/32/48/64/128/256) ICO built from `app/static/logo.png` for use by the operator's desktop shortcut.

### 2026-04-19 (continued)
- **Shva processor added** as enabled PaymentProcessor (priority 8) so it appears as a tab between Nedarim Plus (5) and Stripe (10). Tab labels on `/admin/donations` now use `name` instead of the donor-facing `display_name`.
- **Admins are no longer exempt** from `allowed_processors` — an empty/null list still means "all"; a non-empty list applies to every role. This lets specific admins be scoped to a single processor (e.g. Gittle Goldblum → stripe only).

### 2026-04-19
- **Per-processor permission + tab filter on Donations page:**
  - Added `allowed_processors` JSON column to `User` model (null/empty = access to all processors)
  - `User.can_view_processor(code)` helper; admins bypass restrictions
  - Admin donations page (`/admin/donations`) now shows a processor tab row below the status filters, listing each enabled processor the current user has permission to view
  - `processor` query param filters donation list; restricted users viewing "All" are scoped to their allowed processors
  - Pagination and status-tab links preserve the active processor filter
  - Salesperson form gained a "Payment Processor Access" section with a checkbox per enabled processor; saved on create and edit
  - Migration `03fc01b4e58c_add_allowed_processors_to_users`

### 2026-04-15
- **ZTorm i18n:** Full English/Hebrew translation for all 17 ZTorm templates + base
  - ~300 translation keys under `ztorm.*` namespace in en.json and he.json
  - EN/עב language toggle button in ZTorm toolbar
  - RTL/LTR Bootstrap switching based on language
  - ZTorm base template uses `lang`/`text_dir` for direction
- **Three New Payment Processors (built, not activated):**
  - `CreditGuard (Hyp)` — XML API, leading Israeli gateway, tokenization, 3D Secure
  - `Yaad (iCard)` — REST form-encoded, simplest API, popular with nonprofits
  - `Pelecard` — JSON REST, 35+ year processor, standing orders
  - All registered in `router.py`, support ILS/USD/EUR/GBP, charges, installments, refunds, tokens
- **Encrypted AI API Keys:** Fernet encryption (AES) for all API keys in database
  - Anthropic (Claude), OpenAI (ChatGPT), Google (Gemini) — all encrypted at rest
  - `app/utils/crypto.py` with encrypt_value/decrypt_value derived from SECRET_KEY
  - Admin Settings page: purple "AI API Keys" card with three password fields
  - Keys never stored in code, .env, or environment variables
- **Help Widget Redesign:**
  - `admin` username → ttyd terminal (Claude Code direct access) + screenshot tools
  - All other users → AI chat via API key (reads CLAUDE.md for context) + screenshot tools
  - Ctrl+V paste screenshots from ANY screen (auto-opens widget, uploads, shows copyable URL)
  - 📸 Screenshot button captures current page and uploads
  - 📁 Upload button for file selection
  - Widget appears on both Matat and ZTorm pages
- **ZTorm ↔ Matat Toggle:** Orange "Matat" button in ZTorm toolbar, gold "ZTorm" in Matat nav
- **Donor Model Fix:** Added missing relationships (addresses, phones, memorial_names, communications)
- **Dashboard Fix:** Missing `in processor_breakdown` on for loop

### 2026-04-16
- **Charge Form Redesign:** Completely rewritten `/ztorm/charge` form with 3-column RTL layout
  - Column 1 (Right): Donor details with dual address toggle (Israeli / Foreign)
  - Column 2 (Middle): Charge details, currency, installments, receipt section
  - Column 3 (Left): Card details with masking, warning and info boxes
  - Checkbox toggle switches between Israeli fields (TZ, IL address/city/zip) and Foreign fields (address, city, state, zip, country)
  - Currency change auto-suggests matching address type (ILS -> Israeli, USD/EUR -> Foreign)
  - Hidden `address_type` field submitted with form for backend logging
  - "Save Donor" button saves donor info without charging
  - Donor search API now returns both Israeli and foreign address fields
  - Charge route logs `address_type`, `currency`, `amount` per charge
  - Address fields saved to correct donor model columns based on address_type

### 2026-04-14 (ZTorm Integration)
- **ZTorm Portal:** Full Access-lookalike donation management system integrated at 
  - Switchboard (main menu), Donor browser with search, Donor detail with 8 tabs
  - Data entry (Klita) form, Donation/Payment/Agreement management
  - Reports with filters and Excel export
  - Receipt generation via EZCount API (type 400 - קבלה על תרומה)
  - Credit card charging via Shva/Ashrait SOAP API (production)
  - Email sending via Mailtrap with receipt PDF attachment
  - Hebrew RTL UI mimicking Access 2003 styling
- **14 New Database Tables:** agreements, payments, addresses, phones, classifications,
  memorial_names, communications, donation_events, accounts, account_allocations,
  accounting_credits, collection_batches, credit_card_recurring, credit_card_charges,
  standing_orders
- **30+ New Donor Fields:** title, suffix, gender, spouse, parents, classifications,
  receipt preferences, letter name overrides, bookmark, follow-up frequency
- **20+ New Donation Fields:** agreement_id, paid_nis/usd, expected_nis/usd, payment dates,
  cancellation tracking, receipt preferences, ZTorm ID mapping
- **ZTorm Data Import:** 1,764 donors imported from Access MDB with smart merge
  - Matched by TZ (Israeli ID), email, or name against existing 770 Matat donors
  - Each donor has  linking back to Access 
  - Total donors: 2,480 (merged + new + existing)
- **Shva/Ashrait Credit Card Processor:** ()
  - SOAP API at 
  - Terminal: 2481062014, Username: MXRCX
  - Supports regular charges, installments, card validation
  - Processor selection UI for user to choose CC provider
- **EZCount Receipt API:** ()
  - API Key configured, prefix Z2
  - Creates official Section 46 tax receipts (type 400)
  - Downloads PDFs, sends via email
- **Business Logic Services:** ()
  -  - Donation lifecycle (activate, cancel, complete, recalculate)
  -  - Payment CRUD with auto-recalculation
  -  - Sequential numbering, PDF generation, batch preparation
  -  - Account allocations, credit entries
  -  - Israeli TZ validation, bank account checksum, duplicate detection
  -  - Mailtrap integration with receipt PDF attachment
  -  - EZCount API for official Israeli tax receipts
- **Navigation:** Gold "🏛 ZTorm" link added to both admin and salesperson nav bars
- **Authentication:** ZTorm uses same Matat login session - no separate credentials needed

### 2026-03-27
- **Multi-Processor Payment System (Complete):** Built table-driven payment routing supporting 11 processors
  - Created `PaymentProcessor` model for processor configuration (credentials, currencies, countries, fees)
  - Created `PaymentRoutingRule` model for routing rules (currency, country, amount, donation type)
  - Added `payment/` service package with abstract `BasePaymentProcessor` class
  - 8 credit card processors: Stripe, Nedarim Plus, CardCom, Grow, Tranzila, PayMe, iCount, EasyCard
  - 3 DAF processors: The Donors Fund, Matbia, Chariot/DAFpay (1,151+ providers)
  - `PaymentRouter` class with table-driven routing logic
  - Generic `Donation` model fields: `processor_transaction_id`, `processor_token`, `processor_confirmation`, `processor_recurring_id`, `processor_receipt_url`
  - Created `seed_processors.py` for initial processor/rule setup
- **DAF/Charity Card Processors:** Added support for Donor-Advised Fund donations
  - `DonorsFundProcessor`: Username+PIN or Card+CVV authentication
  - `MatbiaProcessor`: Jewish charity cards with NFC support
  - `ChariotProcessor`: Universal DAFpay button covering OJC, JCF, Fidelity, Schwab, etc.
  - Added `is_daf_donation`, `daf_provider`, `daf_grant_id` fields to Donation model
  - DAF donations do NOT generate tax receipts (donor has receipt from DAF provider)
  - Chariot webhook at `/webhook/chariot` with HMAC-SHA256 verification
- **Admin UI for Payment Processors:** `/admin/payment-processors`
  - Credit card processors section with enable/disable toggle
  - DAF processors section (separate, purple accent)
  - Processor-specific credential configuration forms for all 11 processors
  - Routing rules table with priority, conditions, and target processor
  - Link added to Settings page for easy access
- **Multi-Platform Design:** Each platform/client can enable different processors based on their needs
- **International Routing:** System routes by donor location for multi-country organizations with multiple merchant IDs

### 2026-04-14
- **Nedarim Plus Transaction Sync:** Automatic polling of Nedarim API every 10 minutes
  - `flask sync-nedarim` CLI command polls `GetHistoryJson` for new transactions
  - Cron job runs every 10 minutes (`/var/log/nedarim-sync.log`)
  - No receipts generated (Nedarim provides their own) — `--with-receipts` flag to opt in
  - Imported 1,375 historical transactions from Nedarim Plus
  - Donor matching: email first, phone fallback, updates missing info
- **Donor Model Enhancements:**
  - `teudat_zehut` field on Donor model (Israeli ID from Nedarim `Zeout`)
  - `donor_comment` field on Donation model (comments/dedications from donors)
  - Backfilled 184 teudat zehut values and 546 comments from existing data
- **Nedarim Plus Donation Page** (`/donate/nedarim`):
  - Two-step flow: payment method selection → donation form
  - Payment methods: credit card, standing order, bank standing order, BIT, bank transfer
  - Our form (amount presets ₪100-₪3,600, name, ת.ז., phone, email, comments)
  - Nedarim `/iframe/` for PCI-compliant card entry via PostMessage
  - Currently redirects to Nedarim standalone page (iframe API auth issue pending)
  - Test page at `/donate/nedarim-test` for debugging with Nedarim support
- **Dynamic Donation Page Tabs:** Payment method tabs auto-generated from enabled processors
  - Enabling a processor in admin automatically adds its tab to `/donate`
  - Nedarim tab links to separate `/donate/nedarim` page
- **Dashboard Processor Breakdown:** Table showing donations by processor and currency
  - Stripe USD, Nedarim ILS, Nedarim USD with counts and totals
  - Processor column with colored badges on donations list and recent donations
  - Currency-aware amounts (₪ for ILS, $ for USD)
- **Admin Navigation Overhaul:** Dropdown menus replacing flat link bar
  - Donations: Donations, Donors, Receipts, Donation Pages (USD/ILS)
  - Salespersons: Salespersons, Commissions
  - Settings: Settings, Payment Processors, Email Templates, Screenshots, User Chats
- **Admin Screenshots** (`/admin/screenshots`): Upload and paste screenshots for Claude review
  - Paste (Ctrl+V) or file select with preview before upload
- **Email Campaign Tracking** (`/admin/campaign-track/apology`):
  - Tracks donations from apology email recipients
  - Stats: emails sent, donors who donated, total donated, conversion rate
- **Apology Email Sent:** 30 donors notified about erroneous receipt (system migration glitch)
  - Bilingual English/Hebrew with donate link to Nedarim Plus
  - Sent via Mailtrap, ActiveTrail also configured and tested
- **Nedarim Webhook** (`/webhook/nedarim/webhook`): IP-verified endpoint for payment notifications
  - No receipts for Nedarim donations (Nedarim provides their own)

### 2026-04-13
- **Fix: Payment Processor Config Save:** SQLAlchemy JSON column mutation detection
  - Added `MutableDict.as_mutable()` on `config_json` column in `PaymentProcessor` model
  - Added `MutableList.as_mutable()` on `supported_currencies` and `supported_countries`
  - Credentials now persist correctly when saved via admin UI

### 2026-04-14
- **YeshInvoice Integration (Built, Not Activated):** Israeli invoicing API integration
  - Added `yeshinvoice_user_key`, `yeshinvoice_secret_key`, `yeshinvoice_account_id`, `yeshinvoice_enabled`, `yeshinvoice_default_doc_type` to `ConfigSettings` model
  - Added `yeshinvoice_doc_id`, `yeshinvoice_doc_number`, `yeshinvoice_pdf_url` to `Donation` model
  - Created `app/services/yeshinvoice_service.py` with full API client: `create_receipt()`, `create_credit_note()`, `find_or_create_customer()`, `get_document()`, `test_connection()`
  - Added YeshInvoice settings section to admin settings page with enable toggle, credentials, document type selector, and Test Connection button
  - Added `/admin/settings/test-yeshinvoice` API endpoint for connection testing
  - Disabled by default; not wired into any donation flow

### 2026-04-15
- **AI API Keys:** Added encrypted OpenAI and Google API key fields to ConfigSettings model (same encrypt/decrypt pattern as Anthropic key)
  - New columns: `openai_api_key`, `google_api_key` with property getters/setters
  - Renamed settings card from "Claude AI API Key" to "AI API Keys" with all three providers
  - Admin routes updated to save new keys with masked value check
- **Chat Widget System Context:** Chat widget now loads CLAUDE.md as system documentation context, so the assistant knows all system features
- **ZTorm Widget:** Claude chat widget now included in ZTorm base template for all authenticated users
- **ZTorm-Matat Toggle:** Added "Matat" toggle button in ZTorm toolbar to switch back to main app

### 2026-04-09
- **Server Migration:** Migrated from compromised server (`/root/matat`) to new server (`/var/www/matat`, IP 178.128.83.220)
  - Security audit: all MD files and codebase scanned for compromise — clean
  - Updated all hardcoded `/root/matat` paths to `/var/www/matat` (routes, PDF templates, CLAUDE.md)
  - Recreated Python venv (old shebang pointed to `/root/matat/venv/bin/python3`)
  - Generated new cryptographic SECRET_KEY (replaced dev default)
  - Fixed APP_DOMAIN to `https://matatmordechai.org`
  - Restricted `.env` permissions to 0600
- **Systemd Service:** Created `/etc/systemd/system/matat.service` for Gunicorn (port 5050, 3 workers)
- **Caddy Reverse Proxy:** Installed and configured Caddy with auto-HTTPS
  - `matatmordechai.org` → Matat app (Gunicorn 5050)
  - `db.matatmordechai.org` → Adminer (PHP-FPM)
  - Disabled Apache2 (was occupying port 80)
  - Let's Encrypt SSL auto-provisioned for both domains
- **Adminer Setup:** Configured `db.matatmordechai.org` for database management via PHP-FPM

### 2026-03-29
- **Donor Notes System:** Added `DonorNote` model for adding notes to donor records
  - Admin can add, edit, delete, and pin notes on any donor
  - Salespersons can add notes to donors they have donations from
  - All notes visible to anyone with access to the donor
  - Notes show author and timestamp
- **Donor Activity History:** Added activity timeline showing all transactions and communications
  - Donations, receipts, emails (with tracking status), notes in unified timeline
  - Sorted chronologically with icons and status indicators
- **Donor Detail Page Tabs:** Reorganized admin donor detail page with Overview, Notes, and Activity tabs
- **Salesperson Donor View:** Added `/salesperson/donors` route for salespersons to see their donors
  - Restricted to donors they have donations from
  - Can view donor details and add notes
  - Created `my_donors.html` and `donor_detail.html` templates
- **Email Template Attachments:** Added attachment support to email templates
  - `attachment_path` and `attachment_name` fields added to `EmailTemplate` model
  - Upload files (PDF, DOC, XLSX, etc.) up to 10MB when creating/editing templates
  - Attachments included when sending donation link emails using a template
  - Attachment indicator shown in template list and email preview modal
- **ActiveTrail Email Integration:** Added ActiveTrail as an email provider option
  - Database-driven configuration via Admin Settings
  - Fields: `activetrail_api_key`, `activetrail_from_email`, `activetrail_from_name`, `email_provider`
  - Email provider dropdown: Mailtrap (default), ActiveTrail, SMTP
  - ActiveTrail uses transactional API at `webapi.mymarketing.co.il/api/smtpapi/Message`
  - Server IP whitelist displayed: 161.35.137.106
  - Supports attachments via base64 encoding

### 2026-03-26
- **Claude Session Tracking:** Added `/claude` blueprint with session management, embedded ttyd terminal, screenshot paste/upload
- **File Upload Tool:** Added `/upload` blueprint for token-protected file uploads
- **Email Templates:** Added `EmailTemplate` model for custom donation link emails
- **Donor Linking:** Added `external_id` field and donor merging capabilities
- **Donor Detail Page:** Added comprehensive donor detail view with donation history
- **Link Management:** Enhanced donation links with donor selection and pending links tab
- **Email Tracking:** Added delivery, open, and click tracking via Mailtrap webhooks
- **Claude Chat Widget:** Floating chat widget on all admin pages with screenshot paste/upload, minimize/maximize, drag to move
- **Fix Unknown Donors:** Script to auto-fix "Unknown" donor names from Stripe billing details (fixed 36 donors)
- **Bulk Fix Tool:** Added `/admin/donors/fix-unknown` page for manually fixing remaining unknown donor names
- **Fix:** ttyd systemctl commands now use full path (`/usr/bin/systemctl`) for gunicorn compatibility
- **Fix:** ttyd iframe now uses `/help` proxy path instead of direct port access (fixes HTTPS mixed-content)
- **Fix:** ttyd service now attaches to tmux session `matat` (changed from session `4`)
- **Fix:** Receipt MM-2026-00123 had wrong donor_id, corrected to match donation's donor
- **Fix:** Prevent "Leave site?" browser warning on admin pages (all changes auto-saved via AJAX)
