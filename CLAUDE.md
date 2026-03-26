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
- **Payments:** Stripe (card payments, supports test and live modes)
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
├── services/        # Business logic (stripe, email, pdf, receipts)
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
- `ttyd-matat.service` - Systemd service running ttyd on port 7681, attaching to tmux session 4

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

---

## Changelog

### 2026-03-26
- **Claude Session Tracking:** Added `/claude` blueprint with session management, embedded ttyd terminal, screenshot paste/upload
- **File Upload Tool:** Added `/upload` blueprint for token-protected file uploads
- **Email Templates:** Added `EmailTemplate` model for custom donation link emails
- **Donor Linking:** Added `external_id` field and donor merging capabilities
- **Donor Detail Page:** Added comprehensive donor detail view with donation history
- **Link Management:** Enhanced donation links with donor selection and pending links tab
- **Email Tracking:** Added delivery, open, and click tracking via Mailtrap webhooks
- **Fix:** ttyd systemctl commands now use full path (`/usr/bin/systemctl`) for gunicorn compatibility
