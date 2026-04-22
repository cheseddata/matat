# Matat TEST server — setup & deploy

The test server lives on the same DigitalOcean droplet as production, at
`/var/www/matat/test`, and is reachable **only** through an SSH tunnel
(no public Caddy entry). SANDBOX mode is permanently on, so every outbound
API call (payments, email, SMS) is short-circuited.

## How you reach it

From any machine on the Tailscale net with an SSH key on the server:

    ssh -L 8080:127.0.0.1:5051 root@matat-server

Open <http://localhost:8080> in a browser. The first page redirects via
`/sandbox-login` → Hebrew Gemach switchboard, the same landing as the
operator PC.

## Services

| Unit                         | Purpose                                           |
|------------------------------|---------------------------------------------------|
| `matat-test.service`         | Gunicorn on `127.0.0.1:5051`, 2 workers           |
| `matat-test-deploy.service`  | Oneshot: `git fetch origin staging` + restart     |
| `matat-test-deploy.timer`    | Fires the deploy service every 60 s               |

Inspect:

    systemctl status matat-test matat-test-deploy.timer
    journalctl -u matat-test -f
    journalctl -u matat-test-deploy -n 50

## How deploys happen

1. Push to branch `staging` on GitHub from anywhere.
2. Within ~60 s the server's timer runs `tools/deploy_staging.sh`, which:
   - Fast-forwards to `origin/staging`
   - Runs `pip install -r requirements.txt` if that file changed
   - Runs `flask db upgrade` if `migrations/` changed
   - Restarts `matat-test`
3. Refresh your browser — change is live.

No cherry-picking, no SSH, no operator PC involvement.

## How fresh data lands

`sync_live_data.bat` on the operator PC ends with an `scp` that pushes
the synced `instance/matat.db` to the test server via Tailscale, then
restarts `matat-test` so SQLAlchemy reopens the file.

On-demand refresh from anywhere with the SSH key:

    ssh root@matat-operator-pc 'C:/matat/sync_live_data.bat'

(requires OpenSSH server on the operator PC — not installed yet; for now
run the `.bat` directly on the PC or on a Windows Scheduled Task).

## One-time server setup (already done)

    cd /var/www/matat
    git clone -b staging git@github.com:cheseddata/matat.git test
    cd test
    python3 -m venv venv
    venv/bin/pip install -r requirements.txt gunicorn
    # write .env with SANDBOX_MODE=1, DATABASE_URL=sqlite:///..., fresh SECRET_KEY
    cp tools/staging/matat-test.service         /etc/systemd/system/
    cp tools/staging/matat-test-deploy.service  /etc/systemd/system/
    cp tools/staging/matat-test-deploy.timer    /etc/systemd/system/
    chmod +x tools/deploy_staging.sh
    systemctl daemon-reload
    systemctl enable --now matat-test matat-test-deploy.timer
