import subprocess

from minio import Minio


def mongodump_to_minio_stream(
        minio_client: Minio,
        minio_bucket: str,
        minio_file_name: str,
        mongo_uri: str,
        mongo_database: str | None = None,
        mongo_collection: str | None = None,
        mongo_query: str | None = None,
):
    command = [
        "mongodump",
        "--archive",
        "--gzip",
        "--uri", mongo_uri,
    ]

    if mongo_database:
        command += ["--db", mongo_database]

    if mongo_collection:
        command += ["--collection", mongo_collection]

    if mongo_query:
        command += ["--query", mongo_query]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=None,
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

        returncode = process.wait()
        if returncode != 0:
            raise RuntimeError(f"mongodump failed with exit code {returncode}")

    finally:
        process.kill()
