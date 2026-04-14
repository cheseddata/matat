# Yaad (iCard) Payment Processor Integration

## Overview
Yaad (formerly iCard / EasyCard's API brand) is an Israeli payment gateway.
Popular with nonprofits for simple integration and competitive rates.
Website: https://yaad.net/ (also https://www.e-c.co.il/)

## API Details
- **Base URL:** `https://icom.yaad.net/p/`
- **Test URL:** `https://icom.yaad.net/p/` (test credentials)
- **Protocol:** REST (form-encoded POST or query string)
- **Auth:** Masof (terminal) + PassP (password) + KEY

## Integration Type
REST API with URL parameters. Simple HTTP POST/GET.

## Endpoints
| Endpoint | Purpose |
|----------|---------|
| `/p/?action=pay` | Create payment |
| `/p/?action=APISign` | Tokenize card |
| `/p/?action=soft` | Charge with token (recurring) |
| `/p/?action=refund` | Refund |
| `/p/?action=getTransData` | Get transaction info |

## Request Format (Create Payment)
```
POST https://icom.yaad.net/p/
Content-Type: application/x-www-form-urlencoded

action=pay
&Masof=TERMINAL_ID
&PassP=PASSWORD
&KEY=API_KEY
&CC=4580000000000000
&Tmonth=12
&Tyear=27
&CVV=123
&Amount=18.00
&Currency=1
&Tash=1
&UserId=336321807
&ClientName=מנחם קנטור
&ClientLName=קנטור
&phone=0584754666
&email=test@example.com
&Order=donation_123
&Info=תרומה
&J5=True
&MoreData=True
&Coin=1
&Sign=True
```

## Currency Codes
- `1` = ILS
- `2` = USD
- `3` = EUR
- `4` = GBP

## Installments
- `Tash=1` = Regular (no installments)
- `Tash=3` = 3 installments
- `Tash=12` = 12 installments
- Up to 36

## Response Format
Returns URL-encoded or JSON response:
```json
{
  "CCode": "0",
  "Id": "12345678",
  "ACode": "0963058",
  "Fild1": "",
  "Fild2": "",
  "Fild3": "",
  "Token": "token_string_for_recurring",
  "Tokef": "1227",
  "CC": "0000",
  "Brand": "2",
  "L4digit": "0000",
  "Coin": "1",
  "Amount": "1800",
  "Hesh": "1",
  "errMsg": ""
}
```

## Response Codes (CCode)
- `0` = Success / Approved
- `1` = Card declined
- `2` = Card stolen
- `3` = Call card company
- `4` = General error
- `6` = CVV error
- `10` = Partial amount approved
- `33` = Card expired
- `99` = System error

## Token / Recurring (action=soft)
After first successful charge, use the `Token` from response:
```
POST https://icom.yaad.net/p/
action=soft
&Masof=TERMINAL_ID
&PassP=PASSWORD
&KEY=API_KEY
&Token=TOKEN_FROM_FIRST_CHARGE
&Amount=18.00
&Currency=1
&Tash=1
&UserId=336321807
&Info=recurring_donation
```

## Card Tokenization (action=APISign)
To save card without charging:
```
action=APISign
&Masof=TERMINAL_ID
&PassP=PASSWORD
&CC=4580000000000000
&Tmonth=12
&Tyear=27
&CVV=123
&Amount=0
&Sign=True
```
Returns token that can be used for future charges.

## Refund (action=refund)
```
action=refund
&Masof=TERMINAL_ID
&PassP=PASSWORD
&KEY=API_KEY
&TransId=ORIGINAL_TRANSACTION_ID
&Amount=18.00
&CreditId=ORIGINAL_APPROVAL
```

## Configuration Needed
- Masof (Terminal ID / מספר מסוף)
- PassP (Password)
- KEY (API Key)
- Test/Production mode toggle

## File Location
Create as: `app/services/payment/yaad_processor.py`
Must extend `BasePaymentProcessor` from `app/services/payment/base.py`
Register in `app/services/payment/router.py`

## Supported Features
- ✅ One-time charges
- ✅ Installments (up to 36)
- ✅ Tokenization (for recurring without storing card)
- ✅ Card-only tokenization (save card without charging)
- ✅ Refunds
- ✅ ILS, USD, EUR, GBP
- ✅ Donor details in transaction (name, TZ, phone, email)
- ✅ Simple REST API (easiest to integrate)
