import os

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://root:password@mongodb:27017/?authSource=admin&readPreference=primaryPreferred")
MONGODB_COLLECTIONS = os.getenv("MONGODB_COLLECTIONS", "")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "")
MINIO_PATH = os.getenv("MINIO_PATH", "backups")
MINIO_SECURE = (os.getenv("MINIO_SECURE", "False").lower() in ("true", "1", "enabled")) or (MINIO_ENDPOINT or "").startswith("https://")

RETENTION_PERIOD = os.getenv("RETENTION_PERIOD", "")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
