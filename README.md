# backup-mongodb-s3
Simple script for backing up a MongoDB database to an S3 (minio) bucket.


# Configuration
- [x] Supports custom S3 endpoints (e.g. minio)
- [x] Uses piping instead of tmp file
- [x] Compression is done with gzip
- [x] Creates bucket if it's not created
- [x] Can be run in Kubernetes or Docker

## Configuration
```bash
# Required environment variables
MONGODB_URI='mongodb://root:password@mongodb:27017/?authSource=admin'
MINIO_ENDPOINT='http://localhost:9000'
MINIO_ACCESS_KEY='minioadmin'
MINIO_SECRET_KEY='minioadmin'

# Optional variables
MINIO_BUCKET='mongodb-backups'
MINIO_PATH='mongodb-dumps'
MONGODB_READ_PREFERENCE='secondaryPreferred'
RETENTION_PERIOD='7d'
MINIO_COMMAND='mc'
DISCORD_WEBHOOK_URL=''
COLLECTION_STRATEGIES='db.collection1=day db.collection2=week db.collection3=month'
STRATEGY_ID='_id'
```

## Strategies
The script supports different backup strategies for creating partial backups of specific collections.
If no strategies are defined, a full dump of the mongodb instance will be created (all databases and collections).

The strategies are defined in the `COLLECTION_STRATEGIES` environment variable as a space-separated list of `db.collection=strategy` pairs.
Supported strategies:
- `full`: full backup of the collection
- `day`: [yesterday 00:00, today 00:00)
- `week`: [1st day of last week 00:00, 1st day of this week 00:00)
- `month`: [1st day of last month 00:00, 1st day of this month 00:00)

The `STRATEGY_ID` variable defines the field used for filtering the documents in the collection (default is `_id`).
This can be changed if a collection references another object which should be used as the filter field (e.g. `_parent`).

## Cron backup with kubernetes

cronjob.yaml:
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup-mongodb
spec:
  schedule: {{ .Values.backup.mongodb.schedule }}
  timeZone: {{ .Values.backup.mongodb.timeZone }}
  concurrencyPolicy: Replace
  jobTemplate:
    spec:
      parallelism: 1
      template:
        spec:
          restartPolicy: Never
          imagePullSecrets:
            - name: registry-vs
          containers:
            - name: backup-mongodb-s3
              image: {{ .Values.backup.mongodb.image }}
              imagePullPolicy: Always
              env:
                - name: MONGODB_URI
                  valueFrom:
                    secretKeyRef:
                      name: {{ .Values.backup.mongodb.existingSecret }}
                      key: MONGO_URI
                - name: MINIO_BUCKET
                  value: {{ .Values.backup.mongodb.bucket }}
                - name: MINIO_PATH
                  value: {{ .Values.backup.mongodb.path }}
                - name: MINIO_ENDPOINT
                  valueFrom:
                    secretKeyRef:
                      name: {{ .Values.backup.mongodb.existingSecret }}
                      key: minio-endpoint
                - name: MINIO_ACCESS_KEY
                  valueFrom:
                    secretKeyRef:
                      name: {{ .Values.backup.mongodb.existingSecret }}
                      key: minio-access-key
                - name: MINIO_SECRET_KEY
                  valueFrom:
                    secretKeyRef:
                      name: {{ .Values.backup.mongodb.existingSecret }}
                      key: minio-secret-key
                - name: DISCORD_WEBHOOK_URL
                  valueFrom:
                    secretKeyRef:
                      name: {{ .Values.backup.mongodb.existingSecret }}
                      key: discord-webhook-url
                      optional: true
                - name: RETENTION_PERIOD
                  value: {{ .Values.backup.mongodb.keep | quote }}
```

When not using Helm, replace the placeholders `{{ ... }}` with appropriate values.