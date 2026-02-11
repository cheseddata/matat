# Matat Mordechai Implementation Guide

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
│   ├── donate/      # Public donation pages
│   ├── salesperson/ # Salesperson dashboard, phone entry, links, commissions
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
- **Donation Tracking:** All donations linked to salesperson referral codes
- **Receipt System:** Auto-generated PDF receipts with sequential numbering, email delivery
- **Commission System:** Automatic calculation based on salesperson tier, bulk payment
- **Language Toggle:** Cookie-based EN/HE switching on all pages
- **Email BCC:** All outgoing emails BCC'd to support@matatmordechai.org

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
