# YeshInvoice Integration - Implementation Guide

## Overview
YeshInvoice (yeshinvoice.co.il) is an Israeli digital invoicing platform for generating
tax-compliant receipts, invoices, and donation receipts. Fixed-price unlimited documents.
40-day free trial. Integrates with Israeli payment gateways.

## API Reference

### Base URL
https://api.yeshinvoice.co.il/api/v1/

### Authentication
Every request requires UserKey + SecretKey in the JSON body:
- UserKey: from Account > API Keys in dashboard
- SecretKey: from Account > API Keys in dashboard
- Account ID: from Account > Overview (top-right)

Method: POST
Content-Type: application/json

### Full API Docs (requires login)
https://user.yeshinvoice.co.il/api/doc

---

## PHASE 1: Database and Config

### ConfigSettings model
- yeshinvoice_user_key = db.Column(db.String(255), nullable=True)
- yeshinvoice_secret_key = db.Column(db.String(255), nullable=True)
- yeshinvoice_account_id = db.Column(db.String(100), nullable=True)
- yeshinvoice_enabled = db.Column(db.Boolean, default=False)
- yeshinvoice_default_doc_type = db.Column(db.String(50), default='receipt')

### Donation model additions
- yeshinvoice_doc_id = db.Column(db.String(255), nullable=True)
- yeshinvoice_doc_number = db.Column(db.String(100), nullable=True)
- yeshinvoice_pdf_url = db.Column(db.String(500), nullable=True)

---

## PHASE 2: Document Types Supported

1. Tax Invoice (hashbonit mas)
2. Receipt (kabala)
3. Tax Invoice + Receipt (hashbonit mas kabala)
4. Credit Note (hashbonit zikuy)
5. Digital Invoice (hashbonit digitalit)
6. House Committee Receipts

For Matat Mordechai (nonprofit): Use Receipt (kabala) or check if
Section 46 donation receipt type is available in the authenticated docs.

---

## PHASE 3: API Operations

### Create Invoice / Receipt
POST https://api.yeshinvoice.co.il/api/v1/createInvoice (exact endpoint in auth docs)

Required fields:
- UserKey, SecretKey (auth)
- DocumentType (document type code)
- CurrencyID (ILS, USD, etc.)
- LangID (language)
- DateCreated (document date)
- MaxDate (due date)
- statusID (document status)
- Customer Name
- Quantity (line item)
- DueDate (payment due date)

Optional fields:
- Title, Notes, NotesBottom
- vatPercentage, ExchangeRate
- roundPrice, RoundPriceAuto
- OrderNumber (external reference)
- isDraft
- sendSign (request digital signature)
- DontCreateIsraelTaxNumber
- fromDocID (for credit notes referencing original)

Customer fields:
- Customer Name (required)
- NameInvoice, FullName
- NumberID (Israeli Teudat Zehut / company number)
- EmailAddress, Address, City, Phone, Phone2
- CustomKey (external reference -- use donor_id)
- ZipCode, CountryCode

Line items:
- Quantity (required)
- Price (unit price)
- Item Name (description, e.g. "Donation to Matat Mordechai")
- Sku, vatType, SkuID

Email/SMS delivery (built-in):
- SendEmail: true (auto-emails receipt to donor)
- SendSMS: true (sends via SMS)
- IncludePDF: true (attaches PDF to email)

### Customer Management
- Add Customer (Name, Email, Address, City, Zipcode, Phone)
- Update Customer (by Customer ID)
- Delete Customer (by Customer ID)

### Search / Query
- Find Customers (search/filter)
- Find Invoices (by Customer ID)
- Find Open Invoices
- Find Closed Invoices
- Find Products
- Find VAT Types
- Find Language Types

### Credit Note (Refund Receipt)
Create with DocumentType = credit note code
Set fromDocID = original document ID

---

## PHASE 4: Integration with Payment Processors

YeshInvoice can replace or complement the built-in receipt system.

Flow:
1. Donation processed via payment processor (CardCom, Grow, Stripe, etc.)
2. On success, call YeshInvoice API to create receipt
3. YeshInvoice generates Israeli tax-compliant document
4. YeshInvoice auto-emails PDF receipt to donor
5. Store yeshinvoice_doc_id and yeshinvoice_doc_number on donation record

This is especially useful because:
- Israeli tax compliance built-in (automatic tax allocation numbers)
- Professional Hebrew/English receipts
- PDF generation handled by YeshInvoice
- Email delivery handled by YeshInvoice
- Replaces need for WeasyPrint receipt generation for Israeli donors

---

## PHASE 5: Payment Gateway Integrations (Built-in)

YeshInvoice natively integrates with these Israeli gateways:
- Tranzila
- CardCom
- PeleCard
- Meshulam (Grow)
- PayPal
- YaadPay
- Max Business

This means YeshInvoice can ALSO process payments directly (not just receipts).

---

## PHASE 6: Webhook / Callback

Confirmed callback support:
- Callback receives: UniqueID, transaction_id, PelecardStatusCode, payment metadata
- Your server receives POST with payment confirmation
- Use this to trigger receipt generation + donation record creation

---

## Important Notes

1. FULL DOCS BEHIND LOGIN: Complete API at https://user.yeshinvoice.co.il/api/doc
   Sign up for 40-day free trial to access.

2. FIXED PRICING: Unlimited documents at fixed price. No per-document fees.

3. ISRAELI TAX COMPLIANCE: Automatic tax allocation numbers, VAT handling,
   digital signature support.

4. DUAL USE: Can serve as BOTH receipt generator AND payment processor.

5. MAKE.COM + ZAPIER: Official integrations exist for no-code automation.

---

## Contact

- Support: support@yeshinvoice.co.il
- Developer: ori@yeshinvoice.co.il
- WhatsApp: +972-058-493-7247
- Address: HaHaroshet 25, Raanana, Israel

---

## File Changes Summary

- app/models/config_settings.py - Add yeshinvoice fields
- app/models/donation.py - Add yeshinvoice fields
- app/services/yeshinvoice_service.py - NEW - API client
- app/blueprints/webhook/routes.py - Add yeshinvoice callback
- app/blueprints/admin/routes.py - Add yeshinvoice settings
- app/templates/admin/settings.html - Add yeshinvoice config
- migrations/ - New migration

## Testing Checklist
- [ ] YeshInvoice credentials configured in admin
- [ ] Receipt created via API after donation
- [ ] PDF generated and emailed to donor
- [ ] Document number stored on donation record
- [ ] Credit note works for refunds
- [ ] Customer created/linked in YeshInvoice
- [ ] Hebrew and English receipts work
- [ ] ILS and USD currencies work
