#!/bin/bash
# Matat Mordechai nightly backup.
# - Full mysqldump of the matat database (gzip'd)
# - Tarball of uploads/ + instance/ (user-uploaded files)
# Both go to /var/backups/matat/. Rotation: keep 14 daily + 4 weekly.
# Wired via cron at 03:00 UTC daily.

set -euo pipefail

BACKUP_DIR=/var/backups/matat
TS=$(date +%Y%m%d-%H%M%S)
DOW=$(date +%u)  # 1-7, 7=Sun
LOG=/var/log/matat-backup.log

# Read DB password from the live .env (single source of truth).
# Matches lines like: DATABASE_URL=mysql+pymysql://root:THEPASSWORD@localhost:3306/matat
DB_USER=$(grep '^DATABASE_URL=' /var/www/matat/.env | sed -E 's|^DATABASE_URL=[^:]+://([^:]+):.*|\1|')
DB_PASS=$(grep '^DATABASE_URL=' /var/www/matat/.env | sed -E 's|^DATABASE_URL=[^:]+://[^:]+:([^@]+)@.*|\1|')
DB_NAME=$(grep '^DATABASE_URL=' /var/www/matat/.env | sed -E 's|^.*/([^?]+).*|\1|')

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

{
  echo "[$(date -Iseconds)] === Matat backup starting ==="

  # 1. Database dump
  DB_FILE="$BACKUP_DIR/db-${TS}.sql.gz"
  echo "[$(date -Iseconds)] mysqldump -> $DB_FILE"
  mysqldump --user="$DB_USER" --password="$DB_PASS" \
            --single-transaction --quick --triggers --routines --events \
            "$DB_NAME" | gzip > "$DB_FILE"
  DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
  echo "[$(date -Iseconds)] DB dump done — $DB_SIZE"

  # 2. User-uploaded files
  FILES_FILE="$BACKUP_DIR/files-${TS}.tar.gz"
  echo "[$(date -Iseconds)] tar -> $FILES_FILE"
  tar --exclude='instance/feedback_git' \
      --exclude='*.pyc' --exclude='__pycache__' \
      -czf "$FILES_FILE" \
      -C /var/www/matat uploads instance
  FILES_SIZE=$(du -h "$FILES_FILE" | cut -f1)
  echo "[$(date -Iseconds)] file tarball done — $FILES_SIZE"

  # 3. Weekly snapshot — pin Sunday's backup so we have month-old history
  if [ "$DOW" = "7" ]; then
    cp "$DB_FILE"    "${DB_FILE%.sql.gz}-weekly.sql.gz"
    cp "$FILES_FILE" "${FILES_FILE%.tar.gz}-weekly.tar.gz"
    echo "[$(date -Iseconds)] Sunday — weekly snapshots pinned"
  fi

  # 4. Rotation: keep 14 daily + 4 weekly. Delete anything older.
  #    Weekly files have "-weekly" in the name; daily files don't.
  find "$BACKUP_DIR" -maxdepth 1 -type f -name 'db-*.sql.gz'    ! -name '*-weekly.sql.gz'    -mtime +14 -delete
  find "$BACKUP_DIR" -maxdepth 1 -type f -name 'files-*.tar.gz' ! -name '*-weekly.tar.gz'   -mtime +14 -delete
  find "$BACKUP_DIR" -maxdepth 1 -type f -name '*-weekly.sql.gz'  -mtime +28 -delete
  find "$BACKUP_DIR" -maxdepth 1 -type f -name '*-weekly.tar.gz' -mtime +28 -delete

  KEPT=$(ls -1 "$BACKUP_DIR" 2>/dev/null | wc -l)
  echo "[$(date -Iseconds)] Rotation done — $KEPT files kept"
  echo "[$(date -Iseconds)] === Matat backup complete ==="
  echo
} >> "$LOG" 2>&1
