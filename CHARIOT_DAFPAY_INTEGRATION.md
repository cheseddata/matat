# Chariot / DAFpay Integration - Implementation Guide

## Overview
Chariot (givechariot.com / dafpay.com) is THE universal DAF integration layer. One button covers 1,151+ DAF providers including The Donors Fund, OJC Fund, Jewish Communal Fund, Fidelity Charitable, Schwab Charitable, and more. Named TIME Best Invention of 2025. This is the single most important DAF integration for Matat Mordechai.

## Authentication
- API Key from Chariot dashboard
- Webhook verification: HMAC-SHA256 using api_key as key, payload as message, Base64 encoded

### Environments
- Production API: https://api.givechariot.com
- Sandbox API: https://sandboxapi.givechariot.com
- Developer Docs: https://docs.givechariot.com
- API Reference: https://docs.givechariot.com/api

---

## PHASE 1: Database and Config

### ConfigSettings model
- chariot_api_key = db.Column(db.String(255), nullable=True)
- chariot_connect_id = db.Column(db.String(255), nullable=True)
- chariot_enabled = db.Column(db.Boolean, default=False)

### Donation model
- chariot_grant_id = db.Column(db.String(255), unique=True, nullable=True)
- chariot_tracking_id = db.Column(db.String(255), nullable=True)
- daf_provider = db.Column(db.String(255), nullable=True)
- is_daf_donation = db.Column(db.Boolean, default=False)

---

## PHASE 2: API Endpoints

### Register Nonprofit
POST /nonprofits
- Register your nonprofit by EIN
- Returns 201 (new) or 200 (existing)

### Create Connect Instance
POST /connects
- Creates a Connect ID (CID) for your nonprofit
- CID is used to initialize the DAFpay web component

### Query Grants
GET /grants (with filters)
- Track grants generated through Connect
- Includes Tracking ID and External Grant ID

### Transaction Management
- Track and reconcile DAF gift data
- Grant status webhooks

---

## PHASE 3: Frontend Integration (DAFpay Button)

### Add DAFpay Web Component to Donation Page

The DAFpay button is a single-line web component:

1. Include Chariot script on your donation page
2. Initialize with your Connect ID (CID)
3. Button appears alongside other payment options
4. Donor clicks DAFpay -> authenticates with their DAF provider -> confirms grant -> done

### Flow:
1. Donor clicks DAFpay button on your donation page
2. Chariot popup opens
3. Donor selects their DAF provider (Donors Fund, OJC, JCF, Fidelity, etc.)
4. Donor logs into their DAF account
5. Donor confirms grant amount
6. Grant initiated
7. Chariot sends webhook to your server
8. Funds disbursed to your nonprofit

---

## PHASE 4: Webhook Handler

Chariot sends webhook events for grant status changes.

### Verification:
- Compute HMAC-SHA256 of the raw webhook payload using your api_key
- Base64 encode the result
- Compare with the signature header

### Handler logic:
1. Verify webhook signature
2. Extract grant details (amount, donor info, DAF provider, tracking ID)
3. Create Donation record with:
   - payment_provider = "chariot_daf"
   - is_daf_donation = True
   - daf_provider = "The Donors Fund" / "OJC" / "JCF" / etc.
4. Generate receipt
5. Calculate commission
6. Return HTTP 200

---

## PHASE 5: Supported DAF Providers (Jewish)

Through one DAFpay button, donors can give from:
- The Donors Fund
- OJC Fund (Orthodox Jewish Chamber)
- Jewish Communal Fund (JCF)
- Combined Jewish Philanthropies (CJP)
- Jewish Federation DAFs (various cities)
- Fidelity Charitable
- Schwab Charitable
- Vanguard Charitable
- National Philanthropic Trust
- 1,141+ more providers

---

## Important Notes

1. ONE BUTTON COVERS ALL: Single DAFpay integration covers every major Jewish and secular DAF.

2. DISBURSEMENT: If registered with Chariot, funds go directly to your bank via ACH/check/EFT. If not registered, funds go through DAFpay Network (DPN) minus fees.

3. PROCESSING: DAF grants take longer than credit cards. Typical: 3-10 business days depending on DAF provider.

4. FEES: Chariot charges 2.9% processing fee on DAF donations.

5. SANDBOX: Full test environment at sandboxapi.givechariot.com.

6. REGISTER YOUR NONPROFIT: First step is POST /nonprofits with your EIN to register.

---

## File Changes Summary
- app/models/config_settings.py - Add chariot fields
- app/models/donation.py - Add chariot/DAF fields
- app/services/chariot_service.py - NEW - API client
- app/blueprints/webhook/routes.py - Add /chariot/webhook POST
- app/blueprints/donate/routes.py - Add DAFpay flow
- app/blueprints/admin/routes.py - Add chariot settings
- app/templates/donate/donation_page.html - Add DAFpay button
- migrations/ - New migration

## Testing Checklist
- [ ] Chariot API key configured in admin
- [ ] Nonprofit registered via POST /nonprofits
- [ ] Connect ID created via POST /connects
- [ ] DAFpay button appears on donation page
- [ ] Test DAF donation in sandbox
- [ ] Webhook received and verified (HMAC-SHA256)
- [ ] Donation record created with is_daf_donation=True
- [ ] DAF provider name captured
- [ ] Receipt generated
- [ ] Commission calculated
