#!/bin/bash
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
COLLECTION_STRATEGIES="${COLLECTION_STRATEGIES:-}"
STRATEGY_ID="${STRATEGY_ID:-_id}"

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

# If no collection strategies are specified, dump the whole instance
if [ -z "$COLLECTION_STRATEGIES" ]; then
  echo "[mongodb-backup] No collection strategies specified. Dumping entire MongoDB instance and uploading..."

  mongodump --archive --gzip --readPreference=$MONGODB_READ_PREFERENCE --uri "$MONGODB_URI" | \
  $MINIO_COMMAND pipe "storage/$MINIO_BUCKET/$MINIO_PATH/mongodump_$NOW.bson.gz"

  echo "[mongodb-backup] Successfully uploaded mongodump_$NOW.bson.gz to $MINIO_BUCKET bucket"
else
  echo "[mongodb-backup] Collection strategies specified. Dumping specified collections..."
  for COLLECTION_STRATEGY in $COLLECTION_STRATEGIES; do
    [ -z "$COLLECTION_STRATEGY" ] && continue # Skip empty entries

    # db.coll.ection=strategy
    STRATEGY="${COLLECTION_STRATEGY#*=}" # Remove everything before =
    DATABASE_COLLECTION="${COLLECTION_STRATEGY%%=*}" # Remove everything after =
    DATABASE="${DATABASE_COLLECTION%%.*}" # Remove everything after first .
    COLLECTION="${DATABASE_COLLECTION#*.}" # Remove everything before first .

    echo "[mongodb-backup] Processing collection '$DATABASE.$COLLECTION' with strategy '$STRATEGY'..."
    if [ "${STRATEGY^^}" != "FULL" ]; then
      QUERY=$(python3 /usr/local/bin/query-generator.py "$STRATEGY" "$STRATEGY_ID")
    else
      QUERY=""
    fi

    mongodump --archive --gzip --readPreference=$MONGODB_READ_PREFERENCE --uri "$MONGODB_URI" --db "$DATABASE" --collection "$COLLECTION" --query "$QUERY" | \
    $MINIO_COMMAND pipe "storage/$MINIO_BUCKET/$MINIO_PATH/${COLLECTION}_$NOW.bson.gz"
  done
fi

if [ -n "$RETENTION_PERIOD" ]; then
  echo "[mongodb-backup] Deleting backups older than $RETENTION_PERIOD from MinIO..."
  $MINIO_COMMAND rm --recursive --older-than "$RETENTION_PERIOD" --force "storage/$MINIO_BUCKET/$MINIO_PATH/"
fi

echo "[mongodb-backup] Backup process completed successfully!"
