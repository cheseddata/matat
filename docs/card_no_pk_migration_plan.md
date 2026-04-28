# Migration plan: switch `gemach_members` PK from synthetic `id` to Access `card_no`

Status: DRAFT — for operator review before any code change.

## Why

Operator's instruction: "use the access card number as the primary key."

Today the Flask `GemachMember` model uses an auto-increment `id` (Flask-style)
plus a separate `gmach_card_no` column. Every relationship (`gemach_loans.member_id`
→ `gemach_members.id`) is keyed on the synthetic id. This means:

1. We have a translation layer between Access (where everyone is keyed by
   `card_no`) and the website (keyed by `id`). That layer hides bugs (we hit
   one yesterday with `counter` vs `card_no` in the MASAV fix).
2. Cross-source joins to the verbatim mirror (`mirror/MttData.db`) need a
   lookup table to convert `id` ↔ `card_no` on every query.
3. Dedup and merge tools have nowhere to put `old_card_no → primary_card_no`
   aliases without yet another translation layer.

Switching the PK to `card_no` removes all of that. SQL becomes:
`SELECT ... FROM gemach_members m JOIN Hork h ON h.card_no = m.card_no` —
no translation, no FK to a synthetic id, matches Access semantics 1:1.

## What changes

| Model | Before | After |
|---|---|---|
| `GemachMember` | `id` (autoinc PK), `gmach_card_no` (unique) | `card_no` (PK), no `id` |
| `GemachLoan` | `member_id` FK -> `gemach_members.id`, `gmach_num_hork` | `card_no` FK -> `gemach_members.card_no`, `num_hork` |
| `GemachTransaction` | `member_id` FK | `card_no` FK |
| `GemachLoanTransaction` | `loan_id` FK -> `gemach_loans.id` | `num_hork` FK (since `Hork.num_hork` is unique on Access side too) |
| `GemachCancelledLoan` | mirrors GemachLoan | mirrors GemachLoan |
| `GemachInstitution` | `id` PK, `gmach_num_mosad` | `num_mosad` PK |
| `GemachMemorial` | `id` PK, `member_id` FK | keep `id`, change FK to `card_no` |

Column renames (verbatim Access names per our rule):
- `gmach_card_no` → `card_no`
- `gmach_num_hork` → `num_hork`
- `gmach_num_mosad` → `num_mosad`
- `payments_made` → `buza`
- `total_expected` → `sach_buza`
- `bounces` → `hazar`
- `committed_payments` → `hithayev`
- `period_months` → `tkufa`
- `last_charge_date` → `date_hiuv_aharon`
- `start_date` → `date_hathala`
- `loan_type` → `sug`
- `amount_paid` → `shulam`

Routes + templates: ~30 places touch `member.id` or `loan.member_id` —
each gets a one-line change to `member.card_no`.

## Migration steps (Alembic)

1. **Read all data** out of current `gemach_*` tables into a backup SQLite.
2. **Drop** all `gemach_*` tables (clean slate; we have the mirror as source).
3. **Create** new tables with verbatim Access names + `card_no` PK.
4. **Re-import** from `instance/mirror/MttData.db` (verbatim) — this
   becomes the new authoritative populate path. Replaces today's
   `import_gmach_data.py` translation logic.
5. **Run** the existing test suite + the MASAV byte-for-byte test to confirm
   we still produce the same MASAV file with the new column names.

## Rollback

- The Alembic migration is reversible: keep the backup SQLite from step 1.
- If anything fails, restore `instance/matat.db` from `instance/matat.db.before-pk-migration.bak`
  and revert the migration commit.

## Why this comes AFTER the parallel agents land

- **Agent A** (verification) doesn't touch models — independent.
- **Agent B** (customer history) reads from `mirror.db` directly, not
  `gemach_*` — independent.
- **Agent C** (reports) reads from `mirror.db` directly — independent.

So all three can land first without conflict. Then PK migration is a single
serialized step on this thread.

## Estimated scope

- ~12 model column renames in 4 files (`app/models/gemach_*.py`)
- ~30 callsite updates in `app/blueprints/gemach/{routes,reports,extras,sync,masav}.py`
- ~8 template references (`gemach/member_detail.html`, `loan_detail.html`,
  `members.html`, etc.)
- 1 Alembic migration script
- 1 importer rewrite (`sync/import_gmach_data.py` → reads mirror.db, no
  translation)
- Verification: MASAV byte-test still passes; member detail page
  renders the same record set; loans page count unchanged.

## Decision needed from operator

1. Go ahead with the rename to verbatim Access names everywhere?
2. Or alias-only — keep `gmach_card_no` etc. but ALSO expose `card_no` as a
   computed column? (Less invasive but doesn't fully resolve the rule.)

Operator preference noted: "use the access card number as the primary key" —
suggests option 1 (full rename). Confirming before any write.
