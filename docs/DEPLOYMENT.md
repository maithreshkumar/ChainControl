# Deployment

Development uses Docker Compose for MySQL, Redis, MinIO, four Besu QBFT validators, Django, Celery, React, and NGINX. Besu bootstrap generates disposable validator keys into a Docker volume; these keys are not production credentials.

Production requires separate hosts/failure domains for validators, TLS everywhere, secrets in a KMS/secret manager, HSM/KMS transaction signing, private networking, database backups, MinIO replication/versioning, monitoring, rate limiting, and image pinning/signature verification.

The public edge exposes only NGINX. MySQL, Redis, MinIO API, backend, and validator peer/RPC interfaces remain private.

