# Setup Guide: Operator PC (Sandbox Install)

**Audience:** Claude Code running on the operator's Windows PC.
**Goal:** Install the full Matat + ZTorm + Gemach Flask stack as a **sandbox**:
real data pulled from her live Access files (`C:\Gmach\MttData.mdb`, `C:\ztorm\ztormdata.mdb`),
no live transactions — no bank charges, no emails, no SMS.

**Starting state assumed:**
- Windows 10 or 11
- No Python installed
- No Git installed (optional)
- Microsoft Access 2003-era apps at `C:\Gmach\` and `C:\ztorm\` (she uses them daily)
- Microsoft Access Database Engine (or Office) already installed
  (verify with `Get-OdbcDriver | Where-Object Name -like '*Access*'` — should list Jet 4.0)

---

## Step 1 — Install Python 3.12

1. Download **Python 3.12** (any 3.12.x) from https://www.python.org/downloads/
2. Run the installer as **Administrator**
3. **CRITICAL:** check the **"Add Python to PATH"** box on the first screen
4. Click "Install Now"
5. Verify in a **new** PowerShell:
   ```powershell
   python --version
   ```
   Should print `Python 3.12.x`. If "not recognized", restart the shell after install.

## Step 2 — Get the code

**Option A (recommended):** install Git for Windows, then clone:
1. Download Git from https://git-scm.com/download/win — use defaults
2. Open a new PowerShell:
   ```powershell
   cd C:\
   git clone https://github.com/cheseddata/matat.git Matat
   ```
   The code lands in `C:\Matat\`.

**Option B (no Git):** download the repo as a ZIP
1. Visit https://github.com/cheseddata/matat/archive/refs/heads/master.zip
2. Extract to `C:\Matat\`
3. Make sure the structure looks like `C:\Matat\app\`, `C:\Matat\install.bat`, etc.

## Step 3 — Run the installer

1. Open `C:\Matat\` in Explorer
2. **Double-click `install.bat`**
3. The installer will do (about 4–5 minutes total):
   - [1/7] Detect Python
   - [2/7] Create a `venv\` (Python virtual environment)
   - [3/7] `pip install -r requirements.txt` (Flask, SQLAlchemy, etc.)
   - [4/7] Write a local `.env` with SQLite + `SANDBOX_MODE=1`
   - [5/7] Create the fresh SQLite database at `instance\matat.db` via Alembic migrations + seed `admin / admin123`
   - [6/7] **Pull her live data** from `C:\Gmach\MttData.mdb` and `C:\ztorm\ztormdata.mdb`
   - [7/7] Create a Desktop shortcut called "Matat (Sandbox)"
4. Leave the window open until it says "Install complete" and "Press any key to continue"

## Step 4 — Launch & verify

1. Double-click **"Matat (Sandbox)"** on the Desktop
   (or `C:\Matat\start.bat`)
2. A black console window opens and stays open — this is the Flask server. **Do not close it.**
3. The browser opens at `http://localhost:5060/login`
4. Log in: `admin` / `admin123`
5. Every page should show an amber banner across the top:
   > ⚠️ SANDBOX MODE — תצוגת הדגמה / No live transactions…
6. Navigate:
   - **💚 Gemach** (top nav, green link) — Hebrew switchboard with 5 menu buttons
   - **Gemach → Members** — her ~4,000+ Haverim records, Hebrew search
   - **Gemach → Loans** — active Hork records (הו״ק)
   - **Gemach → Transactions** — Peulot + Tnuot (this is the big one, ~230K rows)
   - **🏛 ZTorm** — donations side (if her ZTorm sync succeeded)
7. Switch language with the "עב / EN" button (top-right)

## Step 5 — Operator sign-off

Hand the laptop to the operator. Have her:
- Run her normal day (lookups, reports, whatever she does in Access)
- Report any data she expected to see that's missing
- Report any Hebrew label that reads wrong
- Report any workflow that doesn't match her Access habit

Nothing she does moves real money, sends real email, or modifies the server — it all stays in `C:\Matat\instance\matat.db` on her PC.

---

## Daily use (after install)

- **Start:** double-click "Matat (Sandbox)" on Desktop → browser opens automatically
- **Stop:** close the black console window
- **Refresh her live data** (re-pulls from C:\Gmach and C:\ztorm): double-click `C:\Matat\sync_live_data.bat`

---

## Troubleshooting

### "Python is not recognized"
PATH wasn't set during Python install. Run the installer again and tick "Add Python to PATH", or add `C:\Users\<her>\AppData\Local\Programs\Python\Python312` and `...\Python312\Scripts` to PATH manually.

### "Microsoft Jet database engine not found" during sync
The 32-bit Access Database Engine redistributable is missing. Install it from
https://www.microsoft.com/en-us/download/details.aspx?id=54920 (pick `AccessDatabaseEngine.exe` — the 32-bit one, not 64-bit).

### Port 5060 already in use
`start.bat` auto-falls back to 5061. If both are taken, edit `start.bat` and set `set PORT=<free port>`.

### Sync fails but install finished
The empty DB and empty tables are OK — she can still log in and see the UI. To retry the sync later, double-click `sync_live_data.bat`.

### Full reset
Delete `C:\Matat\venv\`, `C:\Matat\instance\matat.db`, `C:\Matat\.env` — then double-click `install.bat` again.

---

## What the sandbox CANNOT do

- **No real credit card charges.** All payment processor calls return a fake "success" with a `sbx_` transaction ID.
- **No real emails.** Emails are logged to the `message_queue` table but never sent to an SMTP/API.
- **No real SMS.** Same — logged, not sent.
- **No server contact.** This install talks only to `C:\Gmach`, `C:\ztorm`, and its own `instance\matat.db`.

To lift the sandbox (go live on the server, not on her PC), see `SESSION_HANDOFF.md` (deferred — only after operator sign-off).

---

## Files created by install

```
C:\Matat\
├── venv\                        (Python virtual environment, ~200 MB)
├── instance\
│   └── matat.db                 (SQLite DB — empty after migrations, populated after sync)
├── .env                         (DATABASE_URL, SANDBOX_MODE, etc.)
├── start.bat                    (daily launcher)
├── install.bat                  (one-time install)
├── sync_live_data.bat           (re-sync her Access data)
├── OPERATOR_README.md           (Hebrew quick reference for her)
└── SETUP_OPERATOR_PC.md         (this file)
```

Plus a Desktop shortcut: **"Matat (Sandbox)"**.
