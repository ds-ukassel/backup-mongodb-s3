import datetime
import json
import sys
from typing import cast

import yaml
from bson import json_util
from minio import Minio
from pymongo import MongoClient
from timedeltaparse import timedeltaparse

from backup_mongodb_s3 import config, utils
from backup_mongodb_s3.mongodump import mongodump_to_minio_stream
from backup_mongodb_s3.query_generator import strategy_to_query, Strategy, TimeStampFormat


def extract_settings(entry: str | dict[str, str]) -> tuple[str, str, str, str, str]:
    if isinstance(entry, str):
        entry = {"database": entry}

    database = entry.get("database", "")
    collection = entry.get("collection", "")
    strategy = entry.get("strategy", "FULL").upper()
    ts_column = entry.get("ts_column", "_id")
    ts_format = entry.get("ts_format", "OID").upper()

    return database, collection, strategy, ts_column, ts_format


def check_entries(mongo: MongoClient, entries: list[str | dict[str, str]]) -> bool:
    for entry in entries:

        # Check if collection is string or settings object
        if not isinstance(entry, (str, dict)):
            print(f"[mongodb-backup] Invalid backup entry (not an object or database name): {entry}", file=sys.stderr)
            return False

        # Check if dictionary only contains string values
        if isinstance(entry, dict) and not all(isinstance(value, str) for value in entry.values()):
            print(f"[mongodb-backup] Invalid entry (all settings must be strings): {entry}", file=sys.stderr)
            return False

        database, collection, strategy, ts_column, ts_format = extract_settings(entry)

        # Check if database is valid and exists
        if not database or not utils.is_identifier(database):
            print(f"[mongodb-backup] Invalid entry (missing/invalid database name): {entry}", file=sys.stderr)
            return False

        if not utils.database_exists(mongo, database):
            print(f"[mongodb-backup] Database '{database}' does not exist.", file=sys.stderr)
            return False

        # Check if collection is valid and exists
        if collection and not utils.is_identifier(collection):
            print(f"[mongodb-backup] Invalid backup entry (missing/invalid collection name): {entry}", file=sys.stderr)
            return False

        if collection and not utils.collection_exists(mongo, database, collection):
            print(f"[mongodb-backup] Collection '{database}.{collection}' does not exist.", file=sys.stderr)
            return False

        # Check if strategy is valid
        if strategy not in ("FULL", "DAY", "WEEK", "MONTH"):
            print(f"[mongodb-backup] Unsupported strategy '{strategy}': {entry}", file=sys.stderr)
            return False

        if not collection and (ts_column != "_id" or ts_format != "OID" or strategy != "FULL"):
            print(f"[mongodb-backup] If you specify a database without a collection, you cannot specify 'ts_column', 'ts_format', or a strategy other than 'FULL': {entry}", file=sys.stderr)
            return False

        # Check if settings are valid for strategy
        if strategy != "FULL" and (not ts_column or not ts_format):
            print(f"[mongodb-backup] For strategy {strategy} you must specify 'ts_column' and 'ts_format'.", file=sys.stderr)
            return False

        if ts_column and not utils.is_identifier(ts_column):
            print(f"[mongodb-backup] Invalid timestamp column '{ts_column}' for collection '{collection}'.", file=sys.stderr)
            return False

        if ts_format and ts_format not in ("OID", "EPOCH", "DT"):
            print(f"[mongodb-backup] Unsupported timestamp format '{ts_format}' for entry: {entry}", file=sys.stderr)
            return False

    return True


def main() -> None:
    try:
        # Check if required config options are set
        if not all([config.MINIO_ENDPOINT, config.MINIO_ACCESS_KEY, config.MINIO_SECRET_KEY, config.MINIO_BUCKET]):
            print("[mongodb-backup] Incomplete MinIO configuration. Check your environment variables.", file=sys.stderr)
            utils.webhook("Backup process failed due to incomplete MinIO configuration.")
            sys.exit(1)

        if not all([config.MONGODB_URL, config.MONGODB_READ_PREFERENCE]):
            print("[mongodb-backup] Incomplete MongoDB configuration. Check your environment variables.", file=sys.stderr)
            utils.webhook("Backup process failed due to incomplete MongoDB configuration.")
            sys.exit(1)

        if not config.MONGODB_COLLECTIONS.strip():
            print("[mongodb-backup] No databases/collections specified for backup.", file=sys.stderr)
            utils.webhook("Backup process stopped due to missing collections configuration.")
            sys.exit(0)

        # Create Minio Client
        try:
            minio: Minio = Minio(
                endpoint=config.MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
                access_key=config.MINIO_ACCESS_KEY,
                secret_key=config.MINIO_SECRET_KEY,
                secure=config.MINIO_SECURE
            )
        except Exception as e:
            print(f"[mongodb-backup] Failed to create MinIO client. Check your MinIO configuration: {e}", file=sys.stderr)
            utils.webhook("Backup process failed due to invalid MinIO configuration.")
            sys.exit(1)

        # Create MongoDB client
        try:
            mongo = MongoClient(config.MONGODB_URL)
        except Exception as e:
            print(f"[mongodb-backup] Failed to connect to MongoDB. Check your MongoDB configuration: {e}", file=sys.stderr)
            utils.webhook("Backup process failed due to invalid MongoDB configuration.")
            sys.exit(1)

        # Create bucket if it doesn't exist
        try:
            if not minio.bucket_exists(config.MINIO_BUCKET):
                minio.make_bucket(config.MINIO_BUCKET)
        except Exception as e:
            print(f"[mongodb-backup] Failed to access or create MinIO bucket '{config.MINIO_BUCKET}': {e}", file=sys.stderr)
            utils.webhook("Backup process failed due to MinIO bucket access issues.")
            sys.exit(1)

        # Load collection configuration
        try:
            entries = yaml.safe_load(config.MONGODB_COLLECTIONS)
            if not isinstance(entries, list):
                raise ValueError("Must be a YAML array of collection entries.")
        except Exception as e:
            print(f"[mongodb-backup] Failed to parse collections: {e}", file=sys.stderr)
            utils.webhook("Backup process failed due to invalid collection configuration.")
            sys.exit(1)

        # Check if collections are valid and exist
        if not check_entries(mongo, entries):
            utils.webhook("Backup process failed due to invalid collection configuration.") # Webhook is enough, prints are done in check_entries
            sys.exit(1)

        # Go through all entries
        for entry in entries:

            # Get settings from entry
            database, collection, strategy, ts_column, ts_format = extract_settings(entry)

            # Generate query (at this point, the settings are checked, so we can cast without issues)
            filename, bounds = strategy_to_query(cast(Strategy, strategy), database, collection, ts_column, cast(TimeStampFormat, ts_format))

            # Execute backup
            backup_name = f"{database}.{collection}" if collection else database
            print(f"[mongodb-backup] Executing backup for {backup_name} with strategy '{strategy}'...")
            try:
                mongodump_to_minio_stream(
                    minio_client=minio,
                    minio_bucket=config.MINIO_BUCKET,
                    minio_file_name=f"{config.MINIO_PATH}/{filename}",
                    mongo_uri=config.MONGODB_URL,
                    mongo_database=database,
                    mongo_collection=collection if collection else None,
                    mongo_query=json.dumps(bounds, default=json_util.default) if bounds else None
                )
                print(f"[mongodb-backup] Backup for '{backup_name}' completed successfully.")
            except Exception as e:
                print(f"[mongodb-backup] Backup for collection '{backup_name}' failed with error: {e}", file=sys.stderr)
                utils.webhook(f"Backup of MongoDB collection `{backup_name}` failed.")
                sys.exit(1)

        if config.RETENTION_PERIOD.strip():
            try:
                retention_date = datetime.datetime.now(datetime.timezone.utc) - timedeltaparse.parse_delta(config.RETENTION_PERIOD)
                backups = minio.list_objects(config.MINIO_BUCKET, prefix=f"{config.MINIO_PATH}/", recursive=True)
                for backup in backups:
                    if backup.last_modified < retention_date:
                        minio.remove_object(config.MINIO_BUCKET, backup.object_name)
                        print(f"[mongodb-backup] Deleted old backup: {backup.object_name}")
            except Exception as e:
                print(f"[mongodb-backup] Error during retention cleanup: {e}", file=sys.stderr)
                utils.webhook("Retention cleanup failed.")

    except Exception as e:
        print(f"[mongodb-backup] {e}", file=sys.stderr)
        utils.webhook(f"Backup process failed.")
        sys.exit(1)
