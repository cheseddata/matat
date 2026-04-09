# iCount Payment + Invoicing Integration - Implementation Guide

## Overview
Add iCount as a payment processor AND invoicing system. iCount is Israeli accounting software with built-in credit card processing, invoice generation, and Israeli tax compliance. Unique value: combined payment + accounting in one API.

## Authentication
- Method: Bearer Token
- Header: Authorization: Bearer YOUR_API_TOKEN
- Content-Type: application/json
- Create API Token in iCount dashboard
- Rate Limit: 30 requests per minute

### Environments
- Legacy API: https://api.icount.co.il/
- API V3: https://api-v3.icount.co.il/
- V3 Docs: https://apiv3.icount.co.il/docs/iCount/

---

## PHASE 1: Database and Config

### ConfigSettings model
- icount_api_token = db.Column(db.String(255), nullable=True)
- icount_enabled = db.Column(db.Boolean, default=False)

### Donation model
- icount_transaction_id = db.Column(db.String(255), unique=True, nullable=True)
- icount_invoice_number = db.Column(db.String(100), nullable=True)
- icount_doc_url = db.Column(db.String(500), nullable=True)

---

## PHASE 2: Document Types (doctype values)

- invoice -- Tax Invoice (Heshbonit Mas)
- invrec -- Invoice-Receipt (Heshbonit Mas / Kabala)
- receipt -- Receipt (Kabala)
- refund -- Credit Note / Refund
- order -- Order
- offer -- Price Quote
- delivery -- Delivery Note
- deal -- Deal

For Matat Mordechai: Use "receipt" for donation receipts, "refund" for credit notes.

---

## PHASE 3: Key API Endpoints (V3)

All endpoints use POST with JSON body and Bearer token header.

### Create Document
POST /doc/create

Parameters:
- doctype: "receipt" (or "invoice", "invrec", etc.)
- client_name: "Donor Name"
- email: "donor@example.com"
- vat_id: "123456789" (Israeli ID)
- currency_code: "ILS" or "USD" or "EUR" or "GBP"
- lang: "he" or "en"
- items: array of {description, quantity, unitprice, vat}
- send_email: true (auto-email PDF to client)

### Client Operations
- POST /client/create
- PUT /client/update
- GET /client/get
- GET /client/search

### Credit Card Operations
- POST /cc/charge -- Direct charge
- POST /cc/token -- Tokenize card

### Payment Page (Hosted)
iCount provides a hosted payment page.
After payment, redirects to success_url or fail_url.
Recommended for PCI compliance.

### Standing Orders / Recurring
Recurring payments via API, payment page, or manual.

### Events
POST /event/create

---

## PHASE 4: Simulator / Test Environment

When simulator is active, only test cards work:
- 4580000000000000 -- Error (4): Declined
- 4580458000000000 -- Error (1): Blocked
- 4580000045800000 -- Error (2): Stolen
- 4580000000004580 -- Error (3): Contact company
- 4580458045804580 -- Error (5): Fraudulent

---

## PHASE 5: Section 46 Donation Receipts (Israeli Tax)

Starting January 1, 2026, all Section 46 approved institutions must report donations through the Israel Tax Authority digital system.
- System issues a report number for each donation receipt
- iCount as approved accounting software should support this
- Confirm with iCount support

---

## PHASE 6: Currency Support
ILS, USD, EUR, GBP and others.

---

## Important Notes

1. DUAL PURPOSE: iCount handles BOTH payment processing AND invoice/receipt generation. You may use it as your invoicing backend even if using another processor for payments.

2. RATE LIMIT: 30 requests/minute. Queue bulk operations.

3. BEARER TOKEN: Old cid/user/pass method is deprecated. Use API token only.

4. SECTION 46: Verify iCount supports the new 2026 digital donation reporting requirement.

5. PYTHON EXAMPLE:
   import requests
   headers = {
       "Authorization": "Bearer YOUR_TOKEN",
       "Content-Type": "application/json"
   }
   response = requests.post(
       "https://api-v3.icount.co.il/doc/create",
       headers=headers,
       json={
           "doctype": "receipt",
           "client_name": "Donor Name",
           "email": "donor@example.com",
           "currency_code": "ILS",
           "lang": "he",
           "items": [{"description": "Donation", "quantity": 1, "unitprice": 100.00}],
           "send_email": True
       }
   )

## Community Resources
- PHP: https://github.com/Binternet/icount_api
- Python: https://gist.github.com/urigoren/682c82e706063497f351ce2059a2426d
- n8n: https://www.npmjs.com/package/n8n-nodes-icount

## File Changes Summary
- app/models/config_settings.py - Add icount fields
- app/models/donation.py - Add icount fields
- app/services/icount_service.py - NEW
- app/blueprints/webhook/routes.py - Add icount callback
- app/blueprints/donate/routes.py - Add icount payment flow
- app/blueprints/admin/routes.py - Add icount settings
- migrations/ - New migration

## Testing Checklist
- [ ] API token works, authenticated calls succeed
- [ ] Payment page loads
- [ ] Charge completes
- [ ] Receipt (doctype=receipt) auto-generated and emailed
- [ ] Token saved for recurring
- [ ] Refund generates credit note
- [ ] ILS and USD work
