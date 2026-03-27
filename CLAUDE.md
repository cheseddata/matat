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
│   └── webhook/     # Stripe webhook handlers
├── models/          # SQLAlchemy models
├── services/        # Business logic (payment/, email, pdf, receipts)
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

**Service:**
- `ttyd-matat.service` - Systemd service running ttyd on port 7681, attaching to tmux session `matat`

**Widget:**
- Floating chat widget included on all admin pages via `components/claude_widget.html`
- Features: minimize/maximize, drag to move, screenshot paste (Ctrl+V), resize

## File Upload Tool (`/upload`)
Token-protected file upload page for migration files (Access databases, spreadsheets, etc.).

**Access:** Token required (`matat2026`)
**Location:** Files saved to `/root/matat/uploads/`
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
- Nedarim Plus (disabled) - Awaiting credentials from office@nedar.im
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
