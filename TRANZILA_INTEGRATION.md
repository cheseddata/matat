# Tranzila Payment Integration - Implementation Guide

## Overview
Add Tranzila as a payment processor for the Matat Mordechai donation platform. Tranzila is Israel oldest and largest payment gateway with modern REST APIs, iframe integration, and tokenization support.

## Tranzila API Reference

### Authentication
Every API call requires custom HTTP headers:
- X-tranzila-api-app-key -- Application key supplied by Tranzila

Gateway credentials:
- terminal_name (also called supplier) -- Your Tranzila merchant terminal ID
- terminal_password (also called TranzilaPW) -- Required for handshake/iframe operations
- app_key -- Application key
- secret -- Application secret

Contact Tranzila to obtain credentials and a test terminal.

### API Versions

Legacy API (CGI-based):
- Charge: POST https://secure5.tranzila.com/cgi-bin/tranzila71u.cgi
- Token charge: POST https://secure5.tranzila.com/cgi-bin/tranzila31tk.cgi

Modern API V2 (JSON/REST):
- Base: https://api.tranzila.com
- Payment request: POST https://api.tranzila.com/v1/pr/create
- Reports: https://report.tranzila.com/v1/transaction

Full Docs: https://docs.tranzila.com/

---

## PHASE 1: Database and Config

### 1a. Add Tranzila fields to ConfigSettings model (app/models/config_settings.py)

Add these columns:
- tranzila_terminal_name = db.Column(db.String(100), nullable=True)
- tranzila_terminal_password = db.Column(db.String(255), nullable=True)
- tranzila_app_key = db.Column(db.String(255), nullable=True)
- tranzila_enabled = db.Column(db.Boolean, default=False)

### 1b. Add Tranzila fields to Donation model (app/models/donation.py)

- tranzila_transaction_id = db.Column(db.String(255), unique=True, nullable=True)
- tranzila_confirmation = db.Column(db.String(255), nullable=True)
- tranzila_token = db.Column(db.String(255), nullable=True)

### 1c. Migration
Run: flask db migrate -m "add tranzila fields"
Then: flask db upgrade

---

## PHASE 2: iframe Integration (RECOMMENDED - PCI Compliant)

### 2a. iframe URL
https://direct.tranzila.com/{terminal_name}/iframenew.php

### 2b. Flow
1. Your server requests a handshake token from Tranzila (requires terminal_name + terminal_password)
2. Tranzila returns a handshake token
3. Embed iframe with the handshake token
4. Customer enters card details in iframe
5. On completion, validate via 3-sided handshake (server-to-server verification)

### 2c. iframe Modes
- J5 (default) -- Token billing (tokenize card for future use)
- J4 -- One-time payment (charge immediately)

### 2d. iframe Parameters
- aid: Account/donor ID
- action: "single_payment" for one-time charges
- amount: Charge amount (float)
- installments.number_of_payments: Number of installments
- tokenize_on_single_payment: true to also save token after single payment
- ok_page: Success redirect URL
- fail_page: Failure redirect URL

### 2e. Handshake Verification
After iframe completes, verify server-to-server:
- URL: /paymentgateways/okPage
- Parameters: name=Tranzila, thtk={handshake_token}, index={index}, aid={account_id}, redirect=0
- Returns: status + masked card details

---

## PHASE 3: Legacy API Parameters (Server-to-Server)

### 3a. Required Parameters for a Charge

- supplier: Terminal name (merchant ID)
- TranzilaPW: Terminal password
- ccno: Credit card number (only if PCI certified!)
- expdate: Expiration MMYY (4 digits)
- sum: Amount to charge
- currency: 1=ILS, 2=USD, 3=GBP, 4=EUR, 5=JPY
- tranmode: Transaction type (see below)

### 3b. Optional Parameters
- mycvv: CVV (3 digits)
- myid: Cardholder ID number
- cred_type: 1=regular, 2=installments, 3=credit
- fpay: First payment amount (installments)
- spay: Subsequent payment amount
- npay: Number of additional payments minus 1
- TranzilaTK: Token for token-based charges

### 3c. tranmode Values
- (empty): Regular debit/charge
- V: Verification only
- F: Forced transaction
- C: Credit (refund)
- VK: Verify + create token
- AK: Regular debit + create token

---

## PHASE 4: Tokenization

### Creating a Token
- Use tranmode=VK (verify + create token) or tranmode=AK (charge + create token)
- Token returned as TranzilaTK

### Using a Token
- POST to https://secure5.tranzila.com/cgi-bin/tranzila31tk.cgi
- Send TranzilaTK={token} instead of ccno/expdate

### iframe Tokenization
- Default iframe mode (J5) creates a token
- Single payment mode can also tokenize via tokenize_on_single_payment=true

---

## PHASE 5: Refund / Void

### Legacy API Refund
- Same endpoint: https://secure5.tranzila.com/cgi-bin/tranzila71u.cgi
- Set tranmode=C (credit)
- Include original transaction reference

### Modern API V2 Refund
Parameters: amount, currency, transactionReference, authorizationNumber, card details or token

### Void
Parameters: transactionReference, authorizationNumber
Note: Void may NOT work on test/sandbox accounts

---

## PHASE 6: Additional Features

### 3D Secure
- Supported (3DS V2)
- Docs: https://docs.tranzila.com/docs/payments-billing/1fvxs3w4ntm6d-tranzila-api-3-ds

### Bit Payment (Israeli mobile payment)
- Docs: https://docs.tranzila.com/docs/payments-billing/dcljft4y7sgj2-bit

### Standing Orders (Recurring)
- Docs: https://docs.tranzila.com/docs/payments-billing/7lwf8jetxm6oq-create-a-standing-order

### Invoices
- Separate invoice API
- Docs: https://docs.tranzila.com/docs/invoices/

### Hosted Fields
- Embed individual card input fields hosted on Tranzila servers within your own page design
- Docs: https://docs.tranzila.com/docs/payments-billing/o033w842qo397-hosted-fields

---

## PHASE 7: Currency Support

Currency codes:
- 1 = ILS (Israeli New Shekel)
- 2 = USD
- 3 = GBP
- 4 = EUR
- 5 = JPY

Modern API uses standard codes: "ILS", "USD", etc.

---

## PHASE 8: Webhook / Callback

- iframe supports ok_page and fail_page redirect URLs
- 3-sided handshake serves as server-to-server verification
- No traditional IPN webhook; Tranzila relies on handshake verification and redirect callbacks

---

## PHASE 9: Sandbox / Test

- Tranzila provides test terminals for sandbox usage
- Same API endpoints (terminal name determines test vs production)
- Void operations may NOT work on test accounts
- Contact Tranzila to get sandbox credentials

---

## Important Notes

1. PCI COMPLIANCE: Use the iframe or hosted fields approach. Never handle raw card numbers server-side unless PCI certified.

2. HANDSHAKE VERIFICATION: Always verify transaction server-to-server after iframe completion. Do not trust redirect parameters alone.

3. FEES: Typically 1.5%-3% per transaction depending on agreement.

4. LEGACY vs MODERN: The legacy CGI API still works but the V2 JSON API is recommended for new integrations.

---

## File Changes Summary

- app/models/config_settings.py - Add tranzila fields
- app/models/donation.py - Add tranzila fields
- app/services/tranzila_service.py - NEW - API client
- app/blueprints/webhook/routes.py - Add tranzila verification endpoint
- app/blueprints/donate/routes.py - Add tranzila payment flow
- app/blueprints/admin/routes.py - Add tranzila settings
- app/templates/admin/settings.html - Add tranzila config UI
- app/templates/donate/donation_page.html - Add iframe option
- app/config.py - Add env vars
- .env - Add tranzila credentials
- migrations/ - New migration

## Testing Checklist
- [ ] Admin can enter Tranzila credentials in settings
- [ ] iframe loads with handshake token
- [ ] Payment completes in iframe
- [ ] Handshake verification succeeds server-to-server
- [ ] Donation record created with payment_provider=tranzila
- [ ] Token saved for recurring donations
- [ ] Token charge works for recurring
- [ ] Refund works
- [ ] Receipt generated
- [ ] Commission calculated
