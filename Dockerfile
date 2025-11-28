FROM alpine:latest

RUN --mount=type=cache,target=/etc/apk/cache apk add --update-cache curl bash mongodb-tools minio-client

COPY scripts/backup-mongodb.sh /usr/local/bin/backup-mongodb.sh
RUN chmod +x /usr/local/bin/backup-mongodb.sh

ENV MINIO_COMMAND="mcli"
CMD ["/usr/local/bin/backup-mongodb.sh"]
