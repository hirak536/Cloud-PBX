#!/usr/bin/env bash
# Backup the IHS-PBX Postgres database via pg_dump.
# Reads DB_* settings from the project .env by default.
#
# Usage:
#   ./backup-postgres-db.sh                 # default dest: /var/backups/postgres
#   ./backup-postgres-db.sh /path/to/dest
#
# Env overrides: ENV_FILE, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT,
#                RETENTION_DAYS (default 14).

set -euo pipefail

DEST="${1:-/var/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
ENV_FILE="${ENV_FILE:-/opt/IHS-PBX/.env}"

# Load DB_* from .env if present (without exporting everything blindly).
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC2046
  export $(grep -E '^(DB_NAME|DB_USER|DB_PASSWORD|DB_HOST|DB_PORT)=' "${ENV_FILE}" | xargs -d '\n')
fi

: "${DB_NAME:?DB_NAME not set}"
: "${DB_USER:?DB_USER not set}"
: "${DB_PASSWORD:?DB_PASSWORD not set}"
# Force IPv4 when DB_HOST is "localhost" to avoid ::1-vs-127.0.0.1 pg_hba mismatches.
if [[ "${DB_HOST:-}" = "localhost" ]]; then
  DB_HOST="127.0.0.1"
fi
: "${DB_HOST:?DB_HOST not set}"
: "${DB_PORT:=5432}"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${DEST}/${DB_NAME}-${STAMP}.dump"

mkdir -p "${DEST}"

echo "==> Dumping ${DB_NAME} from ${DB_HOST}:${DB_PORT} as ${DB_USER}"
PGPASSWORD="${DB_PASSWORD}" pg_dump \
  --host="${DB_HOST}" \
  --port="${DB_PORT}" \
  --username="${DB_USER}" \
  --dbname="${DB_NAME}" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file="${OUT}"

chmod 600 "${OUT}"

echo "==> Pruning dumps older than ${RETENTION_DAYS} days in ${DEST}"
find "${DEST}" -maxdepth 1 -name "${DB_NAME}-*.dump" -mtime "+${RETENTION_DAYS}" -delete

echo "==> Done: ${OUT}"
ls -lh "${OUT}"
