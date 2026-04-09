# The Donors Fund API Integration - Implementation Guide

## Overview
The Donors Fund (thedonorsfund.org) is a major Jewish donor-advised fund based in Lakewood, NJ.
They have a FULL PUBLIC REST API (v1.2.0 / OpenAPI 3.0) for creating grants, cancelling grants,
validating giving cards, and looking up charity accounts.

## API Reference (v1.2.0)

### Base URLs
- Sandbox: https://api.tdfcharitable.org/thedonorsfund/integration
- Production: https://api.thedonorsfund.org/thedonorsfund/integration

### Authentication (TWO headers required on every request)

Header: Api-Key
- Type: apiKey (in header)
- Security: Public (same key for all integrators)
- Sandbox key: 3Q1i2KzHmUCiPDr8gCtiRQB6ZtIJBVjEKwSUGwFdtfvw
- Production key: CXtaaW9xqUafyffApPbfVQD0MmLhdprESvor9vi2GNLQ

Header: Validation-Token
- Type: apiKey (in header)
- Security: Private (unique per integrator, secret)
- Obtain from The Donors Fund after registration

### Content-Type: application/json for all requests

---

## PHASE 1: Database and Config

### ConfigSettings model
- donorsfund_validation_token = db.Column(db.String(255), nullable=True)
- donorsfund_account_number = db.Column(db.String(100), nullable=True)
- donorsfund_tax_id = db.Column(db.String(50), nullable=True)
- donorsfund_enabled = db.Column(db.Boolean, default=False)

### Donation model
- donorsfund_transaction_id = db.Column(db.String(255), unique=True, nullable=True)
- donorsfund_confirmation = db.Column(db.String(255), nullable=True)
- is_daf_donation = db.Column(db.Boolean, default=False)
- daf_provider = db.Column(db.String(100), nullable=True)

---

## PHASE 2: API Endpoints

### ENDPOINT 1: POST /create -- Create a Grant

Donors give directly from their Donors Fund account using username+4-digit-pin OR 16-digit-card+CVV.

#### Request Body (JSON):

Charity Authorization (your nonprofit):
- accountNumber (number): Your charity account number. Test value: 1974419
- taxId (string): Your charity tax ID. Test value: 47-4844275
- NOTE: Need either accountNumber OR taxId. If taxId has multiple accounts, provide both.

Donor Authentication (the donor giving):
- userName (string): Donor username. Test: testuser
- pin (number, 4 digits): Donor PIN. Test: 1234
OR
- cardNumber (string, 16 digits): Donor giving card number. Test: 6100123456789010
- cvv (string, 3 digits): Card CVV. Test: 123

Grant Details:
- amount (number, decimal, REQUIRED): Donation amount e.g. 180.00
- isRecurringGrant (boolean): true for recurring, false for one-time
- recurringType (string, enum): weekly | biweekly | monthly | bimonthly | quarterly | semiannually | annually
- startDate (string): Start date for recurring grants
- purpose (string): Grant purpose e.g. in memory of a loved one
- purposeNote (string): Purpose details e.g. In honor of John Doe
- merchantPhoneNumber (number): Your phone number
- merchantID (string): External merchant ID when charity has multiple Donors Fund accounts

#### Response (200):
- confirmationNumber: Transaction ID (save this!)
- error: null if success, error message if failed
- errorCode: 0 = success, non-zero = error
- statusCode: Always 200 (check errorCode instead!)

---

### ENDPOINT 2: PUT /cancel -- Cancel/Delete a Grant

#### Request Body (JSON):
- transactionId (string, required): The confirmationNumber from /create response

---

### ENDPOINT 3: GET /charity/account-numbers/{TaxId} -- Lookup Charity Accounts

Returns all account numbers and DBAs for a given tax ID.
Useful when one charity has multiple Donors Fund accounts.

#### Path Parameter:
- TaxId (string, required): The charity tax ID number

---

### ENDPOINT 4: POST /validate -- Validate Giving Card

Checks whether a Donors Fund giving card is valid before attempting a grant.

#### Request Body (JSON):
- cardNumber (string, required): 16-digit giving card number
- cvv (string, required): 3-digit CVV

---

### ENDPOINT 5: GET /grant/details/{ConfirmationNumber} -- Grant Status

Returns basic details and status of a specific grant.

#### Path Parameter:
- ConfirmationNumber (string, required): The confirmationNumber from /create

---

## PHASE 3: Integration Flow

1. Donor selects Pay with Donors Fund on donation page
2. Donor enters EITHER: username + 4-digit PIN, OR 16-digit card + 3-digit CVV
3. Your server calls POST /create with donor creds + amount + your charity account
4. Check response: errorCode 0 = success, save confirmationNumber
5. Create Donation record with payment_provider=donors_fund, is_daf_donation=True
6. Generate receipt, calculate commission

For Recurring: set isRecurringGrant=true, recurringType=monthly (Donors Fund handles schedule)
To Cancel: PUT /cancel with transactionId
To Check Status: GET /grant/details/{confirmationNumber}

---

## PHASE 4: Test Data
- Charity accountNumber: 1974419
- Charity taxId: 47-4844275
- Donor userName: testuser
- Donor pin: 1234
- Giving card: 6100123456789010
- CVV: 123
- Sandbox API key: 3Q1i2KzHmUCiPDr8gCtiRQB6ZtIJBVjEKwSUGwFdtfvw

---

## Important Notes

1. TWO HEADERS REQUIRED: Both Api-Key and Validation-Token in every request.
2. STATUSCODE ALWAYS 200: Check errorCode and error fields for actual status.
3. TWO AUTH METHODS: Username+PIN or CardNumber+CVV. Support both on form.
4. RECURRING BUILT-IN: Donors Fund handles recurring schedule.
5. VALIDATE FIRST: Use POST /validate before /create to pre-check card.
6. FEES: 2.9% on all grants.
7. CONTACT: support@thedonorsfund.org / +1-844-666-0808
8. SWAGGER DOCS: https://thedonorsfund.org/api-documentation

---

## File Changes Summary
- app/models/config_settings.py - Add donorsfund fields
- app/models/donation.py - Add donorsfund fields
- app/services/donorsfund_service.py - NEW
- app/blueprints/donate/routes.py - Add Donors Fund payment flow
- app/blueprints/admin/routes.py - Add Donors Fund settings
- app/templates/donate/donation_page.html - Add Donors Fund form
- migrations/ - New migration

## Testing Checklist
- [ ] POST /validate works with test card in sandbox
- [ ] POST /create works with username+pin
- [ ] POST /create works with card+cvv
- [ ] Recurring grant creation works
- [ ] PUT /cancel works
- [ ] GET /grant/details works
- [ ] GET /charity/account-numbers works
- [ ] Donation record created with payment_provider=donors_fund
- [ ] Receipt generated, commission calculated
- [ ] Error handling (errorCode != 0)
