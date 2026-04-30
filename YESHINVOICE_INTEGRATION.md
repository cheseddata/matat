# YeshInvoice Integration — Operator Reference

**Goal of this document:** every Claude (and human) working on Matat's
YeshInvoice integration should read this **first**, before touching any
code that calls the YeshInvoice API. The previous integration was built
against the wrong endpoint with the wrong auth scheme and wrong document
type — every receipt came out as a `תעודת משלוח` (shipment) instead of
`קבלה לפי סעיף 46` (Section 46 donation receipt). All the code in
`app/services/yeshinvoice_service.py` was broken. This file is the
ground truth.

Source: <https://user.yeshinvoice.co.il/api/doc?an=createdoc> — the
public, current API documentation. Always verify against that page if
something here looks stale.

---

## 1. Endpoints we actually use

| What we want to do | Method | URL |
|---|---|---|
| Issue a Section-46 donation receipt | `POST` | `https://api.yeshinvoice.co.il/api/v1.1/createDocument` |
| Cancel / reverse a receipt (e.g. a test) | `POST` | `https://api.yeshinvoice.co.il/api/v1.1/cancelDocument` |

There is also `https://api.yeshinvoice.co.il/api/user/createInvoice` —
that's an old v1 endpoint. **Do not use it.** It's still up but it
predates `DocumentType` selection and produces unreliable results.

The previous code in `yeshinvoice_service.py` pointed at
`https://api.yeshinvoice.co.il/api/v1/createDocument`, which returns
404. It also had `getAccountInfo`, `createOrUpdateCustomer`, and
`getDocument` — none of those exist in the public API. Stub them or
delete them.

---

## 2. Authentication — read this carefully, the format is unusual

YeshInvoice does NOT take credentials in the JSON body or in the
`Authorization: Bearer <token>` slot. It uses a **JSON value inside
the Authorization header**:

```
POST /api/v1.1/createDocument HTTP/1.1
Host: api.yeshinvoice.co.il
Content-Type: application/json
Authorization: {"secret":"3c341b0f-310f-4770-b5c1-12655554b3","userkey":"QssW7776655KqJ"}
```

That's a literal JSON object, not Base64, not URL-encoded. The keys
inside it are **lowercase**: `secret` and `userkey`. The values come
from the operator's YeshInvoice account → Settings → API.

### Common mistakes

- Using `UserKey`/`SecretKey` (capital first letters) → the API
  returns `מפתח SECRET KEY לא חוקי` ("Secret Key is invalid"). The
  field names are case-sensitive and **must be lowercase**.
- Putting the keys in the JSON body instead of the header → same
  "invalid Secret Key" error.
- Sending `Authorization: Bearer <secret>` → same error.
- Hitting `/api/v1/...` instead of `/api/v1.1/...` → 404 with the
  message `No HTTP resource was found...`

### Storage in our system

The keys live in `ConfigSettings.yeshinvoice_user_key` and
`ConfigSettings.yeshinvoice_secret_key` (encrypted at rest via Fernet
in `app/utils/crypto.py`). When you read them, decrypt first; when
you build the header, JSON-dump them with **lowercase** keys.

---

## 3. createDocument — full request reference

### Required headers

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `Authorization` | `{"secret":"…","userkey":"…"}` (literal JSON; see §2) |

### Body — all attributes

Required fields are marked *. Defaults shown are what YeshInvoice
uses if you omit the field; for required fields you must supply a value
even if it matches the default.

| Field | Type | Notes / Default |
|---|---|---|
| `Title` | string | Free-text title shown at top of receipt. |
| `Notes` | string | Mid-document notes. |
| `NotesBottom` | string | Bottom-of-document notes. |
| `HideNotes` | string | Internal-only note (operator sees, donor doesn't). |
| `CurrencyId` * | number | See §4 currency table. Default `2` (ILS). |
| `LangId` * | number | `359` = HEB, `139` = ENG. Default `359`. |
| `SendSMS` | bool | Have YeshInvoice SMS the donor a link to the receipt. Default `false`. |
| `SendEmail` | bool | Have YeshInvoice email the donor the receipt. Default `false`. We typically keep this `false` and email from our own system. |
| `IncludePDF` | bool | If `SendEmail=true`, attach the PDF inline. Default `false`. |
| `DocumentType` * | number | **The big one — see §5.** For Section 46 donation receipts use `11`. Default `1` is a shipment, **NOT** what you want. |
| `ExchangeRate` | number | Required when `CurrencyId ≠ 2` (non-ILS). Default `1`. |
| `vatPercentage` | number | Document-level VAT %. Default `17`. **For donation receipts the per-item `vatType: 2` (exempt) is what actually matters** — see §7. We can leave `vatPercentage` at the default; it doesn't affect the line items when each item already specifies `vatType: 2`. |
| `roundPrice` | number | Round amount. Default `0`. |
| `RoundPriceAuto` | bool | Auto-round to nearest 0.5. Default `false`. |
| `OrderNumber` | string | Free-text order ref (we use the Matat donation ID). |
| `DateCreated` * | string | `yyyy-MM-dd HH:mm` — when the donation actually occurred. |
| `MaxDate` * | string | `yyyy-MM-dd HH:mm` — usually same as `DateCreated` for a receipt. |
| `hideMaxDate` | bool | Hide the "valid until" line. Default `false`. We send `true` for receipts. |
| `refdocNumber` | number | Reference doc number from outside YeshInvoice. |
| `refurl` | string | Reference URL from outside YeshInvoice. |
| `statusID` * | number | `1` = issued, `2` = draft. Default `1`. |
| `isDraft` | bool | Same intent as `statusID=2`. Default `false`. |
| `sendSign` | bool | Returns a sign-URL the donor clicks to e-sign. Default `false`. |
| `DontCreateIsraelTaxNumber` | bool | If `true`, skip generating an Israeli tax-authority allocation number. Default `false`. **For Section 46 receipts leave this `false`** — the org needs the allocation number for tax filing. |
| `fromDocID` | number | If converting from a quote/proforma, the source doc ID. |
| `incomeID` | number | Income-category ID (configured per business in YeshInvoice — defines which fund the donation lands in). |
| `payCreditPluginID` | number | Credit-card processor plugin ID (only for paymentRequest docs). |
| `DocumentUniqueKey` | string | **Use this for idempotency.** If we send the same key twice, YeshInvoice rejects the duplicate. Max 20 chars. We use the Matat donation ID (e.g. `"matat-921"`). |
| `sourceType` | number | Not in the official attribute table on the docs page, but the verified body uses `sourceType: 1`. Live tests on 2026-04-29 included this field. Send `1`. |
| `files` | array of strings | URLs of files to attach to the receipt PDF. |
| `Customer` | object | See §6. |
| `items` | array of objects | See §7. For a single donation, one item with the donation amount. |
| `payments` | array of objects | See §8. |
| `discount` | object | `{amount: number, typeid: number}`. Skip for donations. |

### Minimum body for a Section 46 donation receipt

```json
{
  "DocumentType":      11,
  "CurrencyId":        2,
  "LangId":            359,
  "sourceType":        1,
  "statusID":          2,
  "DateCreated":       "2026-04-29 10:00",
  "MaxDate":           "2026-04-29 10:00",
  "hideMaxDate":       true,
  "DocumentUniqueKey": "matat-921",
  "Title":             "תרומה — Menachem Kantor",
  "Customer":          { "...": "see §6" },
  "items":             [ { "Quantity": 1, "Price": "10.00", "Name": "תרומה — Nedarim Plus", "vatType": 2 } ],
  "payments":          [ { "...": "see §8" } ]
}
```

This payload mirrors `yeshinvoice_body.json` in the repo, which is the
exact body that produced a valid Section-46 receipt in the
2026-04-29 live test.

---

## 4. CurrencyId

**The only verified value is `2` = ILS** (called out as the default in
the docs page). The other IDs were guessed during initial development
and have not been confirmed with YeshInvoice — verify before using.

Reference page: <https://user.yeshinvoice.co.il/api/doc?an=currencies>

| ID | Currency | Source |
|---|---|---|
| **`2`** | **ILS (₪)** | Verified — docs say "default `2`" for `CurrencyId` |
| `1`, `3`, `4`, … | USD, EUR, GBP, etc. | UNVERIFIED — confirm via the currencies reference page |

---

## 5. DocumentType

**Only one value below is fully verified. The rest are listed only
because we encountered them — verify with YeshInvoice support before
relying on any of them.**

### Verified values

| ID | Hebrew | What it produces | Source |
|---|---|---|---|
| **`11`** | **קבלה לתרומה / קבלה לפי סעיף 46** | **Section-46 donation receipt** — what Matat uses for every Israeli donor | YeshInvoice support email, 2026-04-29 (see commit `b0ddc0f`) |
| `1` | תעודת משלוח | Delivery note / shipment | Observed: when our old code sent `DocumentType=1`, donors got a "shipment" doc, not a receipt |

### Unverified — DO NOT USE without confirming

The createDocument docs page's body example uses `DocumentType: 9`,
but `9` is **not** Section-46. Other values in our `DOC_TYPES` map
(`3`, `4`, `5`, `6`) were our own guesses earlier in development —
none of them are confirmed. If you need a different document type
(e.g. a tax invoice or a plain receipt), email
support@yeshinvoice.co.il and ask for the numeric code rather than
guessing.

⚠ **Don't trust the docs page's example body.** Don't copy-paste
`DocumentType` from the example. Use `11` for Matat, full stop.

The above is the working subset based on the API doc example and
YeshInvoice's `cancelDocument` description ("works only with the
following document types: Receipt, Donation Receipt, Tax Invoice, and
Tax Invoice/Receipt"). If your operator's account uses other types
(e.g. a הזמנה / order workflow), check the dashboard for additional
codes.

---

## 6. `Customer` object

The donor. YeshInvoice keeps a customers table per business; if you
pass a name/email that doesn't exist, it creates a new customer row
automatically. To update an existing customer, pass their `ID`.

```jsonc
{
  "Name":         "ישראל כהן",                  // primary display name
  "NameInvoice":  "ישראל כהן",                  // name as it appears on the receipt
  "FullName":     "ישראל בן יוסף כהן",          // full legal name (for the tax allocation)
  "NumberID":     "012345678",                  // teudat zehut (9 digits)
  "EmailAddress": "donor@example.com",
  "Address":      "רחוב הרצל 5",
  "City":         "Jerusalem",
  "Phone":        "0501234567",
  "Phone2":       "",
  "ZipCode":      "9100000",
  "CountryCode":  "IL",                         // ISO-3166-1 alpha-2
  "CustomKey":    "matat-donor-751",            // our donor ID, for our own lookups
  "ID":           -1                            // -1 = create new; positive int = update existing
}
```

For Matat: `Customer.NumberID` should be `donor.teudat_zehut` if we
have it; otherwise leave empty (a Section-46 receipt is still legally
valid without a teudat zehut, but the donor can't claim the tax credit
without it).

---

## 7. `items` array

For a donation, send a single item:

```json
[
  {
    "Quantity": 1,
    "Price":    720,
    "Name":     "תרומה לעמותה — מתת מרדכי",
    "Sku":      "DONATION",
    "vatType":  2,
    "SkuID":    -1
  }
]
```

`vatType: 2` = **פטור (exempt)** — required for donation receipts
because the donation isn't a taxable purchase. *Verified working* by
the live `createDocument` test on 2026-04-29 (see
`yeshinvoice_void_policy.md` and `yeshinvoice_body.json`).

⚠ A previous draft of this file said `vatType: 4`. **That was wrong.**
`vatType: 4` = `לא חייב` (not subject to VAT — outside-scope) which
is a different legal category from "exempt". Donations should be
**exempt**, not out-of-scope.

Israeli vatType reference (working understanding — verify before
relying on values other than `2`):

| vatType | Hebrew | English | Use case |
|---|---|---|---|
| `1` | חייב במע"מ | Standard 17% VAT | Regular for-profit sales |
| **`2`** | **פטור** | **Exempt** | **Donations to a registered עמותה — what we use** |
| `3` | מע"מ אפס | Zero-rated | Exports |
| `4` | לא חייב | Not subject (out of scope) | Wrong category for donations |

---

## 8. `payments` array

How the donor paid. `TypeID` selects the payment type.

**Only `TypeID: 5` is observed in the docs example** — all other
values below were our development guesses and have **not** been
confirmed. Before using any other TypeID, verify with YeshInvoice
support or the
<https://user.yeshinvoice.co.il/api/doc?an=paymenttypes> reference
page (if it exists — open the doc page and click into Payments to
see the list).

| TypeID | Likely meaning | Source |
|---|---|---|
| `5` | Other / payment app (Bit, PayPal, …) | Used in the createDocument example body |
| `1`, `2`, `3`, `4`, … | Cash, Check, Bank transfer, Credit card | UNVERIFIED — confirm before relying on |

For a credit-card donation through Nedarim Plus:

```json
[
  {
    "TypeID":           4,
    "Price":            720,
    "CardLastDigits":   "1234",
    "CardType":         -1,
    "TransactionType":  -1,
    "NumberofPayments": 1,
    "Reference":        "nedarim-tx-id-from-webhook"
  }
]
```

For a check:

```json
[
  {
    "TypeID":       2,
    "Price":        720,
    "BankNumber":   "12",
    "BranchNumber": "456",
    "AccountNumber": "789012",
    "CheckNumber":  "0001234"
  }
]
```

---

## 9. Response format

Every endpoint returns the same envelope:

```json
{
  "Success":      true,
  "ErrorMessage": "",
  "ReturnValue":  {
    "url":         "https://yeshbe.co/xNcd2e",
    "pdfurl":      "https://api.yeshinvoice.co.il/download/...",
    "copypdfurl":  "https://api.yeshinvoice.co.il/download/...",
    "loyalpdfurl": "https://api.yeshinvoice.co.il/download/...",
    "pdf80mm":     "https://api.yeshinvoice.co.il/download/...",
    "paymenturl":  "https://api.yeshinvoice.co.il/pay/...",
    "docNumber":   23544,
    "id":          2435456
  }
}
```

PDF URL meanings:
- `pdfurl` — original (מקור)
- `copypdfurl` — duplicate copy (העתק)
- `loyalpdfurl` — certified copy (נאמן למקור)
- `pdf80mm` — narrow receipt-printer format
- `paymenturl` — self-pay link (only meaningful for proforma docs)

On failure:

```json
{
  "Success":      false,
  "ErrorMessage": "אנא הזן שם הלקוח/בית העסק",
  "ReturnValue":  null
}
```

**Persist `ReturnValue.id` and `ReturnValue.docNumber` on the
`Donation` row** — `Donation.yeshinvoice_doc_id` and
`Donation.yeshinvoice_doc_number` (already exist in the model). The
`id` is what `cancelDocument` needs.

---

## 10. cancelDocument — reversing a test or mistaken receipt

> **From YeshInvoice support (2026-04-29):**
> *Please note that issued documents cannot be deleted, as deleting
> official documents is not allowed. If you need to cancel a specific
> receipt or invoice, you can issue a negative receipt (or credit
> document) to offset and cancel the original document.*

Translation for our code: there is **no delete endpoint**. To make a
test or mistake go away, you call `cancelDocument`, which issues an
offsetting credit-document so the original and the cancellation net
to zero. Both records remain in the receipt sequence; that's by
design and required by Israeli tax law.

```
POST https://api.yeshinvoice.co.il/api/v1.1/cancelDocument
Content-Type: application/json
Authorization: {"secret":"…","userkey":"…"}

{ "id": 2435456 }
```

`id` is the `ReturnValue.id` from the original `createDocument`
response. Returns the same envelope shape with the credit-note's
`docNumber` and `id`.

**Only these document types can be cancelled:** Receipt, Donation
Receipt, Tax Invoice, Tax Invoice/Receipt. Quotes, orders, and
delivery notes are not cancellable through this endpoint — those just
expire.

For Matat: when we issue a test Section-46 receipt against a real
account, immediately call `cancelDocument` afterward so the test
doesn't pollute year-end reports. (Better: use the **Sandbox account**
— see §11.)

---

## 11. Sandbox vs Production

YeshInvoice has a sandbox environment that uses the **same base URL**
(`https://api.yeshinvoice.co.il/api/v1.1/`) but a **different account's
keys**. To get sandbox keys, click "Create Sandbox Account" at
<https://user.yeshinvoice.co.il/api/doc>. Sandbox doesn't require a
real teudat zehut or company ID and is the right place to do all
development testing. **Don't issue test receipts against the
production account** — those numbers go into the org's real receipt
sequence.

---

## 12. Idempotency — must use `DocumentUniqueKey`

If the Stripe / Nedarim webhook fires twice (it can — webhooks
re-deliver on retries) and we naively call `createDocument` both times,
we issue two receipts and break the receipt sequence. Always pass
`DocumentUniqueKey` set to a stable identifier — e.g. the Matat
donation ID like `"matat-921"`. YeshInvoice will reject the duplicate
with a recognisable error message and we can match the existing
document by querying via the Matat-side `Donation.yeshinvoice_doc_id`.

---

## 13. Common error messages

| Returned `ErrorMessage` | What's wrong | Fix |
|---|---|---|
| `מפתח SECRET KEY לא חוקי` | Auth-header not recognised | Use `Authorization: {"secret":"…","userkey":"…"}` (lowercase keys, JSON in header). |
| `אנא הזן שם הלקוח/בית העסק` | Missing customer name | Send `Customer.Name`. |
| `No HTTP resource was found...` | Wrong URL | You hit `/api/v1/...` or `/api/user/...`. Use `/api/v1.1/...`. |
| `something went wrong, we are sorry` | Auth failed before validation | Same fix as the first row — auth scheme is wrong. |
| `DocumentUniqueKey already exists` | Idempotency hit | Look up the prior receipt using your own donation ID; don't retry. |

---

## 14. Test-connection pattern (no dedicated ping endpoint)

YeshInvoice doesn't expose a `ping` or `getAccountInfo` endpoint, so
the way to verify credentials is to deliberately call `createDocument`
with a payload that's missing required fields, and check the error
message:

```
POST /api/v1.1/createDocument
Authorization: {"secret":"...","userkey":"..."}

{}
```

- `מפתח SECRET KEY לא חוקי` → keys are wrong.
- `אנא הזן שם הלקוח/בית העסק` → keys are good (auth passed; only the
  body validation failed). **This is the success signal for a
  "test connection" button.**

---

## 15. Mapping Matat → YeshInvoice for a typical ILS donation

This is the recipe `app/services/yeshinvoice_service.py` should
follow when a USD-vs-ILS routed-to-YeshInvoice donation comes in.

⚠ Heads-up: the `CurrencyId` mapping and the `payments[].TypeID`
values in this snippet are **pseudocode** — only `ILS=2` and `TypeID=5`
are confirmed (see §4 and §8). Verify the rest with YeshInvoice
support before flipping the integration on for non-ILS or non-Other
payment types.

```python
def build_payload(donation, donor):
    return {
        # — meta — (field names verified by live test on 2026-04-29)
        "DocumentType":              11,                      # Section 46 donation receipt — verified with YI support
        "CurrencyId":                2,                       # ILS — verified default
        "LangId":                    359,                     # 359=HEB, 139=ENG — verified
        "sourceType":                1,                       # verified — required field per yeshinvoice_body.json
        "statusID":                  2,                       # used in verified test bodies; check whether final issued docs need 1
        "DateCreated":               donation.created_at.strftime("%Y-%m-%d %H:%M"),
        "MaxDate":                   donation.created_at.strftime("%Y-%m-%d %H:%M"),
        "hideMaxDate":               True,
        "DontCreateIsraelTaxNumber": False,
        "DocumentUniqueKey":         f"matat-{donation.id}",
        "OrderNumber":               f"matat-{donation.id}",
        "Title":                     f"תרומה — {donor.full_name or donor.company_name}",
        # — donor —
        "Customer": {
            "Name":         donor.full_name or donor.company_name,
            "NameInvoice":  donor.full_name or donor.company_name,
            "FullName":     donor.full_name or donor.company_name,
            "NumberID":     donor.teudat_zehut or "",
            "EmailAddress": donor.email or "",
            "Address":      donor.address_line1 or "",
            "City":         donor.city or "",
            "Phone":        donor.phone or "",
            "ZipCode":      donor.zip or "",
            "CountryCode":  (donor.country or "IL")[:2].upper(),
            "CustomKey":    f"matat-donor-{donor.id}",
            "ID":           donor.yeshinvoice_customer_id or -1,
        },
        # — what the donor paid for —
        "items": [{
            "Quantity": 1,
            "Price":    donation.amount_dollars,
            "Name":     "תרומה לעמותה — מתת מרדכי",
            "Sku":      "DONATION",
            "vatType":  2,                                    # פטור — exempt (donations); verified
            "SkuID":    -1,
        }],
        # — how they paid —
        "payments": [build_payment_object(donation)],
    }
```

`build_payment_object` switches on `donation.payment_processor`:
- Nedarim / Stripe credit card → `TypeID: 4`, `CardLastDigits`, etc.
- Manual check → `TypeID: 2`, `CheckNumber`, etc.
- Bank transfer / Zelle → `TypeID: 3`.
- Other → `TypeID: 5`.

---

## 16. Action items for the existing codebase

1. **Rewrite `app/services/yeshinvoice_service.py`** — the URL, the
   auth scheme, and the endpoint names are all wrong. Use the spec in
   this document.
2. **Move config**: add `ConfigSettings.yeshinvoice_default_doc_type`
   default → `11`. Stop letting operators pick `1`.
3. **Wire it into the donation flow**: when an ILS donation succeeds
   AND `donor.country == 'IL'` AND `ConfigSettings.yeshinvoice_enabled`,
   call `createDocument`, store `id` and `docNumber` on the
   `Donation`, and skip the matatmordechai.org US-receipt email
   (`send_receipt_email` already gates on country).
4. **Test-connection button** in admin settings — change the
   implementation to use the empty-`createDocument` trick from §14.
5. **Add a "Cancel YeshInvoice receipt" button** on the donation
   detail page (admin) for cleaning up tests / mistakes. Only show
   when `donation.yeshinvoice_doc_id` is set; on click, call
   `cancelDocument` and clear that field.

---

*Last updated: 2026-04-29 — derived from the live YeshInvoice docs at*
*<https://user.yeshinvoice.co.il/api/doc?an=createdoc>. Re-verify*
*against that page if anything in this doc looks wrong.*
