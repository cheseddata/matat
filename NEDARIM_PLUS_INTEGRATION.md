# Nedarim Plus Payment Integration - Implementation Guide

## Overview
Add Nedarim Plus (נדרים פלוס) as a payment processor alongside the existing Stripe integration. Nedarim Plus is Israel's leading nonprofit payment platform. The donation page should let the admin choose which processor to use (or offer both to donors).

## Nedarim Plus API Reference

### Authentication
Every API call requires:
- **`MosadId`** — 7-digit institution ID (get from Nedarim Plus account)
- **`ApiValid`** / **`ApiPassword`** — Auth token (request from `office@nedar.im`)

### Full API Docs
https://matara.pro/nedarimplus/ApiDocumentation.html

---

## PHASE 1: Database & Config

### 1a. Add Nedarim Plus fields to `ConfigSettings` model (`app/models/config_settings.py`)
```python
# Nedarim Plus configuration
nedarim_mosad_id = db.Column(db.String(20), nullable=True)       # 7-digit institution ID
nedarim_api_password = db.Column(db.String(255), nullable=True)   # API auth token
nedarim_enabled = db.Column(db.Boolean, default=False)            # Enable/disable
payment_provider = db.Column(db.String(20), default='stripe')     # 'stripe', 'nedarim', or 'both'
```

### 1b. Add Nedarim Plus fields to `Donation` model (`app/models/donation.py`)
Add these columns alongside the existing Stripe fields:
```python
# Nedarim Plus fields
nedarim_transaction_id = db.Column(db.String(255), unique=True, nullable=True)  # Their Shovar/TransactionId
nedarim_confirmation = db.Column(db.String(255), nullable=True)                  # Confirmation code
nedarim_keva_id = db.Column(db.String(255), nullable=True)                       # Standing order ID (for recurring)
payment_provider = db.Column(db.String(20), default='stripe')                    # 'stripe' or 'nedarim'
```

### 1c. Migration
```bash
flask db migrate -m "add nedarim plus fields"
flask db upgrade
```

### 1d. Admin Settings UI
Add a "Nedarim Plus" section to the admin settings page (`app/templates/admin/settings.html`) with fields for:
- MosadId
- ApiPassword
- Enable/Disable toggle
- Payment provider selector (Stripe / Nedarim Plus / Both)

---

## PHASE 2: Nedarim Plus Service (`app/services/nedarim_service.py`)

Create a new service file. Here are the key endpoints:

### 2a. iframe Payment (RECOMMENDED - handles PCI compliance)

The iframe approach is the safest. Embed this URL in an iframe:
```
https://www.matara.pro/nedarimplus/iframe/
```

Communication is via `window.postMessage()`. The flow:
1. Load iframe on your donation page
2. Send transaction details to iframe via PostMessage
3. iframe handles card entry (PCI compliant)
4. Receive result via PostMessage callback
5. Optionally receive server-side webhook at your CallBack URL

**PostMessage parameters to send to iframe:**
```json
{
  "Mosad": "1234567",
  "ApiValid": "your-api-token",
  "PaymentType": "Ragil",
  "Amount": "100",
  "Currency": "1",
  "Tashlumim": "1",
  "ClientName": "John Doe",
  "Phone": "0501234567",
  "Mail": "john@example.com",
  "Zeout": "",
  "Street": "",
  "City": "",
  "Comments": "",
  "Groupe": "Donations",
  "Param1": "",
  "Param2": "",
  "CallBack": "https://matatmordechai.org/nedarim/webhook",
  "SuccessUrl": "https://matatmordechai.org/donate/success",
  "FailUrl": "https://matatmordechai.org/donate/fail"
}
```

PaymentType values:
- `"Ragil"` = one-time standard charge
- `"HK"` = standing order (recurring / הוראת קבע)
- `"CreateToken"` = tokenize card without charging

Currency values:
- `1` = ILS (Israeli Shekel)
- `2` = USD (US Dollar)

**For token creation (save card without charging):**
Add `Tokef=Hide` and `CVV=Hide` to hide those fields (card is stored, no expiry/CVV retained).

### 2b. Transaction History
```
GET https://matara.pro/nedarimplus/Reports/Manage3.aspx
```
Parameters:
- `Action=GetHistoryJson`
- `MosadId=1234567`
- `ApiPassword=your-token`
- `LastId=0` (for pagination, pass last received ID)
- Max 2000 results per call
- **Rate limit: 20 requests/hour**

Response fields: `Shovar`, `Zeout`, `ClientName`, `Amount`, `TransactionTime`, `Confirmation`, `LastNum`, `TransactionType`, `Tashloumim`, `KabalaId`, `KevaId`

### 2c. Cancel Transaction
```
Action=DeletedAllowedTransaction
TransactionId=<id>
```

### 2d. Refund Transaction
```
Action=RefundTransaction
TransactionId=<id>
RefundAmount=<amount>
```
Note: Full refunds only per Israeli tax authority guidelines. Generates credit receipt.

### 2e. Standing Orders (הוראות קבע)

**Get all:**
```
GET https://matara.pro/nedarimplus/Reports/Manage3.aspx
Action=GetKevaJson
MosadId=...&ApiPassword=...
```
Returns: `KevaId`, `ClientName`, `Amount`, `Currency`, `Tokef`, `NextDate`, `Enabled`

**Create new:**
```
POST https://matara.pro/nedarimplus/Reports/Masav3.aspx
Action=NewMasavKeva
```

**Charge one-time against existing order:**
```
POST Action=TashlumBodedNew
KevaId=<id>&Amount=<amount>&Currency=1&Tashloumim=1
```

**Suspend/Resume:**
```
Action=DisableKeva    (freeze)
Action=EnableKevaNew  (resume)
```

### 2f. Bit Payment (Israeli mobile payment)
```
POST https://matara.pro/nedarimplus/V6/Files/WebServices/DebitBit.aspx
Action=CreateTransaction
```
Parameters: Standard auth + `ClientName`, `Phone`, `Amount`, success/failure redirect URLs, callback.

---

## PHASE 3: Webhook Handler

### 3a. Create webhook route (`app/blueprints/webhook/routes.py`)

Add a new endpoint: `POST /nedarim/webhook`

**Verify origin IP:** `18.194.219.73` (Nedarim Plus server)

**Transaction webhook payload (JSON POST):**
```json
{
  "TransactionId": "123456",
  "ClientId": "...",
  "Zeout": "...",
  "ClientName": "...",
  "Phone": "...",
  "Mail": "...",
  "Amount": "10000",
  "Currency": "1",
  "TransactionTime": "...",
  "Confirmation": "...",
  "LastNum": "1234",
  "Tokef": "12/26",
  "TransactionType": "Ragil",
  "Groupe": "Donations",
  "Comments": "...",
  "Tashloumim": "1",
  "MosadNumber": "1234567",
  "Shovar": "...",
  "KevaId": "0",
  "Param1": "donor_id_here",
  "Param2": "salesperson_id_here"
}
```

**Standing order webhook payload:**
```json
{
  "KevaId": "...",
  "ClientName": "...",
  "Amount": "...",
  "Currency": "1",
  "NextDate": "...",
  "LastNum": "1234",
  "Tokef": "12/26",
  "Groupe": "...",
  "MosadNumber": "..."
}
```

**IMPORTANT:** Nedarim Plus only attempts delivery ONCE. If it fails, they send an email notification. No retries.

### 3b. Webhook handler logic
The handler should:
1. Verify request IP is `18.194.219.73`
2. Parse JSON body
3. Check for duplicate by `TransactionId` (idempotency)
4. Map `Param1` to `donor_id`, `Param2` to `salesperson_id` (custom params set in iframe)
5. Convert amount: Nedarim sends in agorot (cents) for ILS — verify this! Compare with iframe amount.
6. Currency mapping: `1` = ILS, `2` = USD
7. Create `Donation` record with `payment_provider='nedarim'`
8. Generate receipt (same receipt_service)
9. Calculate commission (same commission_service)
10. Send receipt email (same email_service)
11. Return HTTP 200

---

## PHASE 4: Donation Page UI

### 4a. Update donation page template (`app/templates/donate/donation_page.html`)

When `payment_provider` is `'both'`, show a toggle/tabs letting the donor choose:
- **Credit Card (International)** -> Stripe flow (existing)
- **Credit Card (Israel) / Bit** -> Nedarim Plus iframe

When `payment_provider` is `'nedarim'` only, show the Nedarim Plus iframe directly.

### 4b. Nedarim Plus iframe integration JS

```javascript
// Load iframe
const nedarimIframe = document.getElementById('nedarim-iframe');
nedarimIframe.src = 'https://www.matara.pro/nedarimplus/iframe/';

// Listen for messages from iframe
window.addEventListener('message', function(event) {
    if (event.origin !== 'https://www.matara.pro') return;

    const data = event.data;
    // Handle response: check for success/failure
    if (data.Status === 'OK' || data.Result === 'OK') {
        // Transaction succeeded
        window.location.href = '/donate/success?provider=nedarim&txn=' + data.TransactionId;
    } else {
        // Transaction failed
        showError(data.Message || 'Payment failed');
    }
});

// Send payment details to iframe
function submitNedarimPayment() {
    const paymentData = {
        Mosad: NEDARIM_MOSAD_ID,
        ApiValid: NEDARIM_API_VALID,
        PaymentType: 'Ragil',
        Amount: document.getElementById('amount').value,
        Currency: '2',  // USD (use '1' for ILS)
        Tashlumim: '1',
        ClientName: document.getElementById('donor-name').value,
        Phone: document.getElementById('donor-phone').value,
        Mail: document.getElementById('donor-email').value,
        Groupe: 'Donations',
        Param1: donorId,           // Pass donor_id for webhook mapping
        Param2: salespersonId,     // Pass salesperson_id for webhook mapping
        CallBack: 'https://matatmordechai.org/nedarim/webhook',
        SuccessUrl: '',
        FailUrl: ''
    };

    nedarimIframe.contentWindow.postMessage(paymentData, 'https://www.matara.pro');
}
```

### 4c. iframe height management
Query the iframe for its rendered height to avoid scrollbars:
```javascript
// Ask iframe for its height
setInterval(function() {
    nedarimIframe.contentWindow.postMessage({ action: 'getHeight' }, 'https://www.matara.pro');
}, 500);

window.addEventListener('message', function(event) {
    if (event.origin === 'https://www.matara.pro' && event.data.Height) {
        nedarimIframe.style.height = event.data.Height + 'px';
    }
});
```

---

## PHASE 5: Admin Dashboard Updates

### 5a. Donation list
- Add `payment_provider` column to donation list table
- Show "Stripe" or "Nedarim" badge
- Filter by provider

### 5b. Transaction sync (optional but recommended)
Add a button/cron to pull recent transactions from Nedarim Plus API (`GetHistoryJson`) and reconcile with local records. This is a safety net since Nedarim Plus does NOT retry failed webhooks.

### 5c. Refund support
Wire up the existing refund UI to call `RefundTransaction` for Nedarim donations (currently only calls Stripe).

---

## PHASE 6: Environment Variables

Add to `.env`:
```
# Nedarim Plus
NEDARIM_MOSAD_ID=
NEDARIM_API_PASSWORD=
NEDARIM_ENABLED=false
```

Add to `app/config.py`:
```python
NEDARIM_MOSAD_ID = os.environ.get('NEDARIM_MOSAD_ID')
NEDARIM_API_PASSWORD = os.environ.get('NEDARIM_API_PASSWORD')
NEDARIM_ENABLED = os.environ.get('NEDARIM_ENABLED', 'false').lower() == 'true'
```

---

## Important Notes

1. **PCI Compliance:** Use the iframe method. Do NOT send raw card numbers through your server unless you have PCI certification. Nedarim Plus will block your terminal.

2. **Non-Israeli IPs:** Direct API calls from non-Israeli IPs trigger CAPTCHA. The iframe handles this on the client side (the donor's browser). Server-side calls (webhook receipt, history sync) work fine since they use API auth, not card data.

3. **Currency:** The existing system stores amounts in cents (matching Stripe). Nedarim Plus uses agorot for ILS. Standardize: store all amounts in smallest unit (cents/agorot). Add currency-aware display helpers.

4. **Dates:** Nedarim Plus uses `dd/mm/yyyy` format. Convert properly.

5. **Receipt Integration:** The existing `receipt_service.py` and `create_receipt_atomic()` should work for Nedarim donations too. Just pass the Donation object. May need to handle ILS formatting on the PDF template.

6. **Amounts:** Verify whether Nedarim Plus sends amounts in agorot or shekels in the webhook. The iframe Amount param is in shekels (whole units), but webhook might differ. Test and confirm.

7. **Webhook Security:** Only accept webhooks from IP `18.194.219.73`. Nedarim Plus does NOT retry failed webhooks. Implement the `GetHistoryJson` sync as a safety net.

8. **Standing Orders:** These are Nedarim Plus version of recurring payments. Each monthly charge triggers a new webhook. Track via `KevaId` field.

9. **ApiValid in iframe:** Note that the ApiValid token is sent client-side via PostMessage. This is how Nedarim Plus designed it. The token only works for that specific MosadId and can only process payments to that account, so exposure risk is limited.

---

## File Changes Summary

| File | Action |
|------|--------|
| `app/models/config_settings.py` | Add nedarim fields |
| `app/models/donation.py` | Add nedarim fields |
| `app/services/nedarim_service.py` | **NEW** - API client |
| `app/blueprints/webhook/routes.py` | Add `/nedarim/webhook` endpoint |
| `app/blueprints/donate/routes.py` | Add nedarim payment flow |
| `app/blueprints/admin/routes.py` | Add nedarim settings |
| `app/templates/admin/settings.html` | Add nedarim config UI |
| `app/templates/donate/donation_page.html` | Add iframe + toggle |
| `app/config.py` | Add env vars |
| `.env` | Add nedarim credentials |
| `migrations/` | New migration for DB fields |
| `app/i18n/en.json` | Add nedarim-related strings |
| `app/i18n/he.json` | Add nedarim-related strings |

---

## Testing Checklist
- [ ] Admin can enter Nedarim Plus credentials in settings
- [ ] Donation page shows Nedarim Plus iframe when enabled
- [ ] iframe loads and accepts card details
- [ ] PostMessage sends correct params (Amount, Currency, Param1/2, CallBack)
- [ ] Webhook receives POST from Nedarim Plus
- [ ] Webhook creates Donation record with `payment_provider='nedarim'`
- [ ] Receipt is generated for Nedarim donations
- [ ] Commission is calculated for Nedarim donations
- [ ] Receipt email is sent
- [ ] Donation appears in admin dashboard with "Nedarim" badge
- [ ] Refund works for Nedarim donations
- [ ] Standing orders create recurring donations
- [ ] History sync pulls missed transactions
- [ ] ILS donations display correctly with shekel symbol and proper formatting
