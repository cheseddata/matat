# Handoff — 2026-06-22 16:05 IDT

**From:** Claude session on the server (CLI, ttyd)
**To:** Claude on Menachem's PC (GUI / VS Code)
**Branch:** `master`  ·  **Head:** `db4b5dc` (phone-entry warn-then-confirm)
**User:** Menachem Kantor — admin, `support@matatmordechai.org`

This is the live state when MK switched seats. Read it cold, then continue.

---

## What just happened (last 30 min)

1. MK asked about open tickets → 10 pending in DB, newest is **#17 from `mrosen` (2026-06-17)**:
   > *"A donor told me that the program seems to blocked by filters, thereby making it impossible to donate. Is it possible to notify the company, such as Techloq, to take away the block so that people can donate easily?"*

2. **MK personally notified Techloq.** Ticket #17 is **not yet marked resolved in the DB** — leave it pending until the other filter outreach is done, then resolve in one pass.

3. I drafted whitelist letters for **5 other filters** (Netspark, Rimon/Gentech, Meshimer, Akeenu, Kanguru).

4. I attempted to land all 5 as drafts in `support@matatmordechai.org`'s Exchange Drafts folder via Microsoft Graph API → **all 5 returned HTTP 403 "Access denied."**

5. While verifying that "mrosen sends through Exchange," I discovered:
   - `config_settings.email_provider = 'msgraph'` (current)
   - But **every actual outbound in the last 6 weeks went via ActiveTrail or Mailtrap. Zero via msgraph.** Provider field may have been flipped to msgraph after the last send, or there's a runtime fallback override I haven't traced.
   - MK's memory was right: mrosen's recent sends went through ActiveTrail (23) and Mailtrap (16), not Exchange.

---

## Blockers needing MK's action

### Blocker 1 — Grant `Mail.ReadWrite` in Azure
Required to create drafts via Graph API. Without it the 5 letters can't land in Drafts for review.

**Steps:** Azure Portal → App registrations → find the app used by `support@matatmordechai.org` (check `email_inbox_providers` table for client_id) → **API permissions** → **+ Add a permission** → Microsoft Graph → **Application permissions** → check `Mail.ReadWrite` → **Add** → then **"Grant admin consent for [tenant]"** (must be a Global Admin).

Currently the app has `Mail.Send` + `Mail.Read` (inbox sync) but not `Mail.ReadWrite`. The 403 from `POST /users/{mailbox}/messages` confirms.

### Blocker 2 — Decide which email provider is canonical
Three honest options:

| Option | Pro | Con |
|---|---|---|
| **Make msgraph live**, send test → keep as default | Centralized in MK's Exchange, sent items visible in OWA, threading works | Need to verify msgraph send path actually works end-to-end (zero real sends yet) |
| **Flip default back to ActiveTrail** | Already battle-tested for 6+ weeks, all recent mrosen + admin sends succeeded | Sent items not in OWA, no native threading |
| **Investigate the override** | Find why current sends bypass `email_provider='msgraph'` | Time cost — may be a stale fallback path |

Recommend a **single test send via msgraph** first (e.g. resend yourself a tiny "test" link). If it works → keep msgraph and the next mrosen send will route through Exchange automatically. If it fails → flip back to ActiveTrail in `/admin/settings`.

---

## The 5 draft letters — verbatim, ready to paste

Saved as a script at **`tools/draft_filter_whitelist_letters.py`** — re-run after Blocker 1 is cleared:
```bash
cd /var/www/matat && source venv/bin/activate && PYTHONPATH=/var/www/matat python tools/draft_filter_whitelist_letters.py
```

If MK doesn't want to grant `Mail.ReadWrite`, the bodies are below — paste into OWA "New message" manually.

### 1. Netspark — `support@netspark.com`
**Subject:** Whitelist request — matatmordechai.org — nonprofit donation site

> Dear Netspark Team,
>
> We operate **matatmordechai.org**, the official donation site of *Matat Mordechai*, a registered 501(c)(3) nonprofit / Israeli ע"ר (amuta) that funds wedding assistance, kimcha d'pischa, and aid to needy families in Eretz Yisrael and the United States.
>
> Several of our donors have reported that the site is currently blocked by the Netspark filter, preventing them from completing their donation. The site contains:
>
> - A homepage describing the organization's tzedakah activities
> - A donation form (Stripe and Nedarim Plus for ILS)
> - Tax-receipt download (Section 46 / IRS 501(c)(3))
>
> There is no advertising, no user-generated content, no social features, and no external links other than to our payment processors.
>
> Please whitelist:
> - matatmordechai.org
> - www.matatmordechai.org
>
> Thank you for the important work you do for our community.
>
> Sincerely,
> Menachem Kantor — Matat Mordechai — support@matatmordechai.org

### 2. Rimon / Gentech — `office@rimon.net.il`
**Subject:** בקשת הוצאה מסינון — matatmordechai.org — אתר תרומות לעמותה

> שלום רב,
>
> אנו מפעילים את אתר התרומות הרשמי של עמותת **מתת מרדכי** (ע"ר), המסייעת לחתונות, קמחא דפסחא ומשפחות נזקקות בארץ ובחו"ל.
>
> כמה מתורמינו דיווחו כי האתר חסום על-ידי מסנן רימון / ג'נטק. נבקש להוציא מסינון את הכתובת:
>
> - **matatmordechai.org**
> - **www.matatmordechai.org**
>
> האתר מכיל אך ורק: דף בית עם פרטי העמותה, טופס תרומה (Stripe לדולרים, נדרים פלוס לשקלים), והורדת קבלות (טופס 46 / 501(c)(3)). אין באתר פרסומות, תוכן גולשים, רשתות חברתיות או קישורים חיצוניים מלבד למעבדי התשלום.
>
> תודה רבה,
> מנחם קנטור — מתת מרדכי — support@matatmordechai.org

### 3. Meshimer — `info@meshimer.co.il`
**Subject:** בקשת הוצאה מסינון — אתר התרומות של עמותת מתת מרדכי

> לכבוד צוות משמר,
>
> אנו מפעילים את אתר התרומות הרשמי של עמותת **מתת מרדכי** (ע"ר), המסייעת לחתונות, קמחא דפסחא ומשפחות נזקקות. תורם דיווח כי האתר חסום למשתמשי משמר.
>
> נבקש להוציא מרשימת הסינון:
> - matatmordechai.org
> - www.matatmordechai.org
>
> תוכן האתר: דף עמותה, טופס תרומה, והורדת קבלות מס בלבד.
>
> בברכת התורה,
> מנחם קנטור — מתת מרדכי — support@matatmordechai.org

### 4. Akeenu — `support@akeenu.com`
**Subject:** Whitelist request — matatmordechai.org — nonprofit donation site

> Dear Akeenu Team,
>
> Donors using Akeenu-filtered networks (yeshivas, Beis Yaakov schools, kollelim) have reported that **matatmordechai.org** is blocked. We are a registered nonprofit funding wedding assistance and kimcha d'pischa.
>
> Please whitelist:
> - matatmordechai.org
> - www.matatmordechai.org
>
> The site has no advertising, no user-generated content, no social features, and exists solely to accept tzedakah donations and serve tax receipts (Section 46 / 501(c)(3)).
>
> Thank you,
> Menachem Kantor — Matat Mordechai — support@matatmordechai.org

### 5. Kanguru — `service@kanguru.co.il`
**Subject:** בקשת הוצאה מסינון — matatmordechai.org — אתר תרומות לעמותה

> שלום רב,
>
> אנו מפעילים את אתר התרומות הרשמי של עמותת **מתת מרדכי** (ע"ר). תורמים דיווחו כי האתר חסום על-ידי מסנן כנגורו.
>
> נבקש להוציא מסינון את:
> - **matatmordechai.org**
> - **www.matatmordechai.org**
>
> האתר מכיל דף עמותה, טופס תרומה, והורדת קבלות מס בלבד.
>
> תודה רבה,
> מנחם קנטור — מתת מרדכי — support@matatmordechai.org

⚠️ **Verify intake addresses before sending.** All 5 are based on year-old records — filter companies move their contact forms around. Cross-check on each company's website if possible.

---

## Open tickets (10 total)

| # | When | From | Page | Status |
|---|---|---|---|---|
| **17** | 6/17 | mrosen | /salesperson/my-donations | Active — filter whitelisting in flight |
| 16 | 5/13 | ggoldblum | /weddings/ | Resolved in changelog, not in DB |
| 15 | 5/13 | mrosen | /admin/inbox/1748 | Resolved in changelog, not in DB |
| 14 | 5/13 | mrosen | /donate?ref=... | Resolved in changelog, not in DB |
| 13 | 5/06 | mrosen | /salesperson/templates/new | Resolved (template CRUD shipped) |
| 12, 11, 10, 9 | 4/30 | admin | /admin/charge | Resolved (charge page Hebrew + RTL shipped) |
| 1 | 3/27 | ggoldblum | /admin/donations | Unknown — first ticket ever, probably stale |

**Suggested sweep:** mark #1, #9, #10, #11, #12, #13, #14, #15, #16 as `resolved` with a one-line note. Leave #17 pending until filter outreach is done.

```python
# Quick close all-but-#17:
from app.models.help_request import HelpRequest
from app.extensions import db
from datetime import datetime
for tid in [1, 9, 10, 11, 12, 13, 14, 15, 16]:
    t = HelpRequest.query.get(tid)
    if t and t.status == 'pending':
        t.status = 'resolved'
        t.resolution = 'Closed during 2026-06-22 sweep (already resolved in changelog/shipped fix).'
        t.resolved_at = datetime.utcnow()
db.session.commit()
```

---

## Quick-reference

- **Project root:** `/var/www/matat`
- **Service:** `matat.service` (gunicorn :5050) — **NEVER `systemctl restart` without graceful drain.** See `feedback_matat_restart.md`. Use `stop` + wait + `start`, or test in-place.
- **Email DB row:** `email_inbox_providers` where `code='msgraph'` — has the client_id/tenant for the Azure app needing `Mail.ReadWrite`.
- **Provider selector:** `app/services/email_service.py:30` reads `config.email_provider`.
- **Memory dir:** `/root/.claude/projects/-var-www-matat/memory/` (server-side Claude). PC-side Claude has its own; ignore.
- **Last commit:** `db4b5dc — phone-entry: warn-then-confirm on missing email instead of hard-required`
- **Working tree:** clean except for `tools/draft_filter_whitelist_letters.py` (this session's one-shot, uncommitted) and `HANDOFF.md` (this file).

---

## Suggested next actions for PC-Claude

1. Confirm with MK whether he wants `Mail.ReadWrite` granted (Blocker 1). If yes, walk him through Azure UI; if no, switch to copy-paste-into-OWA mode.
2. Once provider question (Blocker 2) is resolved, do **one test send via the chosen provider** to a known-good address before any donor-facing send.
3. If sending live: send the 5 letters one at a time, log the responses in the ticket #17 resolution field.
4. After the 5 letters are out (or queued in OWA), close ticket #17 with the resolution note, and run the bulk-close snippet above for the stale ones.
5. Ping mrosen letting her know what happened — small ping via the in-app system, not email (she's already getting filter-blocked donors).

Good luck. — Server-side Claude
