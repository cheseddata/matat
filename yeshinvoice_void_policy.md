# YeshInvoice — Document Void / Delete Policy

Confirmed by YeshInvoice support, 2026-04-29:

> You can view all issued invoices and documents in the Documents screen
> on the website.
> Please note that issued documents cannot be deleted, as deleting
> official documents is not allowed.
> If you need to cancel a specific receipt or invoice, you can issue
> a negative receipt (or credit document) to offset and cancel the
> original document.

## What this means in practice

| Action | Possible? | How |
|---|---|---|
| **Delete a document** | ❌ No | Israeli tax/audit rules forbid deleting issued documents. Confirmed via API probing too — 22 endpoint variants tested, all 404. |
| **Void a document** | ✅ Yes | Issue a *negative* `createDocument` (or a credit-document DocumentType) that offsets the original. The original stays in the records; the void appears as a separate adjacent document. |
| **View documents** | ✅ Yes | YeshInvoice portal → Documents screen. |

## Implementation in this codebase

- **`yeshinvoice_service.create_credit_note(donation, ...)`** issues a
  counter-document via the same `POST /api/v1/createDocument` endpoint as
  regular receipts, with negative amounts. The exact `DocumentType` code
  for credit notes (currently coded as `4`, a guess) needs YeshInvoice
  confirmation.
- **No "delete" endpoint exists**, public or otherwise.

## Confirmed via live test (2026-04-29)

Voiding works exactly as YeshInvoice support described. The two probe
docs were successfully offset by issuing credit documents:

| Original | Void doc |
|---|---|
| id 8320455, docNumber 30001, ₪18.00 | **id 8322897, docNumber 40001, ₪-18.00** |
| id 8320456, docNumber 30001, ₪18.00 | **id 8322899, docNumber 40001, ₪-18.00** |

### Confirmed answers

| Question | Answer |
|---|---|
| Correct `DocumentType` for credit | **4** (verified — created `Success: true` voids) |
| `DocumentType=11` with negative Price | **Rejected** — returns `"אנא הזן רשימת תקבולים"` (requires a payments list). Receipts can't go negative; you must use a separate credit-doc type. |
| Schema differences vs. issuing path | None — same `CurrencyId=2 / LangId=359 / vatType=2 / sourceType=1 / statusID=2`, same nested `Customer`, same lowercase `items`. Only `DocumentType` (4 instead of 11) and `Price` sign (`"-18.00"`) change. |
| Link-back field name | Sent both `RelatedDocumentId` and `OriginalDocumentID`. Server didn't reject either. The credit doc will reference the original via portal Documents screen regardless. |

### Numbering observation

Credit docs get their own sequence: both voids came back as `docNumber 40001`
(both my first credit doc, separate counter). Receipt-type docs use the
30000-range, credit docs use 40000-range. So credit numbering is
independent of receipt numbering.
