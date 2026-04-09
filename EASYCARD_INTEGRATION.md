# EasyCard Payment Integration - Implementation Guide

## Overview
Add EasyCard (EasycardNG) as a payment processor. EasyCard is a PCI DSS Level 1 certified Israeli payment gateway operating since 2003. Supports credit cards, Bit, Google Pay, recurring payments, and bank transfers. Authorization through Shva (Israeli interbank clearing).

## Authentication
- Terminal Number: merchant terminal identifier
- API Key / Private Key: obtained after merchant registration
- Likely Bearer token or custom header (verify via Swagger docs)

### Environments
- API Docs (Swagger): https://merchant.e-c.co.il/api-docs/index.html
- GitHub: https://github.com/EasycardNG/API
- Contact: office@e-c.co.il or 073-2615690

---

## PHASE 1: Database and Config

### ConfigSettings model
- easycard_terminal_number = db.Column(db.String(100), nullable=True)
- easycard_api_key = db.Column(db.String(255), nullable=True)
- easycard_enabled = db.Column(db.Boolean, default=False)

### Donation model
- easycard_transaction_id = db.Column(db.String(255), unique=True, nullable=True)
- easycard_token = db.Column(db.String(255), nullable=True)
- easycard_confirmation = db.Column(db.String(255), nullable=True)

---

## PHASE 2: Integration Methods

### A. Redirect (Hosted Payment Page)
- Customer redirected to EasyCard hosted payment page
- No SSL required on your site
- After payment, redirect back to success/failure URL
- PCI compliant - card data never touches your server

### B. iframe (Embedded Payment Page)
- EasyCard form embedded in iframe on your page
- SSL certificate IS required on your site
- iframe must include attribute: allow="payment"
- Card data handled within EasyCard iframe

---

## PHASE 3: Transaction Types

- J4 -- Immediate one-time charge (standard payment)
- J5 -- Token billing / reservation (tokenization and recurring)

---

## PHASE 4: Supported Payment Methods

- Credit Cards: Visa, Mastercard, AMEX, Isracard, Diners
- Bit (Israeli mobile payment)
- Google Pay (enable in terminal settings, provide Google Merchant ID)
- Bank Transfers
- Standing Orders / Recurring Payments

### Google Pay Setup
1. Enable Google Pay in terminal settings
2. Set your Google Merchant ID
3. Supported auth: PAN_ONLY (phone transactions), CRYPTOGRAM_3DS
4. Supported networks: AMEX, MASTERCARD, VISA
5. Merchants do NOT send Google Pay data via API -- EasyCard handles it

---

## PHASE 5: Webhooks

- Configure webhook endpoint URL in your terminal settings
- Webhooks deliver transaction status (success, failure) to your server
- Full payload schema available in Swagger docs

---

## PHASE 6: Tokenization and Recurring

- J5 deal type for token billing
- Tokens allow recurring charges without re-entering card details
- Standing orders for automatic recurring charges

---

## PHASE 7: Refunds

- Refund endpoint available via API
- Details in Swagger docs at merchant.e-c.co.il/api-docs/

---

## PHASE 8: Additional Features

- Payment links (send to donors directly)
- Split payments and deposit collection
- Automatic invoice issuance
- Multiple currency support
- 3D Secure

---

## Important Notes

1. PCI DSS LEVEL 1: Highest level of compliance. Use redirect or iframe.

2. SWAGGER DOCS: Full endpoint details at https://merchant.e-c.co.il/api-docs/index.html (requires JS rendering, may need auth).

3. GITHUB: https://github.com/EasycardNG/API has README and integration guides.

4. WOOCOMMERCE PLUGIN: Reverse-engineer exact API calls from the WordPress plugin source: https://wordpress.org/plugins/wc-payment-gateway-easycard/

5. CODE SAMPLES: PHP and ASP.NET samples available from EasyCard directly.

6. CONTACT FOR API CREDENTIALS: office@e-c.co.il or 073-2615690

## File Changes Summary
- app/models/config_settings.py - Add easycard fields
- app/models/donation.py - Add easycard fields
- app/services/easycard_service.py - NEW
- app/blueprints/webhook/routes.py - Add easycard webhook
- app/blueprints/donate/routes.py - Add easycard flow
- app/blueprints/admin/routes.py - Add easycard settings
- migrations/ - New migration

## Testing Checklist
- [ ] Terminal credentials configured
- [ ] Hosted page / iframe loads
- [ ] Credit card payment completes
- [ ] Bit payment completes
- [ ] Webhook received
- [ ] Donation created with payment_provider=easycard
- [ ] Token saved (J5), recurring works
- [ ] Refund works
- [ ] Google Pay works (if enabled)
