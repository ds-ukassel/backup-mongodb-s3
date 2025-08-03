#!/bin/sh

set -e

SCRIPT_NAME=backup-mongodb
ARCHIVE_NAME=mongodump_$(date +%Y%m%d_%H%M%S).gz
OPLOG_FLAG=""
MC_CMD="${MC_CMD:-mc}"
MC_CONF_DIR="/scripts"

export MC_HOST_backup=$S3_URI

if [ -n "$MONGODB_OPLOG" ]; then
        OPLOG_FLAG="--oplog"
fi

echo "[$SCRIPT_NAME] Creating Minio bucket if it does not exist: $S3_BUCKET"
$MC_CMD -C $MC_CONF_DIR mb -p backup/${S3_BUCKET} --insecure

echo "[$SCRIPT_NAME] Dumping all MongoDB databases to compressed archive and than sending to Minio object storage"

mongodump $OPLOG_FLAG \
        --archive \
        --gzip \
        --readPreference=$MONGODB_READ_PREFERENCE \
        --uri "$MONGODB_URI" | \
$MC_CMD -C $MC_CONF_DIR pipe "backup/$S3_BUCKET/$ARCHIVE_NAME" --insecure
echo "[$SCRIPT_NAME] Succsesfull uploading $ARCHIVE_NAME to $S3_BUCKET bucket"

echo "[$SCRIPT_NAME] Removing backups older than $RETENTION_PERIOD"
$MC_CMD -C $MC_CONF_DIR rm --recursive --older-than=${RETENTION_PERIOD} --force "backup/$S3_BUCKET" --insecure
