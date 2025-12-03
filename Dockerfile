FROM alpine:latest

RUN --mount=type=cache,target=/etc/apk/cache apk add --update-cache curl bash mongodb-tools minio-client python3

COPY scripts/backup-mongodb.sh /usr/local/bin/backup-mongodb.sh
RUN chmod +x /usr/local/bin/backup-mongodb.sh

COPY scripts/query-generator.py /usr/local/bin/query-generator.py

ENV MINIO_COMMAND="mcli"
CMD ["/usr/local/bin/backup-mongodb.sh"]
