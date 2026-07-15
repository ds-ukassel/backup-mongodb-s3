# backup-mongodb-s3
Simple script for backing up mongodb databases to an S3 (minio) bucket using different formats.

The script internally uses [`mongodump`](https://www.mongodb.com/docs/database-tools/mongodump/) to create the backups.
When not using Docker, make sure to install it first.

## Configuration

```bash
MONGODB_URI="mongodb://root:password@mongodb:27017/?authSource=admin&readPreference=primaryPreferred"
MONGODB_COLLECTIONS=

MINIO_ENDPOINT=
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
MINIO_BUCKET=
MINIO_PATH="backups"
MINIO_SECURE=false

RETENTION_PERIOD=
DISCORD_WEBHOOK_URL=
```

## Description

When running the script, it will use mongodump to connect to the databases, create a backup for each specified entry and upload it to the specified S3 bucket.

It will also remove backups older than the specified time period defined by `RETENTION_PERIOD`.
To specify a date, use a string like `1y 1m 1d 12H 30M 10S` (1 year, 1 month, 1 day, 12 hours, 30 minutes and 10 seconds).
A year is considered as 365 days and a month is considered as 30 days.

To disable this feature, leave `RETENTION_PERIOD` empty.

`MONGODB_COLLECTIONS` can be used to specify the tables to back up (see [Backup Settings](#backup-settings)).

Backups will be stored under the specified `MINIO_PATH` in the bucket `MINIO_BUCKET`, with filenames in the format `<database>_<collection>_<strategy>_<date>.<extension>`.
The `date` will depend on the strategy and include the timestamp of the backup (for `FULL` strategy) or the start date of the backup (for other strategies).
If the whole database is backed up, the collection will be omitted from the filename.

When setting `DISCORD_WEBHOOK_URL`, a notification will be sent to the specified Discord webhook if the backup fails.

### Backup Settings

The collections and their corresponding backup settings are provided by the `MONGODB_COLLECTIONS` environment variable as a YAML list of objects.
Alternatively you can simply provide the name as a string, which will be treated as a full backup of the database.

```yaml
# Backup all entries in the collection "shop.customers"
- database: "shop"
  collection: "customers"

# Backup all entries in the collection "shop.orders" that were created in the last week
- database: "shop"
  collection: "orders"
  strategy: "WEEK"
  ts_column: "created_at"
  ts_format: "DT"

# Backup the whole database "shop" (equivalent to `- database: "shop"`)
- shop
```

For each entry, the `database` field is required.
If `collection` is not specified, a full backup of the database will be created.
If `collection` is specified, you can either specify a `strategy` or leave it empty for a full backup of the collection.
If a `strategy` is specified, the script will filter the entries and only back up the objects that match the specified strategy.

Supported strategies:
- `full`: full backup of the collection
- `day`: [yesterday 00:00, today 00:00)
- `week`: [Monday of last week 00:00, Monday of this week 00:00)
- `month`: [1st day of last month 00:00, 1st day of this month 00:00)

The `ts_column` defines the field used for filtering the rows (e.g. `createdAt` as a DateTime).
If `ts_column` is not specified, the script will use the `_id` field for filtering, which is an ObjectId that contains a timestamp of when the object was created by MongoDB.
The `ts_format` defines the format of the column and will default to `OID` if not specified.

**Please note that only objects with a valid, compatible timestamp will be backed up when using a strategy other than `full`.**

Supported formats:
- `OID`: ObjectId (from MongoDB)
- `DT`: DateTime (e.g. `2026-02-02 12:00:00`)
- `EPOCH`: Unix timestamp (e.g. `1770988180`)
