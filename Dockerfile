FROM alpine

WORKDIR /scripts

RUN apk add mongodb-tools minio-client
# In the alpine minio-client, the command is called `mcli` instead of `mc`
ENV MC_CMD="/usr/bin/mcli"

COPY scripts/backup-mongodb.sh ./
RUN chmod +x backup-mongodb.sh

ENV MONGODB_URI=""
ENV MONGODB_OPLOG=""
ENV MONGODB_READ_PREFERENCE="secondaryPreferred"
ENV S3_URI=""
ENV S3_BUCKET=""
ENV RETENTION_PERIOD="14d"

CMD ["/scripts/backup-mongodb.sh"]
