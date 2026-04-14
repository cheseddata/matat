# Pelecard Payment Processor Integration

## Overview
Pelecard is one of Israel's largest credit card processors (35+ years).
Website: https://pelecard.com/
API Docs: https://pelecard.com/support/api/

## API Details
- **Base URL:** `https://gateway20.pelecard.biz/api`
- **Test URL:** `https://gateway20.pelecard.biz/api` (same URL, test terminal)
- **Protocol:** REST JSON
- **Auth:** Terminal number + username + password

## Integration Type
Server-to-server JSON API. Also supports iframe/redirect for PCI compliance.

## Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/PaymentGW/init` | POST | Create payment / charge card |
| `/PaymentGW/refund` | POST | Refund a transaction |
| `/PaymentGW/GetTerminalData` | POST | Test connection / get terminal info |
| `/PaymentGW/ValidateByUniqueKey` | POST | Verify transaction status |

## Request Format (Create Payment)
```json
{
  "TerminalNumber": "terminal_id",
  "User": "username",
  "Password": "password",
  "ShopNumber": "1000",
  "CreditCardNumber": "4580000000000000",
  "CreditCardDateMmYy": "1227",
  "CVV2": "123",
  "DebitTotal": "1800",
  "DebitCurrency": "1",
  "DebitType": "51",
  "NumberOfPayments": "",
  "FirstPaymentTotal": "",
  "OtherPaymentsTotal": "",
  "ParamX": "donor_tz"
}
```

## Currency Codes
- `1` = ILS (Shekel)
- `2` = USD (Dollar)
- `978` = EUR (Euro)
- `826` = GBP (Pound)

## Debit Types
- `51` = Regular charge (רגיל)
- `8` = Installments (תשלומים)
- `6` = Credit (זיכוי)
- `9` = Standing order setup (הוראת קבע)

## Response Fields
```json
{
  "StatusCode": "000",
  "ErrorMessage": "",
  "PelecardTransactionId": "12345678",
  "ConfirmationKey": "ABC123",
  "ApprovalNo": "0963058",
  "Token": "token_for_recurring",
  "CreditCardCompanyName": "Visa",
  "CreditCardNumber": "****0000"
}
```

## Status Codes
- `000` = Success / Approved
- `001` = Card blocked
- `002` = Stolen card
- `003` = Contact card company
- `004` = Declined
- `006` = CVV error
- `033` = Card expired

## Token / Recurring
- Response includes `Token` field when charge succeeds
- Use token in subsequent charges instead of full card number
- Token is permanent - no need to store card number
- For recurring: call `/PaymentGW/init` with `Token` field instead of card details

## Refund
POST to `/PaymentGW/refund` with:
```json
{
  "TerminalNumber": "...",
  "User": "...",
  "Password": "...",
  "TransactionId": "original_transaction_id",
  "RefundTotal": "amount_in_agorot"
}
```

## Configuration Needed
Add to settings/config page:
- Terminal Number
- Username
- Password
- Test/Production mode toggle

## File Location
Create as: `app/services/payment/pelecard_processor.py`
Must extend `BasePaymentProcessor` from `app/services/payment/base.py`
Register in `app/services/payment/router.py`

## Supported Features
- ✅ One-time charges
- ✅ Installments (up to 36)
- ✅ Tokenization (for recurring without storing card)
- ✅ Refunds
- ✅ ILS, USD, EUR, GBP
- ✅ Card validation
