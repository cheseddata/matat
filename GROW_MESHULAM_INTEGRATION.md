# Grow (Meshulam) Payment Integration - Implementation Guide

## Overview
Add Grow (formerly Meshulam) as a payment processor. Grow is Israel most popular payment gateway supporting credit cards, Bit, Apple Pay, and Google Pay through a unified Light API.

## Authentication
Three credentials sent as form fields (NOT headers, NOT JSON):
- pageCode -- Identifies your API settings
- userId -- Identifies your business
- apiKey -- Required for multi-business accounts (conditional)

### Environments
- Sandbox: https://sandbox.meshulam.co.il
- Production: https://api.meshulam.co.il
- Docs: https://grow-il.readme.io/

### CRITICAL: All requests use multipart/form-data, NOT JSON. All must originate server-side.

---

## PHASE 1: Database and Config

### ConfigSettings model
- grow_page_code = db.Column(db.String(255), nullable=True)
- grow_user_id = db.Column(db.String(255), nullable=True)
- grow_api_key = db.Column(db.String(255), nullable=True)
- grow_enabled = db.Column(db.Boolean, default=False)

### Donation model
- grow_transaction_id = db.Column(db.String(255), unique=True, nullable=True)
- grow_transaction_code = db.Column(db.String(255), nullable=True)
- grow_token = db.Column(db.String(255), nullable=True)
- grow_recurring_debit_id = db.Column(db.String(255), nullable=True)

---

## PHASE 2: API Endpoints (Light API v1.0)

All endpoints: POST {base_url}/api/light/server/1.0/{method}

### createPaymentProcess (Hosted Payment Page)
POST /api/light/server/1.0/createPaymentProcess

Parameters (multipart/form-data):
- pageCode, userId (required)
- sum: payment amount (required)
- description: payment description
- successUrl, cancelUrl, notifyUrl (required, no localhost)
- paymentNum: number of installments
- paymentType: "1" for Grow-managed recurring
- pageField[fullName], pageField[phone], pageField[email]
- cField1 through cField10: custom fields
- saveToken: "1" to save card token

Response: JSON with url field. URL valid for 10 MINUTES ONLY.

### approveTransaction (MANDATORY after payment webhook)
POST /api/light/server/1.0/approveTransaction
Parameters: pageCode, transactionId
Do NOT call for token-only or delayed transactions.

### createTransactionWithToken (Token Charge / Recurring)
POST /api/light/server/1.0/createTransactionWithToken
Parameters: pageCode, userId, sum, token, paymentNum
- isRecurringDebitPayment: "1" to create new recurring
- recurringDebitId: for subsequent recurring charges
Do NOT call approveTransaction after this.

### refundTransaction
POST /api/light/server/1.0/refundTransaction

### cancelBitTransaction (Bit Refund)
POST /api/light/server/1.0/cancelBitTransaction

### getTransactionInfo
POST /api/light/server/1.0/getTransactionInfo

### createPaymentLink
POST /api/light/server/1.0/createPaymentLink

### updateRecurringPayment
Change amount, pause, or cancel recurring.

---

## PHASE 3: Payment Flow

1. Server calls createPaymentProcess with amount, URLs, customer info
2. Response returns payment page URL (expires in 10 min)
3. Redirect customer or embed in iframe
4. Customer pays (credit card, Bit, Apple Pay, Google Pay)
5. Grow redirects to successUrl or cancelUrl
6. Grow POSTs webhook to notifyUrl
7. Your server calls approveTransaction to close the loop

---

## PHASE 4: Webhook Handler

Grow POSTs to notifyUrl with:
- webhookKey, transactionCode, transactionType
- paymentSum, paymentsNum, firstPaymentSum, periodicalPaymentSum
- paymentDate, asmachta (auth number)
- fullName, payerPhone, payerEmail
- cardSuffix, cardBrand, paymentSource
- purchaseCustomField (cField1, cField2, etc.)

Handler logic:
1. Receive POST, extract transactionId
2. Call approveTransaction (mandatory!)
3. Map custom fields to donor_id, salesperson_id
4. Idempotency check
5. Create Donation with payment_provider=grow
6. Generate receipt, calculate commission
7. Return HTTP 200

---

## PHASE 5: Tokenization and Recurring

Save Token: createPaymentProcess with saveToken=1

Grow-Managed Recurring: paymentType=1, paymentNum=N

Merchant-Managed Recurring:
1. Save token, then createTransactionWithToken with isRecurringDebitPayment=1
2. Save recurringDebitId for subsequent charges
3. updateRecurringPayment to modify/pause/cancel

---

## PHASE 6: Supported Payment Methods
- Credit Cards: Visa, Mastercard, Isracard, Diners, AMEX
- Bit, Apple Pay, Google Pay
- Installments via paymentNum

---

## Important Notes
1. FORM DATA NOT JSON: requests.post(url, data={...})
2. SERVER-SIDE ONLY: Client-side calls blocked
3. APPROVE TRANSACTION: Mandatory after every standard webhook
4. URL EXPIRY: 10 minutes
5. NO LOCALHOST: Use ngrok for dev

## File Changes Summary
- app/models/config_settings.py - Add grow fields
- app/models/donation.py - Add grow fields
- app/services/grow_service.py - NEW
- app/blueprints/webhook/routes.py - Add /grow/webhook POST
- app/blueprints/donate/routes.py - Add grow flow
- app/blueprints/admin/routes.py - Add grow settings
- migrations/ - New migration

## Testing Checklist
- [ ] createPaymentProcess returns URL
- [ ] Hosted page loads, credit card payment works
- [ ] Bit payment works
- [ ] Webhook received, approveTransaction called
- [ ] Donation created with payment_provider=grow
- [ ] Token saved, token charge works
- [ ] Recurring works
- [ ] Refund works
