# Developer Handoff — 2026-04-22

**To Claude running on the developer's laptop.**
**You have no memory of the operator-PC conversation today.** Everything you need is here.

---

## Quick summary — what changed today

1. **Ticket #4 (operator feedback): `/gemach/members` search is now interactive.** All three חיפוש-dialog fields filter the grid live as the operator types — no Enter, no reload. Implemented by extracting the results block into a partial and swapping it on each keystroke.

2. **Test server stood up at `matat-server:/var/www/matat/test`.** Reachable only through an SSH tunnel (no public Caddy entry, no DNS). Runs in `SANDBOX_MODE=1` with a dedicated SQLite DB seeded from the operator PC. Port `127.0.0.1:5051`. Production is untouched.

3. **Tailscale mesh installed.** Operator PC and server address each other by name (`matat-operator-pc` / `matat-server`) under the tailnet `tcmatat@`. No port forwarding, no reverse tunnel.

4. **Git-based deploy loop.** A systemd timer on the server polls `origin/staging` every 60 s and fast-forwards the test working tree (with conditional `pip install` / `flask db upgrade`) + restarts `matat-test`. Push to `staging` = deploy. Cherry-picking to the operator PC is no longer needed for testing.

5. **Operator PC `sync_live_data.bat`** now ends with an `scp` that pushes the freshly-synced `instance/matat.db` to the test server and restarts `matat-test` so SQLAlchemy reopens the file. Fresh Access data lands on the test server automatically after each sync.

6. **Native-window launcher for the test server: `start_test.bat` + `desktop_test.py`.** Same pywebview look as the current `start.bat`, but pointed at the SSH-tunneled test server instead of a local Flask. The operator PC is no longer tied up during testing.

---

## Branches pushed to `origin`

| Branch                             | Head      | What's on it                                                                                     |
|------------------------------------|-----------|--------------------------------------------------------------------------------------------------|
| `fix/interactive-members-search`   | `5490597` | Ticket #4 fix, cleanly branched off master. **Intended PR target: master.**                      |
| `staging`                          | `6a0cc83` | Ticket #4 fix + `tools/deploy_staging.sh` + `tools/staging/` systemd units + README             |
| `operator-feedback-widget`         | `1abbe1d` | Ticket #4 fix (cherry-picked) + `sync_live_data.bat` scp push + `start_test.bat`/`desktop_test.py` + Changelog |
| `master`                           | `3874401` | Unchanged today                                                                                  |

Commit lineage on `operator-feedback-widget`:
```
1abbe1d  Add start_test.bat + desktop_test.py
df05700  sync_live_data.bat: auto-push SQLite to test server
93a357a  Ticket 4: interactive /gemach/members search   (cherry-picked from fix/)
3874401  Loan detail: faithful Access hork-edit reproduction   (= master)
```

---

## Safety analysis

**Prod (`matatmordechai.org`, `/var/www/matat`, `matat.service`) is untouched.**
- No files modified under `/var/www/matat/`.
- No changes to `matat.service`, Caddy config, or any prod systemd unit.
- No prod database reads or writes.
- The only shared resource is the DO droplet itself; test uses port 5051 (prod uses 5050), its own venv, its own `.env`.

**Tailscale** runs as a system service on both the PC and the server. It listens only on its own WireGuard interface (100.x addresses) — no public exposure. Removing it is `tailscale down; apt remove tailscale` on the server, uninstall via Add/Remove on Windows.

**The staging deploy script uses `git reset --hard origin/staging`**, which will clobber uncommitted local changes in `/var/www/matat/test`. A Claude running on the server during heavy editing should `systemctl stop matat-test-deploy.timer` while working and re-enable when done. Documented in `tools/staging/README.md` and the server-Claude handoff prompt.

**SSH access:** The operator PC has a key authorized for `root@178.128.83.220` (used by the install flow today). No new keys were added server-side.

---

## What you (dev-laptop Claude) should do

### Step 1 — Decide the merge path for ticket #4

Three branches contain the ticket-#4 fix. Recommended disposition:
- **Merge `fix/interactive-members-search` → `master`** (clean, one commit, ready for PR).
- Leave `staging` as-is — it'll stay ahead of master until you merge the fix, at which point the next `staging` rebase/reset brings them back in sync.
- `operator-feedback-widget` stays as the operator-PC-specific branch; those commits (`sync_live_data.bat`, `start_test.bat`, `desktop_test.py`, `_developer_handoff_2026-04-22.md`) are operator-PC concerns and should **not** be merged to master — they belong on that branch only.

### Step 2 — Deploy the test server docs to master (optional but recommended)

`tools/staging/` + `tools/deploy_staging.sh` + the corresponding CLAUDE.md Changelog entry currently live only on `staging`. Consider cherry-picking commit `6a0cc83` onto master too, so the infra is versioned on the trunk. The systemd units are harmless on master (nothing runs them outside the test server).

### Step 3 — Your new testing workflow

1. Make changes in a feature branch off `master`.
2. Merge into `staging` and push.
3. Wait ~60 s → test server pulls and restarts.
4. Operator (or you) tests via `start_test.bat` on the operator PC (native window, no browser tab) or `ssh -L 8080:127.0.0.1:5051 root@matat-server` on any machine.
5. When happy, open a PR `feature → master`.

**You no longer need to cherry-pick onto `operator-feedback-widget` to test.** That was the old loop; it's retired.

---

## Known placeholders / things deliberately not done

- **No public `test.matatmordechai.org` DNS entry.** Access is SSH-tunnel-only by design (user asked for option #1). Flipping to public + HTTP Basic Auth later is a ~10-line Caddyfile change.
- **No Claude Code installed on the test server yet.** If the user wants a server-side Claude like prod has, the install is `curl -fsSL https://claude.ai/install.sh | bash` + a git identity. Prompt for it is already drafted (in the operator-PC session transcript).
- **`sync_live_data.bat` has to be run for the scp to fire.** A Windows Scheduled Task running it every N minutes/hours would make the test DB self-refreshing; not set up yet.
- **The deploy timer uses `git reset --hard`.** Intentional (test server should track origin/staging precisely), but worth remembering when editing on the server directly.

---

## Files of note

- `tools/staging/README.md` — full server-setup doc (on `staging` branch)
- `tools/deploy_staging.sh` — the 60 s deploy script
- `CLAUDE.md` (`operator-feedback-widget` branch) — today's Changelog entry has the narrative
- `start_test.bat` / `desktop_test.py` — operator-facing test launcher
