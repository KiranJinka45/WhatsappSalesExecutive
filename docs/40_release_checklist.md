# Closely AI - Production Release & Operations Checklist

This document defines standard procedures, check scripts, and operations protocols for deploying, backup/restoring, monitoring, and maintaining Closely AI in production.

---

## 1. Clean Installation & Docker-Compose Verification

To verify that the application installs cleanly from scratch without dependency issues or environment assumptions, execute the following steps:

### A. Environment Provisioning
1. Clone the repository to a clean, isolated staging environment:
   ```bash
   git clone https://github.com/KiranJinka45/whatsapp_AI-Sales-Employee.git closely-deploy
   cd closely-deploy
   ```
2. Confirm Docker and Docker-Compose are installed:
   ```bash
   docker --version && docker-compose --version
   ```

### B. Setup & Build Sequence
1. Create a secure environment file from the production template:
   ```bash
   cp .env.example .env.production
   # Populate all variables in .env.production
   ```
2. Build and launch all containers in detached mode:
   ```bash
   docker-compose --env-file .env.production up -d --build
   ```
3. Verify that all 3 core containers (`closely_db`, `closely_redis`, and `closely_backend`) are running:
   ```bash
   docker-compose ps
   ```

### C. Database Migration & Initialization
1. Execute the Alembic migrations inside the running backend container to build the database schema:
   ```bash
   docker-compose exec backend alembic upgrade head
   ```
2. Confirm the `products` table has the correct `embedding_status` column and the pgvector extension is enabled:
   ```bash
   docker-compose exec db psql -U postgres -d closely_db -c "\d products"
   ```

---

## 2. Secrets Management Protocol

To protect credentials and prevent security vulnerabilities, do not store API keys or secrets in source control.

### A. Production Config & Environment Variables
* **Required Production Secrets**:
  - `DATABASE_URL`: Production pgvector database credentials.
  - `REDIS_URL`: Production Redis instance credentials.
  - `GEMINI_API_KEY`: Production Google Gemini API access key.
  - `JWT_SECRET`: High-entropy string used for token signatures.
  - `WHATSAPP_ACCESS_TOKEN`: Permanent Meta Cloud API access token.
  - `WHATSAPP_APP_SECRET`: Meta App Dashboard client secret (for signature verification).

### B. Secret Mounting In Production
* **Staging/Local**: Configured via local `.env.production` files (git-ignored).
* **Production Cloud (AWS/GCP)**: Mount secrets directly from **AWS Secrets Manager** or **GCP Secret Manager** into the container runtime. Avoid writing plain text secrets to disk.

---

## 3. Database Backup & Restore Procedures

To prevent data loss and ensure system reliability during updates or unexpected failures, execute the following manual or automated scripts.

### A. Automated Backup Script (`/scripts/backup.sh`)
Configure a nightly cron job on the host machine to dump database contents:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/closely"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="$BACKUP_DIR/closely_db_backup_$TIMESTAMP.sql"

# Create directory if it does not exist
mkdir -p "$BACKUP_DIR"

# Run PostgreSQL backup utility
docker-compose exec -t db pg_dump -U postgres -d closely_db -F c -b -v -f "/var/lib/postgresql/data/backup.dump"
docker-compose cp db:/var/lib/postgresql/data/backup.dump "$FILENAME"
docker-compose exec db rm "/var/lib/postgresql/data/backup.dump"

# Delete backups older than 14 days
find "$BACKUP_DIR" -type f -name "*.sql" -mtime +14 -delete

echo "Backup created successfully at $FILENAME"
```

### B. Restore Procedure
To restore the database from a compiled dump file:
1. Copy the backup file into the running database container:
   ```bash
   docker-compose cp /var/backups/closely/closely_db_backup_20260707_095520.sql db:/var/lib/postgresql/data/restore.dump
   ```
2. Terminate active database connections:
   ```bash
   docker-compose exec db psql -U postgres -d postgres -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE datname = 'closely_db' AND pid <> pg_backend_pid();"
   ```
3. Drop and recreate the database:
   ```bash
   docker-compose exec db dropdb -U postgres closely_db
   docker-compose exec db createdb -U postgres closely_db
   ```
4. Restore the schema and data from the dump:
   ```bash
   docker-compose exec db pg_restore -U postgres -d closely_db -v "/var/lib/postgresql/data/restore.dump"
   ```

---

## 4. Operational Monitoring & Log Rotation

To ensure high uptime and prevent disk exhaustion, the production stack enforces strict log rotation and monitoring configurations.

### A. Docker Log Rotation Config
Avoid unconstrained Docker logs by editing `/etc/docker/daemon.json` (or adding it directly in `docker-compose.yml` for container-level overrides):
```yaml
# docker-compose.yml container log limit config
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "5"
```
This limits container log sizes to **10MB** each and retains a maximum of **5 historical log rotations** per container.

### B. Uptime & Diagnostics Monitoring
* **Diagnostics Health Check**: Endpoint `GET /api/health` checks database connection pool, redis availability, and API configurations.
* **Process Watchdogs**:
  - Configure **Prometheus** to scrape FastAPI endpoints every 15 seconds.
  - Setup **Grafana** dashboard monitoring container CPU, RAM saturation, and Redis cache memory usage.
* **Alerting Boundaries**: Trigger pager alerts (P0 notification) if:
  - `/api/health` returns status code `503` for >2 consecutive minutes.
  - Webhook message latency averages `>3.0s` over a 5-minute window.
  - Redis memory usage exceeds `85%` of allocated system limits.
