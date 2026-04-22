#!/usr/bin/env bash
# Auto-deploy /var/www/matat/test from origin/staging.
#
# Called on a 60-second systemd timer (matat-test-deploy.timer). Idempotent:
# exits fast when HEAD already matches origin/staging. On a new commit it
# fast-forwards, optionally pip-installs / alembic-upgrades, and restarts
# matat-test.
#
# Test-server only. Never run on prod.

set -euo pipefail

REPO=/var/www/matat/test
cd "$REPO"

OLD=$(git rev-parse HEAD)
git fetch origin staging --quiet
NEW=$(git rev-parse origin/staging)

if [[ "$OLD" == "$NEW" ]]; then
    exit 0
fi

echo "[$(date -Iseconds)] Deploying ${OLD:0:7} -> ${NEW:0:7}"
git reset --hard origin/staging --quiet

CHANGED=$(git diff --name-only "$OLD" "$NEW")

if echo "$CHANGED" | grep -qx "requirements.txt"; then
    echo "  requirements.txt changed — pip install"
    venv/bin/pip install -r requirements.txt --quiet
fi

if echo "$CHANGED" | grep -q "^migrations/"; then
    echo "  migrations/ changed — flask db upgrade"
    venv/bin/flask db upgrade 2>&1 || echo "  (migration noop or failed — check manually)"
fi

systemctl restart matat-test
echo "[$(date -Iseconds)] Deploy complete (matat-test restarted)."
