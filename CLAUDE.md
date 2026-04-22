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
