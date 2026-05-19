#!/usr/bin/env bash
# Backup FreeSWITCH databases (SQLite) + key config.
# Run on the FreeSWITCH host (Linux), as root or via sudo.
#
# Usage:
#   sudo ./backup-freeswitch-db.sh                  # default dest: /var/backups/freeswitch
#   sudo ./backup-freeswitch-db.sh /path/to/dest
#
# Keeps the last RETENTION_DAYS days of backups (default 14).

set -euo pipefail

DEST="${1:-/var/backups/freeswitch}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
FS_DB_DIR="${FS_DB_DIR:-/var/lib/freeswitch/db}"
FS_CONF_DIR="${FS_CONF_DIR:-/etc/freeswitch}"
FS_STORAGE_DIR="${FS_STORAGE_DIR:-/var/lib/freeswitch/storage}"

STAMP="$(date +%Y%m%d-%H%M%S)"
WORK="$(mktemp -d)"
OUT="${DEST}/freeswitch-backup-${STAMP}.tar.gz"

mkdir -p "${DEST}"
mkdir -p "${WORK}/db"

echo "==> Backing up FreeSWITCH SQLite DBs from ${FS_DB_DIR}"
if [[ -d "${FS_DB_DIR}" ]]; then
  shopt -s nullglob
  for db in "${FS_DB_DIR}"/*.db; do
    name="$(basename "${db}")"
    echo "    - ${name}"
    # Use sqlite3 .backup for a consistent online snapshot if available;
    # otherwise fall back to a plain copy.
    if command -v sqlite3 >/dev/null 2>&1; then
      sqlite3 "${db}" ".backup '${WORK}/db/${name}'"
    else
      cp -a "${db}" "${WORK}/db/${name}"
    fi
  done
  shopt -u nullglob
else
  echo "    (skipped, ${FS_DB_DIR} not found)"
fi

echo "==> Including FreeSWITCH config (${FS_CONF_DIR})"
if [[ -d "${FS_CONF_DIR}" ]]; then
  cp -a "${FS_CONF_DIR}" "${WORK}/etc-freeswitch"
fi

echo "==> Including voicemail storage metadata"
if [[ -d "${FS_STORAGE_DIR}/voicemail" ]]; then
  # Voicemail .wav files can be huge; back up only the index/metadata by default.
  # Set INCLUDE_VOICEMAIL_AUDIO=1 to include audio files too.
  if [[ "${INCLUDE_VOICEMAIL_AUDIO:-0}" = "1" ]]; then
    cp -a "${FS_STORAGE_DIR}/voicemail" "${WORK}/voicemail"
  else
    mkdir -p "${WORK}/voicemail"
    (cd "${FS_STORAGE_DIR}" && find voicemail -type f ! -name '*.wav' ! -name '*.mp3' -print0 \
      | xargs -0 -I{} cp --parents "{}" "${WORK}/") || true
  fi
fi

echo "==> Creating archive ${OUT}"
tar -czf "${OUT}" -C "${WORK}" .
chmod 600 "${OUT}"
rm -rf "${WORK}"

echo "==> Pruning backups older than ${RETENTION_DAYS} days in ${DEST}"
find "${DEST}" -maxdepth 1 -name 'freeswitch-backup-*.tar.gz' -mtime "+${RETENTION_DAYS}" -delete

echo "==> Done: ${OUT}"
ls -lh "${OUT}"
