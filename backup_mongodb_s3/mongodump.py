import subprocess
from minio import Minio
from backup_mongodb_s3 import config


def mongodump_to_minio_stream(
        minio_client: Minio,
        minio_bucket: str,
        minio_file_name: str,
        mongo_uri: str,
        mongo_database: str,
        mongo_collection: str | None = None,
        mongo_query: str | None = None,
):
    command = [
        "mongodump",
        "--archive",
        "--gzip",
        "--readPreference", config.MONGODB_READ_PREFERENCE,
        "--uri", mongo_uri,
        "--db", mongo_database,
    ]

    if mongo_collection:
        command += ["--collection", mongo_collection]

    if mongo_query:
        command += ["--query", mongo_query]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1024 * 1024,
    )

    if not process.stdout:
        raise RuntimeError("Failed to open mongodump stdout")

    try:
        minio_client.put_object(
            bucket_name=minio_bucket,
            object_name=minio_file_name,
            data=process.stdout,
            length=-1,
            part_size=64 * 1024 * 1024,
            content_type="application/gzip",
        )

        _, stderr = process.communicate()

        if process.returncode != 0:
            raise RuntimeError(stderr.decode("utf-8", errors="replace"))

    finally:
        process.kill()
