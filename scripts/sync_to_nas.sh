#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# G12-next: Project DNA Data Sync → NAS Mirror
# ───────────────────────────────────────────────────────────────
# Syncs:
#   1. PostgreSQL   → pg_dump (gzip) → rsync → NAS (keep 7 last)
#   2. Qdrant       → HTTP snapshot → rsync → NAS
#   3. MinIO        → mc mirror (HTTP-to-HTTP, no rsync)
#
# Requires in deploy/.env:
#   NAS_HOST, NAS_USER, NAS_SSH_PASS
#   PG_USER, PG_PASSWORD
#   MINIO_USER, MINIO_PASSWORD
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ── Paths ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../deploy/.env"
LOG_DIR="$SCRIPT_DIR/../logs"
LOG_FILE="$LOG_DIR/sync_$(date +%Y%m%d).log"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
TMP_DIR="/tmp/dna_sync_$TIMESTAMP"

# ── Load .env (skip comments and empty lines) ───────────────────
set -a
# shellcheck disable=SC1090
source <(grep -v '^#' "$ENV_FILE" | grep -v '^[[:space:]]*$')
set +a

# ── Config (overridable via env) ────────────────────────────────
NAS_HOST="${NAS_HOST:-172.25.9.147}"
NAS_USER="${NAS_USER:-adminDS}"
NAS_BACKUP="/volume1/docker/project_dna_sync"
QDRANT_URL="http://localhost:6333"
QDRANT_COLLECTIONS=("project_prompts" "test_collection")
PG_CONTAINER="ai-postgres"
PG_DB="project_dna"
KEEP_BACKUPS=7    # сколько pg_dump файлов хранить на NAS

# ── Init ────────────────────────────────────────────────────────
mkdir -p "$LOG_DIR" "$TMP_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

log()     { echo "[$(date +%H:%M:%S)] $1"; }
log_ok()  { echo "[$(date +%H:%M:%S)] ✅ $1"; }
log_warn(){ echo "[$(date +%H:%M:%S)] ⚠️  $1"; }
log_err() { echo "[$(date +%H:%M:%S)] ❌ $1"; }

# rsync helper: local file → NAS path
nas_rsync() {
    sshpass -p "$NAS_SSH_PASS" rsync -avz --progress \
        "$1" "$NAS_USER@$NAS_HOST:$2"
}

# ssh helper: command on NAS
nas_ssh() {
    sshpass -p "$NAS_SSH_PASS" ssh "$NAS_USER@$NAS_HOST" "$@"
}

# ────────────────────────────────────────────────────────────────
# 1. PostgreSQL
# ────────────────────────────────────────────────────────────────
sync_postgres() {
    log "📊 PostgreSQL backup..."
    local dump="$TMP_DIR/${PG_DB}_${TIMESTAMP}.sql.gz"

    # Dump inside container, compress on the fly
    docker exec \
        -e PGPASSWORD="$PG_PASSWORD" \
        "$PG_CONTAINER" \
        pg_dump -U "$PG_USER" "$PG_DB" | gzip > "$dump"

    nas_rsync "$dump" "$NAS_BACKUP/postgres/"

    # Rotate: keep only last N dumps on NAS
    nas_ssh "ls -t $NAS_BACKUP/postgres/*.sql.gz 2>/dev/null \
        | tail -n +$((KEEP_BACKUPS + 1)) | xargs rm -f 2>/dev/null; \
        echo 'kept $(ls $NAS_BACKUP/postgres/*.sql.gz | wc -l) backups'"

    log_ok "PostgreSQL: $(du -sh "$dump" | cut -f1) synced to NAS"
}

# ────────────────────────────────────────────────────────────────
# 2. Qdrant
# ────────────────────────────────────────────────────────────────
sync_qdrant() {
    log "🔍 Qdrant snapshots..."

    for COLLECTION in "${QDRANT_COLLECTIONS[@]}"; do
        log "  📸 $COLLECTION..."

        # Create snapshot via API
        SNAP_NAME=$(curl -sf -X POST \
            "$QDRANT_URL/collections/$COLLECTION/snapshots" | \
            python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d.get('result',{}).get('name',''))
" 2>/dev/null || echo "")

        if [ -z "$SNAP_NAME" ]; then
            log_warn "$COLLECTION: snapshot failed, skipping"
            continue
        fi

        # Download snapshot file
        local snap_file="$TMP_DIR/${COLLECTION}.snapshot"
        curl -sf "$QDRANT_URL/collections/$COLLECTION/snapshots/$SNAP_NAME" \
            -o "$snap_file"

        nas_rsync "$snap_file" "$NAS_BACKUP/qdrant/"

        # Cleanup snapshot from Qdrant (free space)
        curl -sf -X DELETE \
            "$QDRANT_URL/collections/$COLLECTION/snapshots/$SNAP_NAME" \
            > /dev/null || true

        log_ok "$COLLECTION: $(du -sh "$snap_file" | cut -f1) synced"
    done
}

# ────────────────────────────────────────────────────────────────
# 3. MinIO
# ────────────────────────────────────────────────────────────────
sync_minio() {
    log "📦 MinIO mirror (HTTP→HTTP)..."

    # Зеркалим каждый bucket: создаём на NAS если нет, затем mirror
    for BUCKET in $(mc ls local/ 2>/dev/null | awk '{print $NF}' | tr -d '/'); do
        log "  🪣  $BUCKET..."
        mc mb --ignore-existing "nas/$BUCKET" 2>/dev/null || true
        mc mirror --overwrite "local/$BUCKET" "nas/$BUCKET" 2>&1 | \
            grep -vE "^$|Calculating" || true
        log_ok "$BUCKET mirrored"
    done
}

# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────
log "═══════════════════════════════════════════════════"
log "🚀 G12-next Sync Start: $TIMESTAMP"
log "   NAS: $NAS_USER@$NAS_HOST:$NAS_BACKUP"
log "═══════════════════════════════════════════════════"

ERRORS=0

sync_postgres  || { log_err "PostgreSQL sync FAILED"; ERRORS=$((ERRORS+1)); }
sync_qdrant    || { log_err "Qdrant sync FAILED";     ERRORS=$((ERRORS+1)); }
sync_minio     || { log_err "MinIO sync FAILED";      ERRORS=$((ERRORS+1)); }

# Cleanup tmp
rm -rf "$TMP_DIR"

log "═══════════════════════════════════════════════════"
if [ "$ERRORS" -eq 0 ]; then
    log_ok "All synced! Log: $LOG_FILE"
else
    log_err "$ERRORS component(s) failed. Check $LOG_FILE"
    exit 1
fi
log "═══════════════════════════════════════════════════"
