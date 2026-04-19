# Delegation Playbook — running Cursor / other Claudes in parallel

**Who this is for:** the human driver (you) running multiple AI agents on the same
repo to get things done faster.

**Goal:** carve a task into independent chunks that a second agent (Cursor, or
another Claude) can execute without stepping on the main Claude's work.

---

## When delegation works

- **Independent features** — one file per feature, no shared scaffolding changes
- **Wide, shallow work** — e.g. "add 5 more reports, each identical pattern"
- **Translation / i18n** — add N keys to en.json + he.json
- **Test writing** — tests are independent per feature
- **Bug fixes with a reproducer** — clear input, clear fix location

## When delegation HURTS

- **Cross-cutting refactors** — a shared schema change means both agents conflict
- **UI-wide redesigns** — every template touches the same layout
- **Config / auth / i18n infrastructure** — the base definitions

---

## The pattern

1. Main Claude (me) finishes the shared foundation and commits to `master`.
2. Main Claude drafts a self-contained **task spec** in this repo under
   `delegation/<task-slug>.md`. The spec contains everything a cold-start
   agent needs (no conversation memory).
3. User opens Cursor in this repo on a **new branch** (`delegation/<task-slug>`).
4. User pastes the task spec into Cursor's chat.
5. Cursor reads the spec, writes code, commits to its branch, pushes.
6. Main Claude pulls the branch, reviews, merges to master.
7. Cursor's branch is deleted.

---

## Task spec template

Every `delegation/<task-slug>.md` MUST include:

```markdown
# Task: <short imperative>

## Context
- Repo root: F:\matat_git (Windows) / /mnt/f/matat_git (WSL)
- You have NO memory of prior chats. Everything you need is in this file
  or in the files it references.
- Assume you CAN run bash, Python, git, and edit files. Assume the venv at
  F:\matat_git\venv already exists — use ./venv/Scripts/python.exe for Python.

## Files you WILL modify / create
- <list of absolute paths>

## Files you MUST NOT touch
- <list of paths that are off-limits — e.g. other delegation branches,
  migrations, anything in app/models/ if this isn't a schema change>

## Acceptance criteria
- A bulleted list of concrete, testable outcomes.
  e.g. "curl http://localhost:5060/gemach/reports/new_report returns 200"
       "./venv/Scripts/python.exe -m pytest tests/test_new_report.py passes"
       "Hebrew label 'דו״ח חדש' appears in the switchboard"

## Commit + push instructions
- Branch name: delegation/<task-slug>
- Commit messages: imperative, one commit per logical chunk
- Co-author line: Co-Authored-By: Cursor <cursor@local>
- Push when done: git push -u origin delegation/<task-slug>

## Dependencies you can use
- All existing code in the repo
- Packages already in requirements.txt
- The shared reports infra: app/utils/reports.py
- DO NOT add new top-level packages without flagging

## Hand-back expectations
- PR URL or branch name (you'll get it from the git push output)
- Short summary of what you did, delivered in comments on the branch
- One-sentence list of anything that didn't work as expected
```

---

## Example: the next 3 reports to delegate

If you want to offload more reports to Cursor, write a spec like this and
point Cursor at it:

```markdown
# Task: add Checks Report + Bounces Report + Active Standing Orders report

## Context  (see template above)
## Files you will create
- app/blueprints/gemach/reports_v2.py            # new module for your reports
- app/templates/gemach/reports/_checks.html      # if you need custom layout
## Files you must not touch
- app/blueprints/gemach/reports.py   (the 8 existing reports)
- app/utils/reports.py                (the shared infra)
## What to build
1. Checks Report — /gemach/reports/checks
   Data source: GemachTransaction filtered by payment_method LIKE '%check%'
   Columns: date, card_no, member, check_number, amount_ils, amount_usd,
            bank_code, branch_code, account_number, receipt
   Default sort: date DESC
2. Bounces Report — /gemach/reports/bounces
   Data source: GemachLoanTransaction.filter_by(bounced=True)
   Columns: date, loan_num_hork, member, amount_ils, bounce_reason, asmachta
3. Active Hork Report — /gemach/reports/active_hork
   Same shape as existing loans report but filtered to status='p',
   sorted by charge_day then member last_name.

## Acceptance criteria
- All three endpoints return 200 and show Hebrew headers
- Each has ?format=pdf and ?format=xlsx that return valid files
- Switchboard links added to app/templates/gemach/reports.html for all three
- No raw "gemach.*" keys leak to the HTML (use t() + add i18n keys)

## Commit + push
git checkout -b delegation/checks-bounces-active-hork
... do the work ...
git push -u origin delegation/checks-bounces-active-hork
```

---

## Review checklist (for main Claude on merge)

Before merging a delegation branch:

- [ ] Lint clean: `./venv/Scripts/python.exe -m py_compile` on every .py
- [ ] Import clean: app starts without errors after pulling the branch
- [ ] All new endpoints return 200 for admin + gemach_user roles
- [ ] No raw i18n keys leak in either language
- [ ] No regressions: run the test client sweep
  ```
  for ep in /gemach/ /gemach/members /gemach/reports /gemach/loans /gemach/transactions; do
    curl -s -o /dev/null -w "$ep %{http_code}\n" http://localhost:5060$ep
  done
  ```
- [ ] Commit history is clean (squash if needed before merge)
- [ ] Merge with `git merge --no-ff` to preserve the delegation branch history

---

## Running Claude in YOLO mode (for the user)

When driving multiple projects, skip the permission prompts:

```
Double-click:  F:\matat_git\start_claude_yolo.bat
```

This runs `claude --dangerously-skip-permissions` in the project dir.
All tool calls are auto-approved. Use only when you trust the session
and can't be interrupted for prompts.

To exit: type `/exit` or press Ctrl+C twice.

---

## When NOT to delegate

If the task is any of these, keep it in the main Claude session:
- Anything touching `app/models/`, migrations, or `app/__init__.py`
- Payment processor changes
- Anything involving SANDBOX_MODE / security gates
- The i18n loader (`app/utils/i18n.py`)
- The feedback widget (it's on its own branch already)
- The operator's PC Claude (that's already a separate session by design)
