# PayMe Payment Integration - Implementation Guide

## Overview
Add PayMe as a payment processor. PayMe offers hosted payment pages, hosted fields (embedded secure inputs), and direct API for PCI-certified merchants. Supports credit cards, Bit, Apple Pay, installments, and Israeli direct debit.

## Authentication
- seller_payme_id: Your merchant/seller PayMe ID (from Settings page in dashboard)
- Passed as parameter in API requests

### Environments
- Sandbox: https://sandbox.payme.io/api/
- Production: separate URL (obtain from PayMe)
- Docs: https://docs.payme.io/
- Apiary: https://paymeapi.docs.apiary.io/

---

## PHASE 1: Database and Config

### ConfigSettings model
- payme_seller_id = db.Column(db.String(255), nullable=True)
- payme_api_key = db.Column(db.String(255), nullable=True)
- payme_test_mode = db.Column(db.Boolean, default=True)
- payme_enabled = db.Column(db.Boolean, default=False)

### Donation model
- payme_sale_id = db.Column(db.String(255), unique=True, nullable=True)
- payme_buyer_key = db.Column(db.String(255), nullable=True)
- payme_transaction_id = db.Column(db.String(255), nullable=True)

---

## PHASE 2: Integration Options

### A. Hosted Payment Page (Recommended - No PCI Required)
Call generate-payment endpoint, get URL, redirect donor.

### B. Hosted Fields (JSAPI) - Embedded in Your Page
Script: https://cdn.payme.io/hf/v1/hostedfields.js

Flow:
1. Include script tag
2. const instance = await PayMe.create(apiKey, { testMode: true })
3. const fields = instance.hostedFields()
4. fields.create('cardNumber'), fields.create('cardExpiration'), fields.create('cvc')
5. Mount to DOM: cardNumber.mount('#card-number-container')
6. Tokenize: const result = await fields.tokenize({ ... })
7. Send token to backend for completion

### C. Direct API (PCI-DSS Level 1 Required)
Full card data sent directly. Not recommended unless PCI certified.

---

## PHASE 3: Key API Endpoints

### Generate Payment (Hosted Page)
POST /generate-payment
Returns URL to redirect donor to PayMe hosted page.

### Generate Sale
POST /generate-sale
Parameters:
- seller_payme_id (required)
- sale_price: amount in agorot/cents (required)
- product_name: description (required)
- currency: "ILS", "USD", or "EUR" (required)
- sale_callback_url: webhook URL (required)
- sale_return_url: redirect URL
- installments: 1-12 (ILS + Israeli cards only)
- language: "he" or "en"
- buyer_key: token for returning buyer
- capture_buyer: 1 to tokenize buyer
- buyer_name, buyer_email, buyer_phone, buyer_social_id

### Generate Sale with Token
POST /generate-sale (with buyer_key parameter)
Charges previously saved buyer without re-entering card details.

### Capture Buyer Token
Set capture_buyer in generate-sale. Returns buyer_key.

### Authorization (Pre-Auth) and Capture
Pre-auth reserves amount for up to 168 hours (7 days).
Capture triggers actual settlement.

### Refund
PUT /refund (with sale GUID)
Need sale_payme_id to process refund.

### Subscriptions
POST /subscriptions
Manage recurring billing.

---

## PHASE 4: Webhook / Callback

sale_callback_url receives POST within ~5 seconds of status change.
Callback includes signature for validation.
Your server must return proper acknowledgment or PayMe retries.

---

## PHASE 5: Currency and Payment Methods

Currencies: ILS (default), USD and EUR (email support@payme.io to enable)
Installments: ILS + Israeli cards only, 1-12 payments
Payment methods: Credit card, Bit, Apple Pay, Direct Debit (Israeli bank)

---

## PHASE 6: Israeli Direct Debit

Uses generate-sale with direct debit parameters.
Buyer provides Israeli bank account details and social ID.
Creates a direct debit mandate for recurring charges.

---

## Important Notes
1. AMOUNTS IN AGOROT: sale_price is in smallest currency unit (agorot for ILS)
2. SIGNATURE VALIDATION: Verify webhook signatures
3. INSTALLMENTS ILS ONLY: Foreign cards/currencies cannot use installments
4. USD/EUR BY REQUEST: Email support@payme.io to enable
5. TEST CARDS: Specific test cards for sandbox at docs.payme.io

## File Changes Summary
- app/models/config_settings.py - Add payme fields
- app/models/donation.py - Add payme fields
- app/services/payme_service.py - NEW
- app/blueprints/webhook/routes.py - Add /payme/webhook POST
- app/blueprints/donate/routes.py - Add payme flow
- app/blueprints/admin/routes.py - Add payme settings
- migrations/ - New migration

## Testing Checklist
- [ ] Hosted payment page loads
- [ ] Payment completes, webhook received
- [ ] Donation created with payment_provider=payme
- [ ] Token (buyer_key) saved
- [ ] Token charge works
- [ ] Refund works
- [ ] ILS and USD work
- [ ] Installments work (ILS)
