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
```

## Cron backup with kubernetes

How usage with [Helm-CronJob](https://github.com/bambash/helm-cronjobs) chart.

values.yaml:
```
---
jobs:
  - name: mongodb-backup
    image:
      repository: registry.example.org/kube-public/mongodump_minio
      tag: 1.0.0
      imagePullPolicy: IfNotPresent
    securityContext:
      runAsUser: 1000
      runAsGroup: 1000    
    schedule: "0 1 * * *"
    failedJobsHistoryLimit: 1
    successfulJobsHistoryLimit: 3
    concurrencyPolicy: Forbid
    restartPolicy: OnFailure
    serviceAccount: {}
    env:
    - name: MONGODB_URI
      value: "mongodb://user:pass@mongodb-example-headless:27017"
    - name: MINIO_ENDPOINT
      value: 'http://localhost:9000'
    - name: MINIO_BUCKET
      value: backup-mongodb
    - name: MINIO_PATH
      value: mongodb-dumps
    - name: RETENTION_PERIOD
      value: 7d
    - name: DISCORD_WEBHOOK_URL
      value: "https://discord.com/api/webhooks/..."
```
Deploy cronjob:

```
helm upgrade --install  backup-mongodb -n backup-mongodb -f values.yaml . --set "jobs[0].env[0].value=$MONGODB_URI_SECRET" --set "jobs[0].env[2].value=$S3_URI_SECRET"
```
