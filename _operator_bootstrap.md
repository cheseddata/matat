# Operator PC — Bootstrap Prompt (2026-04-20)

**To Claude running on the operator's Windows PC at `C:\Matat\`:**
**You have no memory of the dev-PC conversation.** Everything you need is here.

---

## Quick summary — what changed today

Dev Claude (on the developer's PC) reproduced the Access Gmach UI to match the
operator's reference screenshots. The goal is **pixel-faithful Access 2003 look**
so the operator's muscle memory carries over.

Landed on master today (newest first):

```
4bb7ee0  Member detail: faithful Access כרטיס תורם reproduction
8d41def  Switchboard + submenus match Access תפריט ראשי look
1fffe49  Fix url_for kwarg on member linked-donor link
78787fa  Add 4 gemach.* i18n keys used by operator-merge templates
dd6ebef  Operator sandbox polish: auto-login, Hebrew Gemach landing, icon, no-pause exit
971e03b  Add operator feedback widget (Report issue button + auto git backup)
a8286c0  Ticket 3 (loans search + card column) + Access-sync UI + detail polish
```

### What the new look looks like

1. **Main menu (`/gemach/`)** — classic Windows 2000 gray window:
   - Gray titlebar "תפריט ראשי"
   - Cyan banner with black border: "מערכת ניהול גמ״ח"
   - 5 centered beveled buttons: **כרטסת** / **תכניות** / **דוחות** / **תחזוקה** / **עזרה**
   - Exit door icon bottom-left

2. **כרטסת click → `/gemach/members`** (unchanged — member list)

3. **Click a member → dark-teal kartis torem** with:
   - Top-left toolbar: סגור / print / wrench / חפש (binoculars)
   - Search header: מיון sort, מס׳ כרטיס yellow badge, שם, חיפוש
   - 5 tab strip: `1: פרטים` / `2: פרטים` / `3: הו״ק` / `4: תנועות` / `5: מעקב`
   - Left vertical nav: לקודם ↑ / לבא ↓ — jumps to prev/next member by card_no
   - Bottom counter: `רשומה: N ◀ ▶ מתוך 4,112`

4. **תכניות (programs) submenu**: Masav prep / Hash export / Access sync
5. **תחזוקה (maintenance) submenu**: institutions/lookups stubs + link to admin users
6. **עזרה (help)**: Hebrew how-to page

### Known placeholders (NOT BUGS to report unless they break)
- On tab 3 (הו״ק): the 6 action buttons (קליטה / חידוש / ביטול / עדכון / מעקב / קבלה) are visual-only right now. In the sandbox they don't need to do anything yet.
- On tabs 3 and 4: the sub-form below the grid shows the *first* row's details, not the clicked row's. Making it interactive needs JavaScript — not in scope yet.
- On תחזוקה submenu: מוסדות / סיבות ביטול / סוגי תנועות links have `#todo-*` anchors. Admin users link works.

---

## What you need to do

### Step 1 — Pull + rebase the operator branch
```
cd C:\Matat
git fetch origin
git checkout operator-feedback-widget
git rebase origin/master
```
Expect conflicts only on CLAUDE.md (changelog). If any file has a real conflict on the template/code side, stop and ask the user.

Resolve CLAUDE.md by taking both sides' changelog entries (union-merge):
```
git checkout --ours CLAUDE.md   # or --theirs depending on which has more
# manually union if needed
git add CLAUDE.md
git rebase --continue
```

Then force-push:
```
git push --force-with-lease origin operator-feedback-widget
```

### Step 2 — Install new Python packages if any
```
.\venv\Scripts\python.exe -m pip install -r requirements.txt --upgrade
```
(requirements haven't changed since the last pull, but run it to be safe)

### Step 3 — Re-launch the app
1. Close the existing desktop window if open
2. Double-click `C:\Matat\start.bat` (or `"Matat (Sandbox)"` on Desktop)
3. Should open directly on the new Hebrew main menu (auto-login still works)

### Step 4 — Smoke-test the new UI (YOU, quickly, before handing to operator)
1. **Main menu** — should look like Windows 2000 gray window with 5 vertical buttons and a cyan banner. **NOT** the old dark-navy numbered tiles.
2. Click **כרטסת** → member list (unchanged)
3. Click any member (try one with loans, e.g. card 3717) → should open the **dark-teal kartis torem** with the toolbar + 5 tabs
4. Click through all 5 tabs — each should render without a 500
5. Click the **left ↑/↓ arrows** (לקודם / לבא) — should jump to prev/next member
6. Click **סגור** (door icon top-left) → back to member list
7. Back to main menu → click **תכניות** → 3-button submenu; click Masav; back; click **תחזוקה** → 5-button submenu; click **עזרה** → help page
8. Check the **bottom-left orange "דווח על בעיה" (Report issue)** button is still there — the feedback widget is preserved

### Step 5 — Report issues via the feedback widget
If anything looks visually wrong (colors, missing icons, broken layout), take a screenshot via the widget. It auto-pushes to `origin/operator-feedback` branch where dev Claude can pull + fix.

### Step 6 — Hand to the operator
Tell her:
- "לחץ על כרטסת כדי לראות את רשימת החברים"
- "המסך נראה עכשיו כמו התוכנית הישנה באקסס — אותם כפתורים, אותן לשוניות"
- "אם משהו לא נכון או חסר — הכפתור הכתום למטה משמאל ישלח לנו דיווח עם צילום מסך"

---

## Things NOT to touch
- `.claude/` (per-dev settings, gitignored)
- `C:\Gmach\` and `C:\ztorm\` (her live Access data — read-only)
- `app/models/` and `migrations/` (schema changes come from dev master only)
- Any .bat files that already work — if you find a bug, fix it minimally and commit

## Report back
After Step 4 finishes, commit this summary to `operator-feedback-widget`:
```
docs: operator PC sync summary 2026-04-20

Pulled master up to 4bb7ee0.
  - main menu:        [pass/fail]
  - kartis tab 1:     [pass/fail]
  - kartis tab 2:     [pass/fail]
  - kartis tab 3:     [pass/fail]
  - kartis tab 4:     [pass/fail]
  - kartis tab 5:     [pass/fail]
  - left nav prev/next: [pass/fail]
  - bottom record counter: [pass/fail]
  - תכניות / תחזוקה / עזרה submenus: [pass/fail]
  - feedback widget:  [pass/fail]

Operator notes: <whatever she reports>
```
Then push.
