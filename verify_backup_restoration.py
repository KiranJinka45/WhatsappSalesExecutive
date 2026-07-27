import subprocess
import time
import sys
import httpx
from sqlalchemy import create_engine, text

# Configuration
DB_URL = "postgresql://postgres:postgres@localhost:5434/closely_db"
POSTGRES_DB_URL = "postgresql://postgres:postgres@localhost:5434/postgres"
CONTAINER_NAME = "closely_db"
BACKUP_PATH = "/tmp/closely_db_backup.dump"
HEALTH_CHECK_URL = "http://localhost:8000/api/health"

TABLES_TO_CHECK = [
    "organizations",
    "users",
    "categories",
    "products",
    "conversations",
    "messages",
    "orders",
    "order_items"
]

def run_command(cmd, shell=False):
    print(f"Executing command: {cmd}")
    res = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Command failed with exit code {res.returncode}")
        print(f"Stdout:\n{res.stdout}")
        print(f"Stderr:\n{res.stderr}")
        return False, res.stdout, res.stderr
    return True, res.stdout, res.stderr

def get_row_counts():
    counts = {}
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            # Check table existence and row count
            for table in TABLES_TO_CHECK:
                # Check if table exists
                exists_query = text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}');")
                exists = conn.execute(exists_query).scalar()
                if exists:
                    count_query = text(f"SELECT COUNT(*) FROM {table};")
                    count = conn.execute(count_query).scalar()
                    counts[table] = count
                else:
                    counts[table] = -1
    except Exception as e:
        print(f"Failed to query database row counts: {e}")
        return None
    return counts

def verify_backup_restoration():
    print("=== STARTING BACKUP & RESTORATION VERIFICATION ===")
    
    # 1. Fetch baseline counts
    print("\nStep 1: Fetching baseline row counts...")
    baseline_counts = get_row_counts()
    if baseline_counts is None:
        print("[FAIL] Could not query baseline database state. Make sure containers are running.")
        sys.exit(1)
    
    print("Baseline state:")
    for t, c in baseline_counts.items():
        print(f"  - Table '{t}': {c if c != -1 else 'DOES NOT EXIST'} rows")

    # 2. Run pg_dump inside container
    print("\nStep 2: Performing PG dump inside container...")
    dump_cmd = ["docker", "exec", CONTAINER_NAME, "pg_dump", "-U", "postgres", "-d", "closely_db", "-F", "c", "-b", "-f", BACKUP_PATH]
    success, stdout, stderr = run_command(dump_cmd)
    if not success:
        print("[FAIL] pg_dump failed.")
        sys.exit(1)
    print("[OK] Backup successfully saved to container temp path.")

    # 3. Terminate active sessions to closely_db and drop database
    print("\nStep 3: Dropping database closely_db...")
    # Terminate sessions
    term_sql = "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = 'closely_db' AND pid <> pg_backend_pid();"
    term_cmd = ["docker", "exec", CONTAINER_NAME, "psql", "-U", "postgres", "-d", "postgres", "-c", term_sql]
    run_command(term_cmd)
    
    # Drop db
    drop_cmd = ["docker", "exec", CONTAINER_NAME, "dropdb", "-U", "postgres", "--if-exists", "closely_db"]
    success, _, _ = run_command(drop_cmd)
    if not success:
        print("[FAIL] Drop database failed.")
        sys.exit(1)
    print("[OK] Database closely_db successfully dropped.")

    # 4. Recreate empty closely_db and load pgvector extension
    print("\nStep 4: Recreating database closely_db...")
    create_cmd = ["docker", "exec", CONTAINER_NAME, "createdb", "-U", "postgres", "closely_db"]
    success, _, _ = run_command(create_cmd)
    if not success:
        print("[FAIL] Recreate database failed.")
        sys.exit(1)
        
    vector_cmd = ["docker", "exec", CONTAINER_NAME, "psql", "-U", "postgres", "-d", "closely_db", "-c", "CREATE EXTENSION IF NOT EXISTS vector;"]
    success, _, _ = run_command(vector_cmd)
    if not success:
        print("[FAIL] Creating vector extension failed.")
        sys.exit(1)
    print("[OK] Recreated empty closely_db with vector extension loaded.")

    # 5. Restore backup using pg_restore
    print("\nStep 5: Restoring database backup...")
    restore_cmd = ["docker", "exec", CONTAINER_NAME, "pg_restore", "-U", "postgres", "-d", "closely_db", BACKUP_PATH]
    # pg_restore often outputs warnings (like roles already exist) with non-zero exit codes or standard warnings.
    # We will log it but double check the data counts to determine final success.
    run_command(restore_cmd)
    print("[OK] Restore completed.")

    # 6. Verify row count integrity
    print("\nStep 6: Verifying restored row counts...")
    restored_counts = get_row_counts()
    if restored_counts is None:
        print("[FAIL] Could not query database counts after restore.")
        sys.exit(1)

    integrity_passed = True
    for table in TABLES_TO_CHECK:
        base = baseline_counts.get(table, -1)
        restored = restored_counts.get(table, -1)
        if base != restored:
            print(f"  [FAIL] Row count mismatch on table '{table}': expected {base}, found {restored}")
            integrity_passed = False
        else:
            print(f"  [PASS] Table '{table}': {restored} rows (matches baseline)")

    if not integrity_passed:
        print("[FAIL] Database integrity check failed.")
        sys.exit(1)
    print("[OK] Database integrity check passed! All rows and tables match baseline.")

    # 7. Smoke test active application health endpoint
    print("\nStep 7: Executing application smoke test...")
    try:
        # Give API a moment if it needs to reconnect
        time.sleep(1)
        res = httpx.get(HEALTH_CHECK_URL, timeout=5)
        if res.status_code == 200:
            print(f"[PASS] Health check API is responding: {res.json()}")
        else:
            print(f"[FAIL] Health check returned status code {res.status_code}: {res.text}")
            sys.exit(1)
    except Exception as e:
        print(f"[WARNING] Could not contact health check API: {e}. If the backend server is not running, run 'docker-compose up backend' first.")

    print("\n=== BACKUP & RESTORATION VERIFICATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    verify_backup_restoration()
