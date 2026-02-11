# Matat Mordechai — Donation & Commission Management System

## Project Overview

A Stripe-integrated web application for **Matat Mordechai** that manages charitable donations, salesperson commissions, tax-deductible receipt generation, and administrative reporting. The system supports both English and Hebrew interfaces.

**Database:** `matat` (already created)

---

## 1. Technology Stack

- **Backend:** Flask (Python)
- **Database:** MySQL (`matat` database)
- **Payments:** Stripe (test/live keys to be provided)
- **Frontend:** HTML/CSS/JS with English ↔ Hebrew toggle (per user setting or page-level toggle)
- **Email:** Automated transactional emails (receipts + donation links)
- **Hosting:** DigitalOcean (existing infrastructure)

---

## 2. User Roles & Authentication

### 2.1 Administrator
- Full system access: manage salespersons, set commission structures, view all reports, manage payouts
- Creates salesperson accounts with a **temporary login** (username + temp password)

### 2.2 Salesperson
- On first login with temp credentials → forced to change password
- Password stored as a **hash key** (bcrypt or similar)
- Can view **only their own** sales/donations and commission status
- Can key in donations over the phone
- Can send email donation links to donors (link credits back to the salesperson)

### 2.3 Donor (Public / No Login Required)
- Arrives via a salesperson-generated link OR the general donation page
- Provides: **Name**, **Address**, **Email** (required)
- Completes payment via Stripe checkout

---

## 3. Commission Structure

Admin has the ability to configure commission on a **per-salesperson basis**. Two options:

### Option A: Flat Rate Per Sale
- A fixed dollar amount per completed donation
- Example: $50 per donation regardless of amount

### Option B: Percentage-Based
- A percentage of each donation amount
- Example: 10% of a $1,000 donation = $100 commission
- Admin can set tiered percentages if needed (e.g., 5% up to $500, 8% from $501–$2,000, 10% above $2,000)

### Commission Settings (Admin Panel)
- Choose flat or percentage mode per salesperson
- Set the rate/percentage value
- Option for tiered percentage brackets
- Commission is calculated automatically upon successful Stripe charge
- Admin marks commissions as **paid** with date, check number, or payment method

### Commission Resolution Hierarchy

When a donation comes in, the system determines the commission rate using this **explicit priority order:**

```
1. Campaign override rate (if donation has aff= AND campaign has commission_override set)
       ↓ if null
2. Salesperson custom rate (if donation has ref= AND salesperson has commission_type/rate set)
       ↓ if null
3. System-wide default rate (from config table: default_commission_type, default_commission_rate)
       ↓ if null
4. No commission (direct donation with no ref= or aff=)
```

**Edge case — `ref` + `aff` together:**
If a donation has both a salesperson (`ref=SP-0042`) and a campaign (`aff=PURIM2026`), and the campaign has a commission override:
- The **campaign rate applies** (overrides the salesperson's personal rate)
- The **salesperson still gets credited** — they earn the commission, just at the campaign's rate
- The Admin UI clearly shows when a campaign override is active, including:
  - A warning badge on the campaign setup page: "This rate will override individual salesperson rates"
  - In the salesperson portal: "Commission for this donation calculated at PURIM2026 campaign rate (15%)" instead of their normal rate
  - In reports: both the campaign rate used and what the salesperson's default rate would have been, so admin sees the difference

---

## 4. Donation Flow

### 4.1 Phone/In-Person Entry (Salesperson Keys In)
1. Salesperson logs in
2. Enters donor info: Name, Address, Email (required)
3. Enters donation amount
4. Selects one-time or recurring
5. Processes payment via Stripe (card details entered into Stripe Elements)
6. On success:
   - Donation recorded in DB with salesperson ID
   - Tax-deductible receipt emailed to donor
   - Commission calculated and logged
   - Salesperson sees the donation in their dashboard

### 4.2 Email Link (Salesperson Sends Link to Donor)
1. Salesperson enters donor's Name, Address (if available), and Email
2. Optionally sets a **preset donation amount** (from phone conversation)
3. System generates a **unique compressed short link** tied to that salesperson
4. Link **does not expire**
5. Email is sent to the donor with the link
6. Donor clicks link → lands on donation page:
   - If preset amount was set → amount is pre-filled (donor can still change it if needed)
   - If no preset → donor enters their own amount
   - Name/Address pre-filled if provided by salesperson
   - Donor completes via Stripe
7. On success:
   - Donation credited to the originating salesperson
   - Receipt emailed to donor
   - Commission logged

### 4.3 General Donation Page (No Salesperson)
- Public-facing page for direct donations (no commission)
- Donor enters Name, Address, Email, Amount
- One-time or recurring option
- Receipt emailed on completion

### 4.4 Donation Rules
- **No minimum or maximum** donation amount
- **One-time and recurring** donations supported
- Recurring: use Stripe Subscriptions or Stripe Payment Links with recurring billing
- All donor info and Stripe transaction data stored in DB

---

## 5. Donation Links & URL Tracking (`ref` / `aff`)

### 5.1 URL Structure

Every donation link uses query parameters to track **who** or **what** drove the donation. Two tracking parameters are supported:

| Parameter | Purpose | Tracks Back To |
|-----------|---------|---------------|
| `ref=` | **Referral** — identifies the salesperson | Salesperson account |
| `aff=` | **Affiliate / Campaign** — identifies a campaign or source | Campaign record |

Both can be used together. Examples:

```
# Salesperson link (ref only)
https://donate.matatmordechai.org/d/Xk9mZ2?ref=SP-0042

# Campaign link (aff only)  
https://donate.matatmordechai.org/d/Xk9mZ2?aff=PURIM2026

# Salesperson + Campaign (both)
https://donate.matatmordechai.org/d/Xk9mZ2?ref=SP-0042&aff=PURIM2026

# With preset amount
https://donate.matatmordechai.org/d/Xk9mZ2?ref=SP-0042&amt=500

# Full example with all params
https://donate.matatmordechai.org/d/Xk9mZ2?ref=SP-0042&aff=PURIM2026&amt=500&name=Mark+Newman&email=mark@example.com
```

### 5.2 Tracking Codes

#### `ref` — Salesperson Reference Code
- Auto-generated when a salesperson account is created
- Format: `SP-NNNN` (e.g., `SP-0042`) or a custom slug (e.g., `moshe-k`)
- Unique per salesperson, stored in `users.ref_code`
- Admin can edit/reassign ref codes
- Any donation that comes through a `ref=` link is **credited to that salesperson** for commission purposes
- The ref code is embedded in every link the salesperson generates

#### `aff` — Campaign / Affiliate Code
- Created by admin for specific campaigns, events, or marketing initiatives
- Format: Custom slug (e.g., `PURIM2026`, `GALA-DINNER`, `EMAIL-JAN`, `FACEBOOK-AD-1`)
- Stored in a `campaigns` table
- Tracks the **source/reason** for the donation independent of the salesperson
- A campaign can have its own commission structure (overrides salesperson default if set)
- Can be used without a `ref` (e.g., a general campaign page shared on social media)
- Can be used with a `ref` (e.g., a salesperson promoting a specific campaign)

### 5.3 Link Generation

**Salesperson-generated links (personal):**
- Salesperson fills in donor info + optional preset amount
- System generates a short code and appends `ref=` automatically
- If salesperson is working under a specific campaign, `aff=` is also appended

**Campaign links (admin-generated):**
- Admin creates a campaign → system generates a base URL with `aff=`
- This link can be shared publicly (social media, email blasts, print)
- No salesperson credit unless `ref=` is also present

**Combined links:**
- A salesperson can generate links for a specific campaign
- Both `ref=` and `aff=` are included
- Commission logic: campaign override > salesperson default

### 5.4 Link Short Codes

- Every donation link has a unique **compressed short code** (6-8 alphanumeric chars)
- Stored in `donation_links.short_code`
- Resolves to the full donation page with all parameters
- Short code can be used in SMS, WhatsApp, print materials
- Links **never expire**

### 5.5 URL Parameter Reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `ref` | No | Salesperson reference code |
| `aff` | No | Campaign/affiliate code |
| `amt` | No | Preset donation amount (dollars) |
| `name` | No | Pre-fill donor name |
| `email` | No | Pre-fill donor email |
| `addr` | No | Pre-fill donor address |
| `lang` | No | Force language (`en` or `he`) |
| `type` | No | `onetime` or `recurring` |

### 5.6 Attribution & Lookup

Every donation records:
- `salesperson_id` — resolved from `ref=` parameter
- `campaign_id` — resolved from `aff=` parameter
- `link_id` — the specific generated link used
- `source` — how the donation was initiated (phone / email_link / sms_link / whatsapp_link / direct / campaign_page)

**Admin can trace any donation back to:**
- Which salesperson referred it (`ref`)
- Which campaign it came from (`aff`)
- Which specific link was used (short code)
- When the link was created and by whom
- How many times the link was used

**Reports can be filtered/grouped by:**
- Salesperson (ref code)
- Campaign (aff code)
- Salesperson + Campaign combination
- Date range
- Any combination of the above

### 5.7 Database Tables

**`campaigns`** — Campaign / Affiliate tracking
- `id`, `aff_code` (unique slug, e.g., "PURIM2026"), `name`, `description`, `start_date`, `end_date` (nullable — ongoing campaigns), `commission_override_type` (nullable — flat/percentage, overrides salesperson default), `commission_override_rate` (nullable), `goal_amount` (nullable), `total_raised` (cached), `is_active`, `created_by` (FK to users), `created_at`, `updated_at`

**Updated `donation_links`** table:
- `id`, `short_code` (unique), `salesperson_id` (FK, nullable), `campaign_id` (FK, nullable), `donor_email`, `donor_name`, `donor_address`, `preset_amount` (nullable), `preset_type` (onetime/recurring, nullable), `full_url` (the complete URL with all params), `times_used`, `last_used_at`, `created_at`

**Updated `users`** table — add:
- `ref_code` (unique, e.g., "SP-0042" or custom slug)

**Updated `donations`** table — add:
- `campaign_id` (FK, nullable — resolved from `aff=` parameter)

---

## 6. Tax-Deductible Receipt

### Receipt Content (US Only for Now)
Modeled after the sample receipt (Congregation Pirchei Shoshanim format):

```
[Organization Logo]

[DATE]
[Donor Full Name]
[Donor Address Line 1]
[Donor City, State ZIP]
Receipt #[MM-YYYY-NNNNN]

Dear [Donor Full Name],

Thank you for your donation totaling $[AMOUNT] to Matat Mordechai.

Your generosity helps ensure the growth and success of our programs.

Enclosed for your records is a copy of your transaction.

-------------------------------------------------------------
Date received    Status       Sender          Type         Amount
[Date]           Completed    [DONOR NAME]    [Type]       $[Amount]
-------------------------------------------------------------

[Payment confirmation details from Stripe]
Transaction number: [Stripe charge ID]

-------------------------------------------------------------

Donation Amount $[AMOUNT]

For accounting purposes our 501c3 tax ID number is [TAX_ID from database]

No goods or services were rendered in exchange for this contribution.
```

### Receipt Number Generator

The receipt number is a **structured, sequential, unique identifier** that encodes enough information to trace back to the original transaction at a glance. It is stored in a dedicated counter table so numbering is never duplicated and can always be looked up.

**Format:** `MM-YYYY-NNNNN`

| Segment | Meaning | Example |
|---------|---------|---------|
| `MM` | Organization prefix code (Matat Mordechai = `MM`) | `MM` |
| `YYYY` | Fiscal year | `2026` |
| `NNNNN` | Sequential number, zero-padded, resets per year | `00001` |

**Example:** `MM-2026-00147` = the 147th receipt issued in 2026 for Matat Mordechai.

**Database Table: `receipt_counter`**
- `id`
- `org_prefix` (e.g., "MM") — allows multi-org in the future
- `fiscal_year` (e.g., 2026)
- `last_sequence` (integer, auto-incremented per receipt)
- `updated_at`

**Generation logic (atomic, with new-year auto-transition):**
```sql
-- Atomic receipt generation inside a transaction
START TRANSACTION;

-- Try to increment existing year counter
UPDATE receipt_counter 
SET last_sequence = last_sequence + 1, updated_at = NOW()
WHERE org_prefix = 'MM' AND fiscal_year = YEAR(CURDATE());

-- If no rows updated, this is the first receipt of a new fiscal year → auto-create
INSERT IGNORE INTO receipt_counter (org_prefix, fiscal_year, last_sequence, updated_at)
VALUES ('MM', YEAR(CURDATE()), 1, NOW());

-- If the INSERT fired (new year), last_sequence is already 1
-- If the UPDATE fired (existing year), last_sequence is incremented
SELECT CONCAT(org_prefix, '-', fiscal_year, '-', LPAD(last_sequence, 5, '0')) AS receipt_number
FROM receipt_counter 
WHERE org_prefix = 'MM' AND fiscal_year = YEAR(CURDATE());

COMMIT;
```

> **⚠ New Year Transition:** The logic automatically handles the fiscal year rollover. When the first donation of 2027 comes in and no `receipt_counter` row exists for `fiscal_year = 2027`, the `INSERT IGNORE` creates it starting at sequence `1`. No manual intervention needed.

**Lookup capabilities:**
- Search by full receipt number → returns the donation, donor, salesperson, amount, date, PDF
- Search by year → all receipts for that fiscal year
- Search by donor → all receipts for a specific donor
- Search by salesperson → all receipts generated from their donations
- Search by date range → receipts within a period
- Admin UI: receipt lookup page with search/filter by any of the above
- Donor email includes receipt number prominently for their records

**Receipt re-generation:**
- Admin or system can re-send or re-generate any receipt by receipt number
- Original PDF is stored on disk/S3 with path in `receipts` table
- If re-generated, a `reissued_at` timestamp is logged (original remains unchanged)

### Receipt Rules
- **Tax ID** pulled from a settings/config table in the database (not hardcoded)
- Receipt number generated via the `receipt_counter` table (see above) — never hardcoded or timestamp-based
- Sent via email as a **PDF attachment** styled similar to the uploaded sample
- Organization name on receipt: **Matat Mordechai**
- US receipts only (for now)
- Original PDF stored and retrievable by receipt number at any time
- Admin can re-send any receipt from the receipt lookup page

---

## 7. Stripe Integration & Webhooks

### 7.1 Webhook Endpoint

A dedicated webhook endpoint (e.g., `/api/stripe/webhook`) will receive real-time events from Stripe. This is the **primary mechanism** for recording donation data — the system should NOT rely solely on the client-side success response. The webhook is the source of truth.

**Webhook signature verification:** Every incoming webhook must be verified using the Stripe webhook signing secret to prevent spoofing.

### 7.2 Webhook Events to Handle

| Event | Purpose |
|-------|---------|
| `payment_intent.succeeded` | Primary trigger — donation completed successfully |
| `charge.succeeded` | Capture fee breakdown (CC vs ACH fees differ) |
| `invoice.paid` | Recurring donation installment completed |
| `charge.refunded` | Mark donation as refunded, reverse commission, track fee loss |
| `charge.failed` | Log failed attempts, update status |
| `customer.subscription.created` | Recurring donation set up |
| `customer.subscription.deleted` | Recurring donation cancelled |
| `payment_method.attached` | Track payment method details |

### 7.3 Fee Capture (Critical)

Stripe charges different processing fees for **credit card** vs **ACH bank transfer**. The webhook provides the exact fee breakdown via the **Balance Transaction** object.

**On every successful charge, the webhook handler must:**

1. Receive the `charge.succeeded` event
2. Extract the `balance_transaction` ID from the charge object
3. Call `stripe.BalanceTransaction.retrieve(balance_transaction_id)` to get:
   - `amount` — gross amount in cents
   - `fee` — total Stripe fee in cents
   - `fee_details` — array breaking down each fee component:
     - `type`: "stripe_fee", "application_fee", etc.
     - `amount`: fee amount in cents
     - `description`: e.g., "Stripe processing fees"
   - `net` — net amount after fees in cents
4. Store all of this in the `donations` table

**Example fee differences:**
- **Credit Card:** ~2.9% + $0.30 per transaction
- **ACH Bank Transfer:** ~0.8% capped at $5.00 per transaction
- **ACH Direct Debit:** Different fee structure

The system must capture the **actual fee** from Stripe (not calculate it), since rates can vary by account, volume, and negotiated pricing.

### 7.4 Refund Fee Tracking

> **⚠ Important:** When a donation is refunded, Stripe typically does **not** refund the original processing fee. This means the organization absorbs a net loss on every refund.

**On `charge.refunded` webhook:**
1. Retrieve the refund object and the original charge's Balance Transaction
2. Check if Stripe refunded any portion of the fee (usually $0, but can vary by account agreement)
3. Calculate and store:
   - `refund_amount` — the amount returned to the donor
   - `fee_refunded` — how much of the original Stripe fee was returned (usually $0)
   - `fee_lost_on_refund` = `original stripe_fee - fee_refunded` — the actual cost to the org
4. This allows the admin to see in reports:
   - Total refunds issued
   - **Total processing fees lost** on those refunds (real cost of refunds)
   - Net financial impact of refunds

### 7.4 Data to Capture from Webhook & Store in DB

**From the Charge/PaymentIntent object:**
- `id` — Stripe Charge ID
- `payment_intent` — Payment Intent ID
- `amount` — gross amount (cents)
- `currency`
- `status` — succeeded / pending / failed
- `payment_method_details.type` — "card", "us_bank_account" (ACH), etc.
- `payment_method_details.card.last4` — last 4 digits (if card)
- `payment_method_details.card.brand` — visa, mastercard, amex, etc.
- `payment_method_details.us_bank_account.last4` — last 4 (if ACH)
- `payment_method_details.us_bank_account.bank_name` — bank name (if ACH)
- `customer` — Stripe Customer ID
- `receipt_url` — Stripe-hosted receipt URL
- `created` — timestamp
- `metadata` — contains our custom fields (salesperson_id, link_id, donor_id)

**From the Balance Transaction object (retrieved separately):**
- `fee` — total fee amount (cents)
- `fee_details` — itemized fee breakdown
- `net` — net amount after all fees (cents)
- `type` — "charge", "refund", etc.

### 7.5 Webhook Processing Flow

```
Stripe Event Received
    │
    ├─► Verify webhook signature
    │
    ├─► Parse event type
    │
    ├─► charge.succeeded / payment_intent.succeeded:
    │       │
    │       ├─► Retrieve Balance Transaction (for fees)
    │       ├─► Extract payment method type (card vs ACH)
    │       ├─► Extract metadata (salesperson_id, link_id, donor_id)
    │       ├─► Create/update donation record in DB
    │       ├─► Calculate commission (based on gross amount)
    │       ├─► Generate receipt PDF
    │       ├─► Email receipt to donor
    │       └─► Update salesperson dashboard data
    │
    ├─► invoice.paid (recurring):
    │       ├─► Same as above but linked to subscription
    │       └─► New donation record per installment
    │
    ├─► charge.refunded:
    │       ├─► Update donation status to "refunded"
    │       ├─► Record fee_refunded amount (Stripe usually keeps the processing fee)
    │       ├─► Reverse/void pending commission
    │       └─► Log refund amount, reason, and net loss
    │
    └─► charge.failed:
            ├─► Log failure
            └─► Update donation status to "failed"
```

### 7.5.1 Webhook Race Condition Handling

> **⚠ Critical:** The `payment_intent.succeeded` webhook can arrive **before** the donor is redirected back to the success page. The frontend must NOT assume the payment is complete just because the Stripe modal/checkout closed.

**Solution — Polling pattern on the success page:**

```
Donor completes Stripe checkout
    │
    ├─► Stripe redirects donor to /donation/success?payment_intent=pi_xxx
    │
    ├─► Frontend shows "Processing your donation..." spinner
    │
    ├─► Frontend polls: GET /api/donation/status?pi=pi_xxx (every 2 seconds, max 15 attempts)
    │       │
    │       ├─► If donation record found in DB (created by webhook) → show confirmation + receipt number
    │       ├─► If not yet found → keep polling
    │       └─► If max attempts reached → show "Your donation is being processed.
    │               You'll receive a receipt by email shortly." (graceful fallback)
    │
    └─► Webhook arrives (possibly before, during, or after polling):
            └─► Creates the donation record, which the poll will pick up
```

**Additional safeguards:**
- **Idempotency:** Use `stripe_payment_intent_id` as a unique key — if the webhook fires twice, the second insert is ignored
- **Pending record:** Optionally create a `status=pending` donation record when the PaymentIntent is created (before Stripe checkout), then the webhook updates it to `succeeded`. This way the success page always has a record to find.
- **Webhook retry:** Stripe retries failed webhooks for up to 3 days. The endpoint must return `200` quickly (process async if needed) to avoid retries

### 7.6 Stripe Metadata Strategy

When creating a PaymentIntent or Checkout Session, attach metadata so the webhook can link everything back:

```python
stripe.PaymentIntent.create(
    amount=amount_in_cents,
    currency="usd",
    customer=stripe_customer_id,
    metadata={
        "salesperson_id": "123",       # from ref= parameter
        "campaign_id": "456",          # from aff= parameter
        "link_id": "789",              # specific donation link used
        "donor_id": "012",
        "donation_type": "one_time",   # or "recurring"
        "ref_code": "SP-0042",
        "aff_code": "PURIM2026",
        "source": "phone" | "email_link" | "sms_link" | "whatsapp_link" | "direct" | "campaign_page"
    }
)
```

### 7.7 Payment Methods to Support
- **Credit/Debit Cards** (Visa, Mastercard, Amex, Discover) via Stripe Elements
- **ACH Bank Transfer** (US bank accounts) via Stripe Financial Connections
- Admin can enable/disable payment methods from settings

### 7.8 Stripe Configuration
- Test and Live API keys stored in environment variables / DB config table
- Webhook signing secret stored securely
- Admin toggle between test and live mode
- Webhook endpoint registered in Stripe Dashboard for both test and live
- Use Stripe Elements or Stripe Checkout for PCI compliance

---

## 8. Database Schema (`matat`)

### Key Tables

> **Foreign Key Strategy:**
> - `ON DELETE RESTRICT` on all FKs referencing `users`, `donors`, `campaigns` — prevent accidental data loss
> - `ON DELETE CASCADE` on `commissions` → `donations` (if a donation is deleted, its commission record goes too — but donations should also be soft-deleted, not hard-deleted)
> - All user-facing entities (`users`, `donors`, `donations`, `campaigns`) use **soft delete** (`deleted_at` timestamp) — never hard delete
> - Indexes on all FK columns and frequently queried fields (`ref_code`, `aff_code`, `short_code`, `receipt_number`, `stripe_charge_id`)

**`config`** — System settings
- `id`, `org_name`, `tax_id`, `stripe_test_key`, `stripe_live_key`, `stripe_mode` (test/live), `stripe_webhook_secret`, `logo_url`, `default_language`, `default_commission_type` (flat/percentage — system-wide fallback), `default_commission_rate` (system-wide fallback), `org_prefix` (for receipt numbering, e.g., "MM")

**`users`** — Admin & salesperson accounts
- `id`, `username`, `password_hash`, `role` (admin/salesperson), `ref_code` (unique — e.g., "SP-0042" or custom slug), `first_name`, `last_name`, `email`, `phone`, `is_temp_password` (boolean), `commission_type` (flat/percentage), `commission_rate`, `commission_tiers` (JSON for tiered rates), `language_pref` (en/he), `active`, `deleted_at` (nullable — soft delete, never hard delete salespersons), `created_at`, `updated_at`

> **⚠ Data Integrity Rule:** Salesperson accounts are **never hard-deleted**. Use `deleted_at` (soft delete) to deactivate. All historical donation records, commission logs, and receipt references must remain intact for tax and audit purposes. FK constraints on `donations.salesperson_id` and `commissions.salesperson_id` use `ON DELETE RESTRICT`.

**`donors`** — Donor information
- `id`, `stripe_customer_id`, `first_name`, `last_name`, `email`, `phone`, `phone_country_code`, `address_line1`, `address_line2`, `city`, `state`, `zip`, `country`, `comm_pref_email` (boolean, default true), `comm_pref_sms` (boolean, default false), `comm_pref_whatsapp` (boolean, default false), `language_pref` (en/he), `deleted_at` (nullable — soft delete), `created_at`, `updated_at`

**`donations`** — All donation transactions
- `id`, `donor_id` (FK), `salesperson_id` (FK, nullable), `campaign_id` (FK, nullable), `stripe_payment_intent_id`, `stripe_charge_id`, `stripe_balance_transaction_id`, `stripe_subscription_id` (nullable), `amount` (gross in cents), `currency`, `stripe_fee` (actual fee from Balance Transaction), `stripe_fee_details` (JSON — itemized fee breakdown), `net_amount` (net after fees from Balance Transaction), `payment_method_type` (card / us_bank_account / etc.), `payment_method_last4`, `payment_method_brand` (visa/mastercard/amex — if card), `bank_name` (if ACH), `status` (succeeded/pending/failed/refunded), `donation_type` (one_time/recurring), `source` (phone/email_link/direct), `receipt_number`, `receipt_sent` (boolean), `receipt_sent_at`, `stripe_receipt_url`, `link_id` (FK, nullable), `refund_amount` (nullable), `refund_date` (nullable), `fee_refunded` (nullable — amount of original processing fee returned by Stripe, usually $0), `fee_lost_on_refund` (nullable — `stripe_fee - fee_refunded`, the net cost to the org from the refund), `stripe_metadata` (JSON), `deleted_at` (nullable — soft delete), `created_at`

**`campaigns`** — Campaign / Affiliate tracking
- `id`, `aff_code` (unique slug), `name`, `description`, `start_date`, `end_date` (nullable), `commission_override_type` (nullable), `commission_override_rate` (nullable), `goal_amount` (nullable), `total_raised` (cached), `is_active`, `created_by` (FK), `created_at`, `updated_at`

**`donation_links`** — Salesperson/campaign-generated links
- `id`, `short_code` (unique), `salesperson_id` (FK, nullable), `campaign_id` (FK, nullable), `donor_email`, `donor_name`, `donor_address`, `preset_amount` (nullable), `preset_type` (onetime/recurring, nullable), `full_url`, `times_used`, `last_used_at`, `created_at`

**`commissions`** — Commission tracking
- `id`, `donation_id` (FK), `salesperson_id` (FK), `donation_amount`, `commission_type` (flat/percentage), `commission_rate`, `commission_amount`, `status` (pending/paid), `paid_date`, `paid_method`, `paid_reference`, `created_at`

**`receipts`** — Receipt log
- `id`, `donation_id` (FK), `receipt_number` (unique, e.g., "MM-2026-00147"), `donor_id` (FK), `amount`, `tax_id_used`, `pdf_path`, `email_sent_to`, `sent_at`, `reissued_at` (nullable), `created_at`

**`receipt_counter`** — Atomic sequential receipt numbering
- `id`, `org_prefix` (e.g., "MM"), `fiscal_year`, `last_sequence` (integer), `updated_at`

---

## 9. Admin Panel Features

### 9.1 Dashboard
- Today's total donations
- This week / month / year totals
- Number of active salespersons
- Recent donations list

### 9.2 Salesperson Management
- Create / edit / deactivate salesperson accounts
- Set commission type and rate per salesperson
- Reset passwords (generates new temp password)

### 9.3 Commission Management
- View all pending commissions
- Mark commissions as paid (with date, method, reference number)
- Commission payout history

### 9.4 Reports
- **Daily Report:** Total income for a specific date
- **Weekly Report:** Total income for a selected week
- **Monthly Report:** Total income for a selected month
- **Yearly Report:** Total income for a selected year
- **Salesperson Report:** Per-salesperson breakdown showing:
  - Total donations generated
  - Total commission earned
  - Total commission paid
  - Outstanding commission balance
  - Individual donation details
- **Campaign Report:** Per-campaign (`aff` code) breakdown showing:
  - Total raised vs. goal
  - Number of donations
  - Which salespersons contributed (via `ref` + `aff` combo)
  - Commission paid under this campaign
  - Active links and their conversion rates
- All reports filterable by date range, salesperson (`ref`), and campaign (`aff`)
- Export to CSV/Excel option

### 9.5 Receipt Lookup
- Search by receipt number (e.g., `MM-2026-00147`)
- Search by donor name or email
- Search by salesperson
- Search by date range
- View original PDF, re-send to donor, or re-generate
- Full receipt history with timestamps

### 9.6 Campaign Management
- Create / edit / deactivate campaigns
- Set campaign `aff` code (unique slug)
- Set optional commission override (flat or percentage — overrides salesperson default)
- Set goal amount
- Track total raised
- Generate campaign-level donation links (no `ref`, just `aff`)

### 9.7 Settings
- Update organization name, tax ID, logo
- Toggle Stripe test/live mode
- Manage email templates

---

## 10. Salesperson Portal

### 10.1 Dashboard
- Their total donations (all time, this month, this week, today)
- Their commission earned vs. paid
- Recent donations list

### 10.2 New Donation (Phone Entry)
- Form: Donor Name, Address, Email (required), Amount, One-time/Recurring
- Stripe payment form (Elements)
- Submit → processes charge → shows confirmation

### 10.3 Send Donation Link
- Form: Donor Name, Address (optional), Email (required), Preset Amount (optional)
- Generate link → system emails the donor
- Shows list of all sent links with status (clicked, donated, amount)

### 10.4 My Transactions
- Full list of all donations credited to them
- Donor name, amount, date, commission earned, commission status (pending/paid)
- **Transparency:** Every salesperson can see all their own data

### 10.5 My Payouts
- History of commission payments received
- Date, amount, method, reference number

---

## 11. Language Support (English / Hebrew)

- **Toggle:** Either a per-user setting (saved in profile) or an on-page language toggle tab
- All UI text, labels, buttons, form placeholders available in both English and Hebrew
- Hebrew layout: RTL (right-to-left) direction
- Receipt emails: generated in the language preference of the donor (default English)
- Admin can view the system in either language
- Use i18n (internationalization) JSON files for all translatable strings

### 11.1 RTL Layout Implementation

> **⚠ Important:** Hebrew support requires a full **layout flip**, not just text translation.

- Set `dir="rtl"` and `lang="he"` on the `<html>` element when Hebrew is active
- Use a CSS framework with RTL support:
  - **Tailwind CSS:** Use `rtl:` variant prefix (built-in since v3.3) or the `@tailwindcss/rtl` plugin
  - **Bootstrap:** Use the official RTL build (`bootstrap.rtl.min.css`)
- All directional CSS properties must flip: `margin-left` → `margin-right`, `text-align: left` → `text-align: right`, `float`, `padding`, flexbox `order`, etc.
- Icons with directional meaning (arrows, chevrons) must also flip
- Forms: input fields, labels, and validation messages must align RTL
- Tables: column order reads right-to-left
- Numbers and currency remain LTR even in RTL context (CSS `direction: ltr` on numeric fields)

### 11.2 Hebrew PDF Receipt Generation

> **⚠ Critical:** Generating Hebrew PDFs in Python requires special handling or the text will render as empty boxes or gibberish.

**Requirements:**
- Use **WeasyPrint** (recommended — handles RTL natively via CSS) or **ReportLab** (requires manual RTL text shaping)
- **Embed a Hebrew-compatible `.ttf` font** in the PDF:
  - Recommended fonts: **Assistant**, **David Libre**, **Heebo**, **Rubik**, or **Frank Ruhl Libre** (all available on Google Fonts, open license)
  - Font file must be bundled with the application (not loaded from CDN at render time)
- If using ReportLab: use the `arabic_reshaper` + `python-bidi` libraries for proper RTL text shaping and bidirectional text handling
- If using WeasyPrint: set `direction: rtl` in the CSS stylesheet and embed the font via `@font-face`
- **Test edge cases:** Mixed Hebrew/English text, numbers within Hebrew sentences, donor names that may be transliterated
- Store both English and Hebrew receipt templates; generate based on donor's `language_pref`

---

## 12. Email Templates

### 12.1 Donation Link Email
- Subject: "Donation to Matat Mordechai" / "תרומה למתת מרדכי"
- Body: Greeting, brief message, prominent donation button/link
- If preset amount: "You've been invited to donate $[AMOUNT]"

### 12.2 Receipt Email
- Subject: "Your Tax-Deductible Receipt — Matat Mordechai"
- Body: Thank you message + PDF receipt attached
- Styled similar to the uploaded sample receipt

### 12.3 Salesperson Welcome Email
- Temporary credentials
- Link to login and change password

---

## 13. Communications Infrastructure

The system is built with a **unified messaging layer** so that any communication — receipts, donation links, notifications, reminders — can be sent through multiple channels. Each channel can be enabled/disabled by the admin from settings.

### 13.1 Communication Channels

| Channel | Provider Options | Use Cases | Status |
|---------|-----------------|-----------|--------|
| **Email** | SendGrid, Amazon SES, ActiveTrail, SMTP | Receipts, donation links, salesperson welcome, reports | **V1 — Active** |
| **SMS / Text** | Twilio, Vonage (Nexmo), Amazon SNS | Donation links, payment confirmations, reminders | **V1 — Ready, Admin Toggle** |
| **WhatsApp** | Twilio WhatsApp API, WhatsApp Business API (Meta) | Donation links, receipts, follow-ups | **V1 — Ready, Admin Toggle** |
| **Push Notifications** | Firebase Cloud Messaging (FCM) | Mobile app alerts (future) | **Future** |
| **In-App Messaging** | Custom (WebSocket / polling) | Salesperson dashboard notifications | **Future** |

### 13.2 Unified Messaging Architecture

All outbound messages go through a single `message_queue` table so that:
- Every message is logged regardless of channel
- Failed messages can be retried
- Admin has a full audit trail of all communications
- Adding a new channel in the future only requires a new sender module — no changes to business logic

```
Business Logic (receipt, link, reminder)
    │
    ▼
Message Queue (DB table)
    │
    ├─► Email Sender Module
    ├─► SMS Sender Module
    ├─► WhatsApp Sender Module
    └─► [Future Channel Module]
```

### 13.3 Channel Details

#### Email
- **V1 provider:** Configurable (SendGrid / SES / ActiveTrail / SMTP)
- **API keys/credentials** stored in DB config table
- **Templates:** HTML email templates stored in DB or filesystem, editable by admin
- **Supports:** Rich HTML, PDF attachments (receipts), images (logo)
- **Tracking:** Open tracking, click tracking (if provider supports)
- **Use cases:**
  - Tax-deductible receipt (PDF attached)
  - Donation link to donor
  - Salesperson welcome / password reset
  - Admin reports (scheduled email)
  - Donation confirmation
  - Recurring donation reminder / failure notice

#### SMS / Text Message
- **Provider:** Twilio (recommended) or Vonage
- **API credentials** stored in DB config table
- **Dedicated phone number** (purchased via provider)
- **Supports:** Plain text, short links
- **Character limits:** 160 chars (SMS) — use compressed donation links
- **Use cases:**
  - Donation link via text
  - Payment confirmation ("Thank you for your $500 donation to Matat Mordechai")
  - Recurring donation reminders
  - Failed payment alerts to donor
- **Opt-in/Opt-out:** Track consent per donor, honor STOP requests, comply with TCPA

#### WhatsApp
- **Provider:** Twilio WhatsApp API or Meta WhatsApp Business API
- **Requires:** Approved WhatsApp Business Account & message templates
- **API credentials** stored in DB config table
- **Supports:** Rich text, buttons, images, PDF attachments
- **Template messages:** Pre-approved by WhatsApp (required for outbound messages)
- **Use cases:**
  - Donation link with rich preview and "Donate Now" button
  - Receipt delivery (PDF or formatted message)
  - Follow-up / thank you messages
  - Recurring donation reminders
- **Opt-in required:** Donor must have opted in to WhatsApp communication
- **Note:** WhatsApp messages outside 24-hour window require approved templates

### 13.4 Salesperson Channel Selection

When a salesperson sends a donation link, they choose the channel:

1. **Send via Email** — default
2. **Send via SMS** — if donor phone number provided
3. **Send via WhatsApp** — if donor phone number provided and WhatsApp enabled
4. **Copy Link** — salesperson copies the link manually (for any channel they handle themselves)

If the donor has both email and phone, the salesperson can send via multiple channels.

### 13.5 Admin Communication Settings

- Enable/disable each channel globally
- Configure API keys and credentials per channel
- Set default channel for receipts (email by default)
- Set default channel for donation links (email by default)
- Manage email/SMS/WhatsApp templates
- View message delivery logs and failure rates
- Set retry policy (max retries, retry interval)

### 13.6 Donor Communication Preferences

Stored in the `donors` table:
- `comm_pref_email` (boolean, default true)
- `comm_pref_sms` (boolean, default false)
- `comm_pref_whatsapp` (boolean, default false)
- `phone` (required for SMS/WhatsApp)
- `phone_country_code`

Donor can update preferences via an unsubscribe/preferences link in every message.

### 13.7 Database Tables for Communications

**`message_queue`** — Unified outbound message log
- `id`, `channel` (email/sms/whatsapp), `recipient_type` (donor/salesperson/admin), `recipient_id` (FK), `recipient_address` (email or phone), `message_type` (receipt/donation_link/welcome/reminder/confirmation/report), `subject` (email only), `body_text` (plain text version), `body_html` (rich version, email/whatsapp), `attachment_path` (nullable — PDF receipt, etc.), `template_id` (FK, nullable), `related_donation_id` (FK, nullable), `related_link_id` (FK, nullable), `status` (queued/sending/sent/delivered/failed/bounced), `provider` (sendgrid/twilio/whatsapp/etc.), `provider_message_id`, `error_message` (nullable), `retry_count`, `max_retries`, `scheduled_at` (nullable — for delayed sends), `sent_at`, `delivered_at`, `opened_at` (nullable — email tracking), `clicked_at` (nullable — link tracking), `created_at`

**`message_templates`** — Reusable templates per channel
- `id`, `name`, `channel` (email/sms/whatsapp), `message_type`, `subject_template` (email only), `body_template_text`, `body_template_html` (email/whatsapp), `language` (en/he), `variables` (JSON — list of available merge fields), `whatsapp_template_name` (nullable — for approved templates), `active`, `created_at`, `updated_at`

**`comm_providers`** — Channel provider configuration
- `id`, `channel` (email/sms/whatsapp), `provider_name`, `api_key`, `api_secret` (nullable), `from_address` (email) / `from_number` (sms/whatsapp), `webhook_secret` (nullable — for delivery status callbacks), `is_active`, `is_default`, `config_json` (additional provider-specific settings), `created_at`, `updated_at`

### 13.8 Message Template Variables

All templates support merge fields that auto-populate:

| Variable | Description |
|----------|-------------|
| `{{donor_name}}` | Donor full name |
| `{{donor_first_name}}` | Donor first name |
| `{{amount}}` | Donation amount (formatted) |
| `{{donation_link}}` | Compressed donation URL |
| `{{receipt_number}}` | Receipt ID |
| `{{tax_id}}` | Organization tax ID |
| `{{org_name}}` | "Matat Mordechai" |
| `{{salesperson_name}}` | Salesperson who generated the link |
| `{{date}}` | Transaction or current date |
| `{{preset_amount}}` | Pre-filled amount (if set) |

### 13.9 Delivery Status Webhooks (Inbound)

Each provider can send delivery status updates back to our system:

- **SendGrid / SES:** Delivery, bounce, open, click events
- **Twilio SMS:** Delivered, undelivered, failed events
- **Twilio WhatsApp / Meta:** Delivered, read, failed events

These update the `message_queue.status` field for full delivery tracking.

---

## 14. Security Requirements

- All passwords hashed (bcrypt)
- Forced password change on first login for salespersons
- HTTPS everywhere
- Stripe handles all card data (PCI DSS compliance via Stripe Elements/Checkout)
- Session management with secure cookies
- Role-based access control (admin vs. salesperson)
- CSRF protection on all forms
- Rate limiting on login attempts

---

## 15. Future Considerations (Not in V1)

- International receipts (non-US)
- Multi-currency support
- Mobile app integration with push notifications
- Donor portal / login for donors to see their giving history
- Automated recurring commission payouts
- Tiered commission brackets UI builder

---

## 16. Summary of Key Decisions

| Item | Decision |
|------|----------|
| Organization Name | Matat Mordechai |
| Database | `matat` (existing) |
| Stripe Mode | Test/Live (admin toggle) |
| Auth | Temp login → hash key on password change |
| Commission | Admin choice: flat rate OR percentage per salesperson |
| Donation Min/Max | None |
| Donation Types | One-time + Recurring |
| Donor Required Fields | Name, Address, Email (must have) |
| Link Expiry | Never expires |
| Link Amount | Optional preset, donor can enter own |
| URL Tracking | `ref=` for salesperson, `aff=` for campaign |
| Receipt Format | US only, PDF email, matches sample template |
| Receipt Numbering | `MM-YYYY-NNNNN` — atomic, sequential, searchable |
| Tax ID Source | Database config table (not hardcoded) |
| Language | English + Hebrew toggle (RTL support) |
| Reports | Daily, Weekly, Monthly, Yearly, Per-Salesperson, Per-Campaign |
| Salesperson Transparency | Full access to their own sales data |
| Communication Channels | Email (V1), SMS (V1 ready), WhatsApp (V1 ready) |
| Message Architecture | Unified queue — all channels logged, retryable |
| Donor Comm Preferences | Per-donor opt-in per channel |

---

## 17. Claude Code Implementation Guide

> **This section is specifically written for Claude Code (Anthropic's CLI agent) to execute the full build.** Follow the phases in order. Each phase should be fully working and testable before moving to the next.

### 17.1 Project Directory Structure

```
matat/
├── app/
│   ├── __init__.py                    # Flask app factory, register blueprints
│   ├── config.py                      # Config classes (Dev, Prod, Test)
│   ├── extensions.py                  # db, bcrypt, mail, csrf, login_manager init
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                    # User model (admin + salesperson)
│   │   ├── donor.py                   # Donor model
│   │   ├── donation.py                # Donation model
│   │   ├── commission.py              # Commission model
│   │   ├── campaign.py                # Campaign model
│   │   ├── donation_link.py           # DonationLink model
│   │   ├── receipt.py                 # Receipt + ReceiptCounter models
│   │   ├── message.py                 # MessageQueue + MessageTemplate models
│   │   └── config_settings.py         # Config (org settings) model
│   ├── blueprints/
│   │   ├── __init__.py
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py              # Login, logout, change password
│   │   │   └── forms.py
│   │   ├── admin/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py              # Dashboard, reports, settings, user mgmt
│   │   │   ├── forms.py
│   │   │   └── reports.py             # Report generation logic
│   │   ├── salesperson/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py              # Dashboard, phone entry, link gen, my sales
│   │   │   └── forms.py
│   │   ├── donate/
│   │   │   ├── __init__.py
│   │   │   └── routes.py              # Public donation page, link resolver, success page
│   │   └── webhook/
│   │       ├── __init__.py
│   │       └── routes.py              # Stripe webhook endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── stripe_service.py          # Stripe API calls, PaymentIntent creation, customer mgmt
│   │   ├── commission_service.py      # Commission calculation with hierarchy logic
│   │   ├── receipt_service.py         # Receipt number generation, PDF creation
│   │   ├── link_service.py            # Short link generation, URL building with ref/aff
│   │   ├── email_service.py           # Email sending (SendGrid/SES/SMTP)
│   │   ├── sms_service.py             # SMS sending (Twilio) — stub for V1
│   │   └── whatsapp_service.py        # WhatsApp sending (Twilio) — stub for V1
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── decorators.py              # @admin_required, @salesperson_required, @login_required
│   │   ├── i18n.py                    # Language loading, translation helper t()
│   │   └── helpers.py                 # Formatting, short code generator, etc.
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css              # Main stylesheet
│   │   │   └── rtl.css                # RTL overrides for Hebrew
│   │   ├── js/
│   │   │   ├── main.js                # Common JS
│   │   │   ├── stripe-checkout.js     # Stripe Elements integration
│   │   │   ├── donation-polling.js    # Success page polling logic
│   │   │   └── language-toggle.js     # EN/HE switch
│   │   ├── fonts/
│   │   │   └── Assistant-Regular.ttf  # Hebrew-compatible font for PDFs
│   │   └── img/
│   │       └── logo.png               # Organization logo for receipts
│   ├── templates/
│   │   ├── base.html                  # Base layout with lang toggle, nav, flash messages
│   │   ├── base_rtl.html              # RTL variant (or use dir= toggle in base.html)
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   └── change_password.html
│   │   ├── admin/
│   │   │   ├── dashboard.html
│   │   │   ├── salespersons.html      # List, create, edit salespersons
│   │   │   ├── salesperson_form.html
│   │   │   ├── campaigns.html         # List, create, edit campaigns
│   │   │   ├── campaign_form.html
│   │   │   ├── commissions.html       # Pending commissions, mark paid
│   │   │   ├── reports.html           # Date-filtered income reports
│   │   │   ├── salesperson_report.html
│   │   │   ├── campaign_report.html
│   │   │   ├── receipt_lookup.html    # Search receipts by number/donor/date
│   │   │   └── settings.html          # Org name, tax ID, Stripe keys, logo
│   │   ├── salesperson/
│   │   │   ├── dashboard.html
│   │   │   ├── phone_entry.html       # Key in donation over phone
│   │   │   ├── send_link.html         # Generate & send donation link
│   │   │   ├── my_sales.html          # All their donations + commissions
│   │   │   └── my_payouts.html        # Commission payment history
│   │   ├── donate/
│   │   │   ├── donation_page.html     # Public donation form with Stripe Elements
│   │   │   └── success.html           # Post-payment polling page
│   │   ├── emails/
│   │   │   ├── receipt_en.html        # English receipt email template
│   │   │   ├── receipt_he.html        # Hebrew receipt email template
│   │   │   ├── donation_link_en.html  # English donation link email
│   │   │   ├── donation_link_he.html  # Hebrew donation link email
│   │   │   └── welcome_salesperson.html
│   │   └── pdf/
│   │       ├── receipt_en.html        # English receipt PDF template (WeasyPrint)
│   │       └── receipt_he.html        # Hebrew receipt PDF template (WeasyPrint)
│   └── i18n/
│       ├── en.json                    # English translations
│       └── he.json                    # Hebrew translations
├── migrations/                        # Flask-Migrate / Alembic
├── tests/
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_webhook.py
│   ├── test_commission.py
│   ├── test_receipt.py
│   └── test_donation_link.py
├── .env                               # Environment variables (NOT committed)
├── .env.example                       # Template for .env
├── .gitignore
├── requirements.txt
├── run.py                             # Entry point: from app import create_app
├── seed.py                            # Seed script: create admin, config, initial data
└── README.md
```

### 17.2 Environment Variables (`.env`)

```bash
# Flask
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=<generate-a-strong-random-key>

# Database
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/matat

# Stripe
STRIPE_TEST_SECRET_KEY=sk_test_...
STRIPE_LIVE_SECRET_KEY=sk_live_...
STRIPE_TEST_PUBLISHABLE_KEY=pk_test_...
STRIPE_LIVE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_MODE=test  # "test" or "live"

# Email (SendGrid example)
MAIL_PROVIDER=sendgrid  # sendgrid | ses | smtp
SENDGRID_API_KEY=SG....
MAIL_DEFAULT_SENDER=receipts@matatmordechai.org

# SMS (Twilio — V1 stubs)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# App
APP_DOMAIN=https://donate.matatmordechai.org
ORG_NAME=Matat Mordechai
```

### 17.3 Python Dependencies (`requirements.txt`)

```
Flask==3.1.*
Flask-SQLAlchemy==3.1.*
Flask-Migrate==4.0.*
Flask-Login==0.6.*
Flask-WTF==1.2.*
Flask-Bcrypt==1.0.*
PyMySQL==1.1.*
cryptography==44.*
stripe==11.*
weasyprint==63.*
sendgrid==6.*
python-dotenv==1.0.*
gunicorn==23.*
shortuuid==1.0.*
Pillow==11.*
```

### 17.4 Build Phases (Execute in Order)

---

#### **PHASE 1: Project Skeleton & Database**

**Goal:** Flask app boots, connects to MySQL, all tables created, admin seed works.

**Steps:**
1. Create the full directory structure above
2. Create `app/__init__.py` with Flask app factory using `create_app()` pattern
3. Create `app/config.py` reading from `.env` with Dev/Prod/Test configs
4. Create `app/extensions.py` initializing SQLAlchemy, Bcrypt, LoginManager, CSRFProtect
5. Create ALL models in `app/models/` matching the schema in Section 8 of this spec exactly:
   - Every model must include `deleted_at` where specified (soft delete)
   - Use `db.Column(db.DateTime, nullable=True)` for `deleted_at`
   - Add a `is_deleted` property: `return self.deleted_at is not None`
   - Add a class method `query_active()` that filters `deleted_at.is_(None)`
6. Create `run.py` entry point
7. Initialize Flask-Migrate: `flask db init`, `flask db migrate`, `flask db upgrade`
8. Create `seed.py` that:
   - Creates the `config` row (org_name="Matat Mordechai", tax_id placeholder, org_prefix="MM")
   - Creates the initial admin user (username: `admin`, temp password: `changeme123`, `is_temp_password=True`)
   - Creates the first `receipt_counter` row (org_prefix="MM", fiscal_year=current year, last_sequence=0)
9. **Test:** Run `python seed.py`, verify tables exist and data is seeded

---

#### **PHASE 2: Authentication**

**Goal:** Login page works, admin can log in, forced password change on temp passwords, role-based redirects.

**Steps:**
1. Create `app/blueprints/auth/routes.py`:
   - `GET/POST /login` — username + password, bcrypt verify, Flask-Login `login_user()`
   - `GET/POST /change-password` — required if `current_user.is_temp_password == True`
   - `GET /logout` — `logout_user()`, redirect to login
2. Create `app/utils/decorators.py`:
   - `@admin_required` — checks `current_user.role == 'admin'`
   - `@salesperson_required` — checks `current_user.role == 'salesperson'`
   - Both should also check `is_temp_password` and redirect to change-password if True
3. Create login template with basic styling
4. After login: admin → `/admin/dashboard`, salesperson → `/salesperson/dashboard`
5. Rate limit login attempts (5 per minute per IP using Flask-Limiter or manual counter)
6. **Test:** Login as admin, get forced to change password, login again, reach admin dashboard stub

---

#### **PHASE 3: Stripe Webhook (Core Engine)**

**Goal:** Stripe webhook endpoint receives events, captures fees from Balance Transaction, creates donation records, calculates commission.

This is the most critical phase. Build the webhook handler BEFORE the frontend donation pages.

**Steps:**
1. Create `app/blueprints/webhook/routes.py`:
   - `POST /api/stripe/webhook`
   - Verify signature using `stripe.Webhook.construct_event()` with `STRIPE_WEBHOOK_SECRET`
   - Exempt this route from CSRF protection
   - Handle these events:
     - `payment_intent.succeeded` → create/update donation record
     - `charge.succeeded` → retrieve `BalanceTransaction` for fee data
     - `invoice.paid` → recurring donation installment
     - `charge.refunded` → update status, record `fee_refunded` and `fee_lost_on_refund`
     - `charge.failed` → log failure
   - Return `200` immediately, process heavy work (PDF, email) in the same request for V1 (move to background queue in V2)
2. Create `app/services/stripe_service.py`:
   - `retrieve_balance_transaction(bt_id)` → returns fee, fee_details, net
   - `create_payment_intent(amount, currency, customer_id, metadata)` → returns PaymentIntent
   - `create_customer(email, name, metadata)` → returns Stripe Customer
   - `get_or_create_customer(donor)` → checks DB first, creates in Stripe if needed
3. Create `app/services/commission_service.py`:
   - `calculate_commission(donation)` implementing the 4-level hierarchy:
     ```python
     def calculate_commission(donation):
         # 1. Check campaign override
         if donation.campaign_id:
             campaign = Campaign.query.get(donation.campaign_id)
             if campaign and campaign.commission_override_type:
                 return compute(donation.amount, campaign.commission_override_type, campaign.commission_override_rate)
         # 2. Check salesperson custom rate
         if donation.salesperson_id:
             salesperson = User.query.get(donation.salesperson_id)
             if salesperson and salesperson.commission_type:
                 return compute(donation.amount, salesperson.commission_type, salesperson.commission_rate)
         # 3. System default
         config = ConfigSettings.query.first()
         if config and config.default_commission_type:
             return compute(donation.amount, config.default_commission_type, config.default_commission_rate)
         # 4. No commission
         return 0
     ```
4. **Test with Stripe CLI:**
   - Install Stripe CLI: `stripe listen --forward-to localhost:5000/api/stripe/webhook`
   - Trigger test events: `stripe trigger payment_intent.succeeded`
   - Verify donation record created in DB with correct fee data

---

#### **PHASE 4: Receipt System**

**Goal:** Atomic receipt numbering works, PDF generated matching the sample template, PDF stored on disk.

**Steps:**
1. Create `app/services/receipt_service.py`:
   - `generate_receipt_number()` — atomic SQL using the INSERT IGNORE + UPDATE pattern from Section 6
   - `generate_receipt_pdf(donation, donor, language='en')` — uses WeasyPrint to render HTML template to PDF
   - `store_receipt(pdf_bytes, receipt_number)` — saves to `receipts/` directory, returns path
   - `get_receipt_by_number(receipt_number)` — lookup for admin
2. Create PDF HTML templates in `app/templates/pdf/`:
   - `receipt_en.html` — matches the uploaded Pirchei Shoshanim sample layout:
     - Organization logo at top
     - Date, donor name/address, receipt number
     - Thank you message
     - Transaction table (date, status, sender, type, amount)
     - Stripe transaction number
     - Donation amount bold
     - Tax ID from config table
     - "No goods or services" disclaimer
   - `receipt_he.html` — same layout, RTL, Hebrew text, embedded Assistant font
3. Download and save `Assistant-Regular.ttf` to `app/static/fonts/`
4. **Test:** Generate a receipt for a test donation, open the PDF, verify it looks like the sample

---

#### **PHASE 5: Donation Link System**

**Goal:** Salesperson can generate short links with `ref=` and `aff=`, links resolve to donation page with pre-filled data.

**Steps:**
1. Create `app/services/link_service.py`:
   - `generate_short_code()` — 8-char alphanumeric using `shortuuid`
   - `build_donation_url(short_code, ref_code, aff_code, preset_amount, donor_name, donor_email)` — constructs full URL with query params
   - `resolve_link(short_code)` — looks up `donation_links` table, returns all associated data
2. Create `app/blueprints/donate/routes.py`:
   - `GET /d/<short_code>` — resolves link, redirects to donation page with params
   - `GET /donate` — public donation page (accepts `ref`, `aff`, `amt`, `name`, `email` query params)
   - `POST /donate/create-payment-intent` — AJAX endpoint, creates Stripe PaymentIntent with metadata
   - `GET /donate/success` — success page with polling logic
   - `GET /api/donation/status?pi=<payment_intent_id>` — polling endpoint for success page
3. Create `app/static/js/stripe-checkout.js`:
   - Initialize Stripe Elements with the publishable key
   - Mount card element (and optionally ACH/bank element)
   - On submit: call `/donate/create-payment-intent`, confirm payment with Stripe.js
   - On success: redirect to `/donate/success?pi=<payment_intent_id>`
4. Create `app/static/js/donation-polling.js`:
   - Poll `/api/donation/status` every 2 seconds, max 15 attempts
   - Show spinner while waiting
   - Show confirmation + receipt number when found
   - Show graceful fallback message if max attempts reached
5. Create `app/templates/donate/donation_page.html`:
   - Donor fields: first name, last name, email (required), address, city, state, zip
   - Amount field (pre-filled if `amt` param present)
   - One-time / Recurring toggle
   - Stripe Elements card input
   - Submit button
   - Pre-fill fields from query params
6. **Test:** Generate a link as salesperson, open it, complete a test donation, verify webhook fires and credits the salesperson

---

#### **PHASE 6: Email System**

**Goal:** Receipts emailed as PDF attachment, donation links emailed, salesperson welcome emails sent.

**Steps:**
1. Create `app/services/email_service.py`:
   - `send_email(to, subject, html_body, attachments=None)` — provider-agnostic
   - Provider implementations: `_send_sendgrid()`, `_send_ses()`, `_send_smtp()`
   - All sends logged to `message_queue` table
2. Create email HTML templates in `app/templates/emails/`
3. Integrate into webhook flow: after receipt PDF is generated, email it to donor
4. Integrate into link flow: when salesperson sends a link, email it to donor
5. **Test:** Complete a donation, verify receipt email arrives with PDF attachment

---

#### **PHASE 7: Salesperson Portal**

**Goal:** Salesperson can log in, see dashboard, key in phone donations, generate links, view their sales and payouts.

**Steps:**
1. Create `app/blueprints/salesperson/routes.py`:
   - `GET /salesperson/dashboard` — totals (today, week, month, all-time), recent donations, commission summary
   - `GET/POST /salesperson/phone-entry` — form to key in donation + process via Stripe
   - `GET/POST /salesperson/send-link` — form to generate donation link + send via email/SMS/WhatsApp
   - `GET /salesperson/my-sales` — paginated list of all their donations with commission status
   - `GET /salesperson/my-payouts` — commission payment history
2. All queries filtered by `current_user.id` — salesperson can ONLY see their own data
3. Show commission rate source when campaign override applies (e.g., "PURIM2026 campaign rate: 15%")
4. **Test:** Login as salesperson, key in a phone donation, generate a link, verify both appear in My Sales

---

#### **PHASE 8: Admin Panel**

**Goal:** Full admin functionality — user management, campaign management, commission payouts, reports, receipt lookup, settings.

**Steps:**
1. Create `app/blueprints/admin/routes.py`:
   - Dashboard: `GET /admin/dashboard`
   - Salesperson CRUD: `GET/POST /admin/salespersons`, `/admin/salesperson/<id>/edit`, `/admin/salesperson/<id>/deactivate`
   - When creating salesperson: generate `ref_code` (SP-NNNN), set `is_temp_password=True`
   - Campaign CRUD: `GET/POST /admin/campaigns`, `/admin/campaign/<id>/edit`
   - Commission management: `GET /admin/commissions`, `POST /admin/commission/<id>/mark-paid`
   - Receipt lookup: `GET /admin/receipts?q=<search>` — search by receipt number, donor name/email, date range
   - Settings: `GET/POST /admin/settings` — org name, tax ID, Stripe mode toggle, logo upload
2. Create `app/blueprints/admin/reports.py`:
   - `GET /admin/reports/income` — filterable by daily/weekly/monthly/yearly, date range
   - `GET /admin/reports/salesperson/<id>` — per-salesperson breakdown
   - `GET /admin/reports/campaign/<id>` — per-campaign breakdown
   - `GET /admin/reports/export?type=csv` — CSV/Excel export
   - All reports must show: gross donations, Stripe fees, net amount, commissions, refunds, fee losses on refunds
3. **Test:** Create a salesperson, create a campaign, process donations through various flows, run reports

---

#### **PHASE 9: Hebrew / RTL & i18n**

**Goal:** Full English ↔ Hebrew toggle, RTL layout, Hebrew PDF receipts.

**Steps:**
1. Create `app/i18n/en.json` and `app/i18n/he.json` with ALL UI strings:
   - Navigation, buttons, form labels, placeholders, flash messages, report headers, email subjects
2. Create `app/utils/i18n.py`:
   - `t(key, lang=None)` — returns translated string, falls back to English
   - `get_current_language()` — from session, user pref, or query param
3. Update `base.html`:
   - Language toggle button (EN | עב) in header
   - `<html dir="{{ 'rtl' if lang == 'he' else 'ltr' }}" lang="{{ lang }}">`
   - Load `rtl.css` when Hebrew is active
4. Create `app/static/css/rtl.css`:
   - Flip all directional properties
   - Use `[dir="rtl"]` selectors
5. Create `app/static/js/language-toggle.js`:
   - On toggle: set cookie/session, reload page
6. Update ALL templates to use `{{ t('key') }}` instead of hardcoded English strings
7. Generate Hebrew PDF receipts using WeasyPrint with embedded Assistant font
8. **Test:** Toggle to Hebrew, verify full RTL layout, generate Hebrew receipt PDF

---

#### **PHASE 10: SMS & WhatsApp Stubs**

**Goal:** Service layer ready, admin can configure, actual sending stubbed with logging.

**Steps:**
1. Create `app/services/sms_service.py`:
   - `send_sms(to_phone, body)` — if Twilio configured, send via Twilio; otherwise log to `message_queue` with `status=stub`
2. Create `app/services/whatsapp_service.py`:
   - `send_whatsapp(to_phone, template_name, params)` — same stub pattern
3. In salesperson "Send Link" form, add channel selector: Email | SMS | WhatsApp | Copy Link
4. `comm_providers` table seeded with placeholder rows for each channel
5. Admin settings page has enable/disable toggles per channel
6. **Test:** Select SMS channel, verify message logged to `message_queue` but not actually sent

---

### 17.5 Deployment Notes (DigitalOcean)

```bash
# Server setup
sudo apt update && sudo apt install python3-pip python3-venv mysql-server nginx
# WeasyPrint system dependencies (CRITICAL — WeasyPrint needs these)
sudo apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev libcairo2

# App setup
cd /var/www/matat
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Database
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS matat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
flask db upgrade
python seed.py

# Run with Gunicorn behind Nginx
gunicorn -w 4 -b 127.0.0.1:5000 run:app

# Or use PM2 (if already in use on the server)
pm2 start "gunicorn -w 4 -b 127.0.0.1:5000 run:app" --name matat

# Stripe webhook registration
# In Stripe Dashboard → Developers → Webhooks → Add endpoint:
# URL: https://donate.matatmordechai.org/api/stripe/webhook
# Events: payment_intent.succeeded, charge.succeeded, charge.refunded, charge.failed, invoice.paid, customer.subscription.created, customer.subscription.deleted
```

### 17.6 Critical Reminders for Claude Code

1. **MySQL charset:** ALL tables must use `CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci` for Hebrew support
2. **Soft deletes:** NEVER use `db.session.delete()`. Always set `deleted_at = datetime.utcnow()`. All queries must filter `deleted_at.is_(None)` by default.
3. **Stripe amounts:** Stripe works in **cents**. Always `amount * 100` when sending to Stripe, `amount / 100` when displaying.
4. **Receipt numbering:** MUST be atomic (inside a DB transaction). Never generate receipt numbers outside a transaction.
5. **Webhook idempotency:** Use `stripe_payment_intent_id` as a unique key. If a duplicate webhook arrives, skip it — don't create duplicate donations.
6. **CSRF exempt:** The Stripe webhook route MUST be exempt from CSRF protection.
7. **Secrets:** Never hardcode API keys. Always read from `.env` via `os.environ`.
8. **Hebrew font:** WeasyPrint will NOT render Hebrew correctly without an embedded `.ttf` font. This is non-negotiable.
9. **Fee capture:** Always call `stripe.BalanceTransaction.retrieve()` to get actual fees. Never calculate fees yourself.
10. **Commission hierarchy:** Campaign override → Salesperson rate → System default → None. Code this exactly.
