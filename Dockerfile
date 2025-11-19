FROM alpine:latest

RUN apk add --no-cache curl bash mongodb-tools minio-client

COPY scripts/backup-mongodb.sh /usr/local/bin/backup-mongodb.sh
RUN chmod +x /usr/local/bin/backup-mongodb.sh

ENV MINIO_COMMAND="mcli"
ENTRYPOINT ["/usr/local/bin/backup-mongodb.sh"]