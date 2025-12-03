#!/bin/bash
set -eo pipefail

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
COLLECTIONS="${COLLECTIONS:-}"

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
if [ -z "$COLLECTIONS" ]; then
  echo "[mongodb-backup] No collections specified. Dumping entire MongoDB instance and uploading..."

  mongodump --archive --gzip --readPreference=$MONGODB_READ_PREFERENCE --uri "$MONGODB_URI" | \
  $MINIO_COMMAND pipe "storage/$MINIO_BUCKET/$MINIO_PATH/mongodump_$NOW.bson.gz"

  echo "[mongodb-backup] Successfully uploaded mongodump_$NOW.bson.gz to $MINIO_BUCKET bucket"
else
  echo "[mongodb-backup] Collection strategies specified. Dumping specified collections..."
  for DB_COLL_STRATEGY_FIELD in $COLLECTIONS; do
    [ -z "$DB_COLL_STRATEGY_FIELD" ] && continue # Skip empty entries

    # db.collection:STRATEGY:FIELD
    IFS=':' read -r DB_COLL STRATEGY FIELD <<< "$DB_COLL_STRATEGY_FIELD"

    if [ -z "$DB_COLL" ]; then
      echo "[mongodb-backup] Skipping invalid entry: '$DB_COLL_STRATEGY_FIELD' (missing db.collection)"
      continue
    fi

    DATABASE="${DB_COLL%%.*}" # remove everything after first .
    COLLECTION="${DB_COLL#*.}" # remove everything before first .
    STRATEGY="${STRATEGY:-FULL}"
    STRATEGY="${STRATEGY^^}" # uppercase
    FIELD="${FIELD:-_id}"

    echo "[mongodb-backup] Processing collection '$DATABASE.$COLLECTION' with strategy '$STRATEGY' on field '$FIELD'..."
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
