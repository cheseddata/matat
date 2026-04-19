# Operator PC — Bootstrap Prompt

**Addressed to:** Claude Code running on the operator's Windows PC at `C:\Matat\`.
**You have no memory of the dev-PC conversation.** Everything you need is here.

---

## Your starting state

- You're on branch `operator-feedback-widget`
- Last commit you made: `af139b0` (feedback widget + auto-git-push)
- Master has moved forward with major upgrades (5 commits since your last sync)
- The operator is a Hebrew-speaking non-technical user. **She does not touch code.** She'll test workflows and describe problems in plain language.

## What the main Claude shipped (commits you need to pull)

```
e421785  Wire Masav + Hash switchboard tiles (no more "Coming Soon")
ae037ec  YOLO launcher for Claude Code GUI + settings.local.json
8158993  Fix WERKZEUG_RUN_MAIN crash in start.bat
067c052  Delegation playbook + operator setup guide updates
361ebe1  ★ FULL REPORTS + MASAV + HASH + DESKTOP LAUNCHER (major)
490c08a  Fix seed_admin.py AttributeError you caught earlier
```

### What changed in plain English

1. **Desktop-app launcher (no browser)** — `start.bat` now opens the app in a native window via pywebview. No more port conflicts, no tabs, no timing popups. Random free port on 127.0.0.1.

2. **All 8 Gemach reports are now LIVE:**
   - Loans, Summaries, Donations, Deposits, Supports, Gmach Totals, Address Labels, Masav Totals
   - Every report has **PDF + Excel + Print** buttons
   - Hebrew labels throughout, RTL layout

3. **Masav Collection (direct-debit) — works end-to-end in sandbox:**
   - `/gemach/masav` lets her select active loans and generate a real Masav fixed-width bank file
   - File written to `instance/masav_batches/MSV-YYYYMMDDHHMMSS.msv` + `.json` sidecar
   - In sandbox mode: **no transmission to bank** — just the file she can inspect

4. **Hash Export (accounting) — works end-to-end in sandbox:**
   - `/gemach/hash` lets her pick date range and generate a CSV of transactions
   - File written to `instance/hash_exports/HASH-*.csv`
   - In sandbox mode: **no upload to accounting system**

5. **Main switchboard tiles 5 + 6 are now clickable** (were "Coming Soon" before)

6. **New Python dependencies to install:** `pywebview`, `reportlab`, `openpyxl`

## What you need to do

### Step 1 — Pull master, rebase your branch
```
cd C:\Matat
git fetch origin
git checkout operator-feedback-widget
git rebase origin/master
```

If the rebase conflicts on a file you don't care about (e.g. she didn't touch switchboard.html), resolve by taking master's version:
```
git checkout --theirs <path>
git add <path>
git rebase --continue
```

Then force-push your branch:
```
git push --force-with-lease origin operator-feedback-widget
```

### Step 2 — Install new Python deps into the venv
```
.\venv\Scripts\python.exe -m pip install -r requirements.txt --upgrade
```
Takes ~1 minute. If `pywebview` install fails, try `.\venv\Scripts\python.exe -m pip install pywebview reportlab openpyxl` directly.

### Step 3 — Re-launch the app
1. Close the existing app window if open
2. Double-click `C:\Matat\start.bat`
3. **A native desktop window should open** (not a browser tab). Title: `מתת מרדכי - Matat / ZTorm / Gemach (SANDBOX)`
4. Log in: `admin` / `admin123`

### Step 4 — Smoke-test the new features (you do this yourself, quickly)
In the app window:
- Click **💚 Gemach** → switchboard should have **6 clickable tiles** (no more greyed-out "Coming Soon")
- Click **Reports** (tile #4) → all 8 report tiles open + 2 operation tiles (Masav, Hash)
- Click **Loans Report** → HTML table loads → click PDF button → file downloads
- Click **Excel** button → .xlsx downloads
- Back to Reports → click **Masav Collection** (orange M tile) → loans listed → click "צור אצווה" → sandbox flash in Hebrew → check `instance/masav_batches/` for the .msv file
- Back to Reports → click **Hash Export** (blue H tile) → pick a date range → "ייצא CSV" → check `instance/hash_exports/`

If any of those fail, commit a short issue note to `operator-feedback-widget` branch and push so main Claude sees it on origin.

### Step 5 — Hand the laptop to the operator
Tell her:
- "Click the green 💚 Gemach tab at the top right"
- "Look around, click things, try to break it, run your usual reports"
- "If something looks wrong or missing, click the orange 'Report issue' button (bottom-left) — it sends a screenshot + her note back to us"

The feedback widget is already on this branch (commit `af139b0`); it auto-pushes each ticket to `origin/operator-feedback`.

## What to commit back if you make fixes

Small fixes for operator-PC-only concerns (window size, Hebrew font tweaks, etc.) → commit to `operator-feedback-widget`, push.
Fixes that apply to everyone → commit to a new `fix/<thing>` branch and push; main Claude will pull + merge to master.

## Things NOT to touch

- `.claude/` folder (per-user settings, gitignored)
- `C:\Gmach\` and `C:\ztorm\` (her live Access data — read-only)
- `app/models/` and `migrations/` (schema changes must come from master)

## Report back expectations

When done with Step 5, commit this summary to `operator-feedback-widget`:
```
docs: operator-pc sync summary

Pulled master up to e421785. Venv upgraded. Desktop window opens cleanly.
Smoke test results:
  - switchboard tiles:   [pass/fail]
  - loans report html:   [pass/fail]
  - loans report PDF:    [pass/fail]
  - loans report Excel:  [pass/fail]
  - masav batch gen:     [pass/fail]   file: <path>
  - hash csv export:     [pass/fail]   file: <path>

Operator notes: <whatever she said>
```

Then push. That's the handoff complete.
