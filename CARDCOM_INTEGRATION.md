# CardCom Payment Integration - Implementation Guide

## Overview
Add CardCom as a payment processor for the Matat Mordechai donation platform. CardCom is an Israeli payment gateway with a unique strength: integrated Israeli tax invoice and receipt generation, including Section 46 donation receipts for nonprofits.

## CardCom API Reference

### Authentication
Every API call requires these fields in the JSON body (not headers):
- TerminalNumber (integer, e.g. 1000) -- MUST be integer, not string
- ApiName (string) -- your API username
- ApiPassword (string) -- your API password

Obtain from CardCom management console: Settings > Company Setup > Manage API-keys

### Environments
- Production API v11: https://secure.cardcom.solutions/api/v11/
- API Documentation: https://secure.cardcom.solutions/api/v11/DOCS
- Test Terminal: 1000, Test User: test9611
- Test Card: 4580000000000000, any future expiry, CVV 123

---

## PHASE 1: Database and Config

### 1a. Add CardCom fields to ConfigSettings model (app/models/config_settings.py)

- cardcom_terminal_number = db.Column(db.Integer, nullable=True)
- cardcom_api_name = db.Column(db.String(255), nullable=True)
- cardcom_api_password = db.Column(db.String(255), nullable=True)
- cardcom_enabled = db.Column(db.Boolean, default=False)

### 1b. Add CardCom fields to Donation model (app/models/donation.py)

- cardcom_transaction_id = db.Column(db.String(255), unique=True, nullable=True)
- cardcom_token = db.Column(db.String(255), nullable=True)
- cardcom_low_profile_code = db.Column(db.String(255), nullable=True)
- cardcom_invoice_number = db.Column(db.String(100), nullable=True)

### 1c. Migration
Run: flask db migrate -m "add cardcom fields"
Then: flask db upgrade

---

## PHASE 2: API Endpoints

All endpoints accept POST with Content-Type: application/json.

### 2a. LowProfile (Hosted Payment Page / iframe)

Create session: POST /api/v11/LowProfile/Create

Request body example:
- TerminalNumber: 1000
- ApiName: "your-api-name"
- ApiPassword: "your-api-password"
- Amount: 100.00
- Currency: 1
- SuccessRedirectUrl: "https://matatmordechai.org/donate/success"
- FailedRedirectUrl: "https://matatmordechai.org/donate/fail"
- WebHookUrl: "https://matatmordechai.org/cardcom/webhook"
- ReturnValue: "unique-order-id-123"
- MaxNumOfPayments: 12
- Operation: 1
- Language: "en"
- ProductName: "Donation to Matat Mordechai"
- Document.DocTypeToCreate: 400
- Document.Name: "Donor Name"
- Document.Products: array of {Description, Price, Quantity}

Response:
- LowProfileCode: "aa-bb-cc-dd-ee"
- Url: "https://secure.cardcom.solutions/hosted/..."
- OperationResponse: 0 (0 = success)

Embed the Url in an iframe or redirect to it.

### 2b. Operation Codes
- 1 = Charge + create token (bill card and save token)
- 2 = Token only (save card without billing)
- 3 = Suspended deal / authorize (deprecated)

### 2c. Get Payment Result: POST /api/v11/LowProfile/GetLpResult

Parameters: TerminalNumber, ApiName, ApiPassword, LowProfileCode

Key response fields:
- DealResponse: 0 = billing successful
- TokenResponse: 0 = token created
- InvoiceRespondCode: 0 = invoice/receipt created
- Token: saved card token (UUID format)
- CardValidityMonth / CardValidityYear: token expiry
- InternalDealNumber: CardCom transaction ID
- ReturnValue: your original reference ID
- Last4CardDigits: for display

### 2d. Charge Token: POST /api/v11/Transactions/ChargeWithToken

Parameters: TerminalNumber, ApiName, ApiPassword, Token, CardValidityMonth, CardValidityYear, SumToBill, CoinID, NumOfPayments
Plus InvoiceHead (CustName, SendByEmail, Email, Language, CoinID) and InvoiceLines (Description, Price, Quantity)

### 2e. Refund: POST /api/v11/Transactions/RefundByTransactionId

Parameters: TerminalNumber, ApiName, ApiPassword, TransactionId, Amount, CancelOnly
Plus Document.DocTypeToCreate: 310 (auto-generates credit note)

### 2f. Transaction List: POST /api/v11/Transactions/GetList
### 2g. Transaction Detail: POST /api/v11/Transactions/GetById
### 2h. Account Info: POST /api/v11/Accounts/GetInfo

---

## PHASE 3: Document Types (Israeli Tax Compliance)

DocTypeToCreate codes:
- 300 = Tax Invoice (Hashbonit Mas)
- 305 = Tax Invoice + Receipt (Hashbonit Mas / Kabala)
- 310 = Credit Note (Hashbonit Zikui)
- 320 = Receipt (Kabala)
- 330 = Proforma / Price Quote
- 400 = Donation Receipt (Section 46 tax-deductible)

FOR MATAT MORDECHAI (nonprofit):
- Use 400 (Donation Receipt) for tax-deductible donation receipts
- Use 320 (Receipt) for standard receipts
- Use 310 (Credit Note) for refunds

This is CardCom killer feature for nonprofits: automatic Israeli tax-compliant receipt generation as part of the payment flow.

---

## PHASE 4: Currency Codes (CoinID)

- 1 = ILS (Israeli New Shekel)
- 2 = USD
- 3 = EUR
- 4 = GBP

---

## PHASE 5: Webhook Handler

CardCom sends a GET request to your WebHookUrl with query parameters:

GET https://matatmordechai.org/cardcom/webhook?terminalnumber=1000&lowprofilecode=aa-bb-cc&Operation=1&DealResponse=0&TokenResponse=0&InvoiceRespondCode=0&ReturnValue=your-order-id

### Webhook handler logic:
1. Receive the GET request
2. Extract lowprofilecode from query params
3. Call POST /api/v11/LowProfile/GetLpResult to verify and get full details
4. Check for duplicate by InternalDealNumber (idempotency)
5. Create Donation record with payment_provider=cardcom
6. Save token for recurring donations
7. CardCom auto-generates receipt via DocTypeToCreate -- optionally also use your own receipt system
8. Calculate commission
9. Send receipt email
10. Return HTTP 200

IMPORTANT: The webhook is a GET request (not POST). Always verify via GetLpResult.

---

## Important Notes

1. PCI COMPLIANCE: The LowProfile/iframe approach handles PCI. Card data never touches your server.

2. TERMINALNUMBER MUST BE INTEGER: In JSON requests, send as number (1000), not string ("1000").

3. WEBHOOK IS GET: Unlike most gateways, CardCom webhook is GET with query parameters.

4. DONATION RECEIPTS: DocTypeToCreate 400 auto-generates Section 46 donation receipts. Huge for Israeli nonprofits.

5. ALL URLS MUST BE HTTPS: Redirect and webhook URLs must be publicly accessible HTTPS.

6. ALWAYS CALL GetLpResult: Verify every transaction server-to-server.

7. DEVELOPER SUPPORT: dev@secure.cardcom.co.il

---

## File Changes Summary

- app/models/config_settings.py - Add cardcom fields
- app/models/donation.py - Add cardcom fields
- app/services/cardcom_service.py - NEW - API client
- app/blueprints/webhook/routes.py - Add /cardcom/webhook GET endpoint
- app/blueprints/donate/routes.py - Add cardcom payment flow
- app/blueprints/admin/routes.py - Add cardcom settings
- app/templates/admin/settings.html - Add cardcom config UI
- app/templates/donate/donation_page.html - Add iframe option
- app/config.py - Add env vars
- .env - Add cardcom credentials
- migrations/ - New migration

## Testing Checklist
- [ ] Admin can enter CardCom credentials in settings
- [ ] LowProfile/Create returns payment URL
- [ ] iframe loads CardCom hosted page
- [ ] Payment completes successfully
- [ ] Webhook GET received
- [ ] GetLpResult verification succeeds
- [ ] Donation record created with payment_provider=cardcom
- [ ] Donation receipt (DocType 400) auto-generated
- [ ] Token saved for recurring
- [ ] Token charge works (ChargeWithToken)
- [ ] Refund works with credit note (DocType 310)
- [ ] Commission calculated
- [ ] ILS and USD donations work
