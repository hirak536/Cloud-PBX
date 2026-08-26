#!/usr/bin/env bash
#
# cloudpbx-db-backup.sh — Daily PostgreSQL backup for Cloud PBX
#
# Dumps both databases with pg_dump -F c --create --clean, timestamped
# MM-DD-YYYY_HH-MM-SS.dump, to the Windows SMB share, and prunes dumps older
# than 30 days. The share is mounted at backup time and unmounted at the end.
#
#   main DB (cloudpbx)     -> \\172.30.109.52\PBXBackups\PBXDevDBBackup\fs1\main
#   cdr  DB (cloudpbx_cdr) -> \\172.30.109.52\PBXBackups\PBXDevDBBackup\fs1\cdr
#
# Scheduled twice daily by cloudpbx-db-backup.timer (11:00 & 04:00 UTC).
set -euo pipefail

# ---- configuration ---------------------------------------------------------
SMB_SHARE='//172.30.109.52/PBXBackups'
SMB_CREDS='/etc/cloudpbx-backup.smbcreds'
MOUNT_POINT='/mnt/pbxbackups'
BACKUP_SUBDIR='PBXDevDBBackup/fs1'          # main/ and cdr/ live under here
RETENTION_DAYS=30

ENV_FILE='/opt/Cloud-PBX/.env'
# Force IPv4: DB_HOST=localhost resolves to ::1 first, which pg_hba often
# rejects even when 127.0.0.1 is trusted.
PGHOST='127.0.0.1'
PGPORT='5432'

# Databases to back up: "<dbname>:<subdir-under-fs1>"
DATABASES=(
  "cloudpbx:main"
  "cloudpbx_cdr:cdr"
)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { log "ERROR: $*" >&2; exit 1; }

# ---- load DB credentials from the app .env --------------------------------
[ -r "$ENV_FILE" ] || fail "Cannot read $ENV_FILE for DB credentials."
# Strip trailing CR and surrounding single/double quotes (decouple does this
# for the app; we must match it here).
strip_env() {
  local v; v="$(grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '\r')"
  v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
  printf '%s' "$v"
}
PGUSER="$(strip_env DB_USER)"
PGPASSWORD="$(strip_env DB_PASSWORD)"
[ -n "$PGUSER" ] && [ -n "$PGPASSWORD" ] || fail "DB_USER/DB_PASSWORD not found in $ENV_FILE."
export PGPASSWORD

# ---- mount the SMB share ---------------------------------------------------
cleanup() {
  if mountpoint -q "$MOUNT_POINT"; then
    umount "$MOUNT_POINT" && log "Unmounted $MOUNT_POINT" || log "WARN: umount failed."
  fi
}
trap cleanup EXIT

mkdir -p "$MOUNT_POINT"
if mountpoint -q "$MOUNT_POINT"; then
  log "Share already mounted at $MOUNT_POINT."
else
  log "Mounting $SMB_SHARE at $MOUNT_POINT..."
  mount -t cifs "$SMB_SHARE" "$MOUNT_POINT" \
    -o "credentials=$SMB_CREDS,vers=3.0,uid=0,gid=0,file_mode=0640,dir_mode=0750" \
    || fail "Failed to mount SMB share $SMB_SHARE."
  log "Mounted."
fi

# ---- back up each database -------------------------------------------------
timestamp="$(date '+%m-%d-%Y_%H-%M-%S')"
overall_ok=1

for entry in "${DATABASES[@]}"; do
  db="${entry%%:*}"
  sub="${entry##*:}"
  dest_dir="$MOUNT_POINT/$BACKUP_SUBDIR/$sub"
  mkdir -p "$dest_dir"
  outfile="$dest_dir/${db}_backup_${timestamp}.dump"

  log "Backing up '$db' -> $outfile"
  if pg_dump --create --clean -F c \
       -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$db" -f "$outfile"; then
    if [ -s "$outfile" ]; then
      log "OK: $db ($(du -h "$outfile" | cut -f1))"
    else
      log "ERROR: $db dump file empty."; overall_ok=0
    fi
  else
    log "ERROR: pg_dump failed for $db."; overall_ok=0
  fi

  # ---- retention: prune dumps older than RETENTION_DAYS --------------------
  log "Pruning '$sub' dumps older than $RETENTION_DAYS days..."
  find "$dest_dir" -maxdepth 1 -type f -name '*.dump' -mtime +"$RETENTION_DAYS" \
    -print -delete || log "WARN: prune failed for $sub."
done

[ "$overall_ok" -eq 1 ] || fail "One or more database backups failed."
log "All backups completed successfully."
