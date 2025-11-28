#!/bin/sh
set -e

# Required environment variables
: "${MONGODB_URI:?Missing MONGODB_URI}"
: "${MINIO_ENDPOINT:?Missing MINIO_ENDPOINT}"
: "${MINIO_ACCESS_KEY:?Missing MINIO_ACCESS_KEY}"
: "${MINIO_SECRET_KEY:?Missing MINIO_SECRET_KEY}"

# Optional variables with defaults
MINIO_BUCKET="${MINIO_BUCKET:-mongodb-backups}"
MINIO_PATH="${MINIO_PATH-mongodb-dumps}"
MONGODB_READ_PREFERENCE="${MONGODB_READ_PREFERENCE:-secondaryPreferred}"
RETENTION_PERIOD="${RETENTION_PERIOD:-}"
MINIO_COMMAND="${MINIO_COMMAND:-mc}"
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"

NOW=$(date +%Y%m%d_%H%M%S)

send_webhook_error() {
  if [ -n "$DISCORD_WEBHOOK_URL" ]; then
    echo "[mongodb-backup] Sending error notification to Discord webhook..."
    PAYLOAD="{\"content\": \"Backup of MongoDB databases at $NOW failed!\"}"
    curl -H "Content-Type: application/json" -X POST -d "$PAYLOAD" "$DISCORD_WEBHOOK_URL" || true
  fi
}

trap 'send_webhook_error' ERR

echo "[mongodb-backup] Starting backup of MongoDB at $NOW..."


echo "[mongodb-backup] Configuring MinIO connection and creating bucket..."
$MINIO_COMMAND alias set storage "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"
$MINIO_COMMAND mb -p "storage/$MINIO_BUCKET"

echo "[mongodb-backup] Compress databases and upload to MinIO..."

mongodump --archive --gzip --readPreference=$MONGODB_READ_PREFERENCE --uri "$MONGODB_URI" | \
$MINIO_COMMAND pipe "storage/$MINIO_BUCKET/$MINIO_PATH/mongodump_$NOW.gz"

echo "[mongodb-backup] Successfully uploaded mongodump_$NOW.gz to $MINIO_BUCKET bucket"

if [ -n "$RETENTION_PERIOD" ]; then
  echo "[mongodb-backup] Deleting backups older than $RETENTION_PERIOD from MinIO..."
  $MINIO_COMMAND rm --recursive --older-than "$RETENTION_PERIOD" --force "storage/$MINIO_BUCKET/$MINIO_PATH/"
fi

echo "[mongodb-backup] Backup process completed successfully!"
