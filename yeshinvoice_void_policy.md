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

## Probe-generated documents needing manual void

These were created by automated testing while we were chasing the
schema; they are real documents in the live account:

- `id 8320455`, `docNumber 30001` — yeshbe.co/CQWU9NE
- `id 8320456`, `docNumber 30001` — yeshbe.co/zDL2pN7

Either void them via the YeshInvoice portal UI (Documents screen), or
once `create_credit_note` is verified working, issue a credit doc for
each one.

## Open questions for YeshInvoice support

1. What is the correct `DocumentType` numeric code for
   **credit document / negative receipt**? (We guessed 4 from the docs
   panel's range, but needs confirmation.)
2. Does the credit-document payload need a `RelatedDocumentId` field
   (or similar) pointing at the original `id` being offset, or is
   matching done purely by donor + amount?
3. Are there special required fields on a negative-amount document
   that aren't required on a positive one (e.g., reason/note,
   reference to original docNumber)?
