import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, request_id_var, SessionLocal
from .routers import auth, catalog, brand, conversations, webhooks, health, analytics, approvals
from sqlalchemy import text
from .config import settings
import logging
logger = logging.getLogger(__name__)
import uuid
try:
    import sentry_sdk
    _sentry_dsn = getattr(settings, "SENTRY_DSN", None)
    if _sentry_dsn:
        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=getattr(settings, "APP_ENV", "production"),
            traces_sample_rate=1.0 if getattr(settings, "APP_ENV", "production") != "production" else 0.1,
        )
except (ImportError, Exception):
    pass


# Configure Correlation Trace ID Logging
class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get() or "no-trace"
        return True

handler = logging.StreamHandler()
handler.addFilter(CorrelationIdFilter())
handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(request_id)s] %(name)s: %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Programmatic database migrations upgrade on startup (bypasses Render startCommand dashboard overrides)
    if os.environ.get("TESTING") != "true":
        try:
            from alembic.config import Config
            from alembic import command
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            alembic_ini_path = os.path.join(base_dir, "alembic.ini")
            if os.path.exists(alembic_ini_path):
                logger.info(f"Running programmatic database migrations from {alembic_ini_path}...")
                alembic_cfg = Config(alembic_ini_path)
                alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("postgres://", "postgresql://").replace("%", "%%"))
                command.upgrade(alembic_cfg, "head")
                logger.info("Programmatic database migrations completed successfully!")
            else:
                logger.warning(f"alembic.ini not found at {alembic_ini_path}. Skipping programmatic migrations.")
        except Exception as migration_err:
            logger.error(f"Failed to run programmatic database migrations: {migration_err}", exc_info=True)

    # Auto-fix legacy database image URLs if domain had typo
    if os.environ.get("TESTING") != "true":
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE products 
                    SET image_urls = string_to_array(replace(array_to_string(image_urls, ','), 'qclmaiqfppunrodjpka.supabase.co', 'qclmaiqqfppunrodjpka.supabase.co'), ','),
                        image_embedding_status = 'pending'
                    WHERE array_to_string(image_urls, ',') LIKE '%qclmaiqfppunrodjpka.supabase.co%';
                """))
                conn.commit()
        except Exception as e:
            logger.debug(f"Production image URL domain migration skipped: {e}")

    # Auto-repair legacy invalid WABA IDs (e.g. email addresses in WABA ID field)
    if os.environ.get("TESTING") != "true":
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE organizations 
                    SET whatsapp_business_account_id = NULL 
                    WHERE whatsapp_business_account_id LIKE '%@%' OR (whatsapp_business_account_id IS NOT NULL AND whatsapp_business_account_id !~ '^[0-9]+$' AND whatsapp_business_account_id NOT LIKE '%demo%');
                """))
                conn.commit()
                logger.info("Auto-repair: Cleaned invalid WABA IDs containing email addresses from organizations table.")
        except Exception as e:
            logger.debug(f"WABA ID cleanup skipped: {e}")

    # Self-healing database schema check (auto-repair missing columns/tables on live DB)
    if os.environ.get("TESTING") != "true":
        try:
            from sqlalchemy import inspect
            with engine.begin() as conn:
                inspector = inspect(conn)
                
                # Check if notifications table exists
                if 'notifications' not in inspector.get_table_names():
                    logger.info("Auto-repair: Creating missing 'notifications' table...")
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS notifications (
                            id UUID PRIMARY KEY,
                            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                            approval_request_id UUID REFERENCES approval_requests(id) ON DELETE CASCADE,
                            type VARCHAR(100) NOT NULL,
                            status VARCHAR(50),
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
                            read_at TIMESTAMP WITH TIME ZONE
                        )
                    """))
                
                # Check columns in approval_requests
                columns = [c['name'] for c in inspector.get_columns('approval_requests')]
                
                if 'risk_score' not in columns:
                    logger.info("Auto-repair: Adding 'risk_score' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN risk_score INTEGER DEFAULT 0"))
                    
                if 'llm_model' not in columns:
                    logger.info("Auto-repair: Adding 'llm_model' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN llm_model VARCHAR(100)"))
                    
                if 'prompt_version' not in columns:
                    logger.info("Auto-repair: Adding 'prompt_version' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN prompt_version VARCHAR(50) DEFAULT 'v1'"))
                    
                if 'retrieval_ids' not in columns:
                    logger.info("Auto-repair: Adding 'retrieval_ids' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN retrieval_ids JSONB DEFAULT '[]'::jsonb"))
                    
                if 'grounding_score' not in columns:
                    logger.info("Auto-repair: Adding 'grounding_score' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN grounding_score NUMERIC(5,2) DEFAULT 0.0"))
                    
                if 'decision_engine_version' not in columns:
                    logger.info("Auto-repair: Adding 'decision_engine_version' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN decision_engine_version VARCHAR(50) DEFAULT 'v1.0'"))
                    
                if 'rule_triggered' not in columns:
                    logger.info("Auto-repair: Adding 'rule_triggered' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN rule_triggered VARCHAR(100)"))

                if 'approved_by_user_id' not in columns:
                    logger.info("Auto-repair: Adding 'approved_by_user_id' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN approved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL"))

                if 'edited_by_user_id' not in columns:
                    logger.info("Auto-repair: Adding 'edited_by_user_id' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN edited_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL"))

                if 'edited_response' not in columns:
                    logger.info("Auto-repair: Adding 'edited_response' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN edited_response TEXT"))

                if 'message_hash' not in columns:
                    logger.info("Auto-repair: Adding 'message_hash' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN message_hash VARCHAR(64)"))

                if 'version' not in columns:
                    logger.info("Auto-repair: Adding 'version' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN version INTEGER DEFAULT 1"))

                if 'price_snapshot' not in columns:
                    logger.info("Auto-repair: Adding 'price_snapshot' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN price_snapshot JSONB DEFAULT '{}'::jsonb"))

                if 'stock_snapshot' not in columns:
                    logger.info("Auto-repair: Adding 'stock_snapshot' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN stock_snapshot JSONB DEFAULT '{}'::jsonb"))

                if 'expires_at' not in columns:
                    logger.info("Auto-repair: Adding 'expires_at' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE"))

                if 'sent_at' not in columns:
                    logger.info("Auto-repair: Adding 'sent_at' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN sent_at TIMESTAMP WITH TIME ZONE"))

                if 'error_message' not in columns:
                    logger.info("Auto-repair: Adding 'error_message' to approval_requests...")
                    conn.execute(text("ALTER TABLE approval_requests ADD COLUMN error_message TEXT"))
                    
                if 'risk_level' in columns:
                    logger.info("Auto-repair: Dropping 'risk_level' from approval_requests...")
                    try:
                        conn.execute(text("ALTER TABLE approval_requests DROP COLUMN risk_level"))
                    except Exception as drop_err:
                        logger.warning(f"Failed to drop risk_level: {drop_err}")

                # Check columns in approval_audit_logs if table exists
                if 'approval_audit_logs' in inspector.get_table_names():
                    audit_columns = [c['name'] for c in inspector.get_columns('approval_audit_logs')]
                    if 'revalidation_passed' not in audit_columns:
                        logger.info("Auto-repair: Adding 'revalidation_passed' to approval_audit_logs...")
                        conn.execute(text("ALTER TABLE approval_audit_logs ADD COLUMN revalidation_passed BOOLEAN DEFAULT TRUE"))
                    if 'message_content' not in audit_columns:
                        logger.info("Auto-repair: Adding 'message_content' to approval_audit_logs...")
                        conn.execute(text("ALTER TABLE approval_audit_logs ADD COLUMN message_content TEXT"))
                    if 'message_hash' not in audit_columns:
                        logger.info("Auto-repair: Adding 'message_hash' to approval_audit_logs...")
                        conn.execute(text("ALTER TABLE approval_audit_logs ADD COLUMN message_hash VARCHAR(64)"))

                # Check columns in organizations
                org_columns = [c['name'] for c in inspector.get_columns('organizations')]
                if 'whatsapp_onboarding_state' not in org_columns:
                    logger.info("Auto-repair: Adding 'whatsapp_onboarding_state' to organizations...")
                    conn.execute(text("ALTER TABLE organizations ADD COLUMN whatsapp_onboarding_state VARCHAR(50) DEFAULT 'NOT_CONNECTED'"))
                if 'whatsapp_onboarding_metadata' not in org_columns:
                    logger.info("Auto-repair: Adding 'whatsapp_onboarding_metadata' to organizations...")
                    conn.execute(text("ALTER TABLE organizations ADD COLUMN whatsapp_onboarding_metadata JSONB DEFAULT '{}'::jsonb"))

                # Check if whatsapp_onboarding_audit_logs table exists
                if 'whatsapp_onboarding_audit_logs' not in inspector.get_table_names():
                    logger.info("Auto-repair: Creating missing 'whatsapp_onboarding_audit_logs' table...")
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS whatsapp_onboarding_audit_logs (
                            id UUID PRIMARY KEY,
                            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                            action VARCHAR(50) NOT NULL,
                            previous_state VARCHAR(50),
                            new_state VARCHAR(50) NOT NULL,
                            error_category VARCHAR(100),
                            metadata JSONB DEFAULT '{}'::jsonb,
                            correlation_id VARCHAR(64),
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
                        )
                    """))
                        
            logger.info("Database schema auto-repair check completed successfully!")
        except Exception as repair_err:
            logger.error(f"Failed during database schema auto-repair: {repair_err}", exc_info=True)

    # In testing and production, schema is managed cleanly by migrations/test fixtures.
    # Lifespan dynamic DDL is only needed as a convenience fallback in local development.
    if os.environ.get("TESTING") != "true" and getattr(settings, "APP_ENV", "production") == "development":
        # Initialize pgvector extension in Postgres dynamically
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
        except Exception as e:
            logger.debug(f"pgvector extension check skipped: {e}")

        # Initialize Database tables
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            logger.debug(f"Base.metadata.create_all skipped: {e}")
    
        # Fail-safe to add detected_language column if it doesn't exist
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS detected_language VARCHAR(50);"))
                conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS whatsapp_business_account_id VARCHAR(100);"))
                conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS whatsapp_phone_number_id VARCHAR(100);"))
                conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS whatsapp_access_token TEXT;"))
                conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS is_whatsapp_connected INTEGER DEFAULT 0;"))
                conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS policies JSONB DEFAULT '{}';"))
                conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_embedding vector(3072);"))
                conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_embedding_status VARCHAR(50) DEFAULT 'pending';"))
                
                # Optimized indexes for multi-tenant query routing and joins
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(organization_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_categories_org_id ON categories(organization_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_customer_memories_org_phone ON customer_memories(organization_id, customer_phone);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_org_phone ON orders(organization_id, customer_phone);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_approval_requests_org_id ON approval_requests(organization_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_notifications_org_status ON notifications(organization_id, status);"))
                
                # Milestone 4 Approval & Audit DDL
                conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS approved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL;"))
                conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS edited_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL;"))
                conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS edited_response TEXT;"))
                conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS message_hash VARCHAR(64);"))
                conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;"))
                conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS price_snapshot JSONB DEFAULT '{}';"))
                conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS stock_snapshot JSONB DEFAULT '{}';"))
                conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;"))
                conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ;"))
                conn.execute(text("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS error_message TEXT;"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_approval_audit_logs_org ON approval_audit_logs(organization_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_approval_audit_logs_req ON approval_audit_logs(approval_request_id);"))
                conn.commit()
        except Exception as e:
            logger.debug(f"Manual index/column ensure skipped: {e}")

    # Start Redis Worker in a daemon background thread for queue processing
    worker_instance = None
    if not settings.TESTING:
        try:
            import threading
            from .worker import Worker
            worker_instance = Worker()
            worker_thread = threading.Thread(target=worker_instance.run, daemon=True)
            worker_thread.start()
            print("Started Closely AI Worker daemon thread in background.")
        except Exception as e:
            print(f"Failed to start worker daemon thread: {e}")

        # Start image embedding backfill task in a background daemon thread
        try:
            import threading
            from .catalog_service import backfill_missing_image_embeddings
            backfill_thread = threading.Thread(
                target=backfill_missing_image_embeddings,
                args=(SessionLocal,),
                daemon=True
            )
            backfill_thread.start()
            print("Started Closely image embedding backfill scan in background.")
        except Exception as e:
            print(f"Failed to start image embedding backfill scan: {e}")
        
    yield
    if worker_instance:
        worker_instance.running = False


app = FastAPI(
    title="Closely AI API",
    description="Backend API for Closely AI - AI Sales Employee for Clothing Brands",
    version="2.0",
    lifespan=lifespan
)

# Standard Outer CORSMiddleware (Guarantees CORS headers on ALL responses including 401, 403, 500)
allowed_origins = [
    "https://closely-frontend.onrender.com",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]

# Append additional origins from CORS_ORIGINS env var (comma-separated)
if getattr(settings, "CORS_ORIGINS", None):
    for origin in settings.CORS_ORIGINS.split(","):
        origin = origin.strip()
        if origin and origin not in allowed_origins:
            allowed_origins.append(origin)

logger.info(f"CORS allowed_origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

def _add_cors_headers(response: Response, request: Request):
    """Add CORS headers to error responses so browsers don't mask 500s as CORS failures."""
    origin = request.headers.get("origin")
    if origin:
        import re
        if origin in allowed_origins or re.match(r"https://.*\.onrender\.com", origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.middleware("http")
async def security_nul_check_middleware(request: Request, call_next):
    # Check NUL bytes in path & query
    import urllib.parse
    decoded_path = urllib.parse.unquote(request.url.path)
    decoded_query = urllib.parse.unquote(request.url.query)
    if "\x00" in decoded_path or "\x00" in decoded_query:
        resp = JSONResponse(status_code=400, content={"detail": "NUL characters are not allowed"})
        return _add_cors_headers(resp, request)
    
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        if "NUL" in str(exc) or "null byte" in str(exc).lower():
            resp = JSONResponse(status_code=400, content={"detail": "NUL characters are not allowed"})
            return _add_cors_headers(resp, request)
        logger.error(f"Unhandled server exception in middleware: {exc}", exc_info=True)
        resp = JSONResponse(status_code=500, content={"detail": f"Internal server error: {str(exc)}"})
        return _add_cors_headers(resp, request)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if "NUL" in str(exc) or "null byte" in str(exc).lower():
        resp = JSONResponse(status_code=400, content={"detail": "NUL characters are not allowed"})
        return _add_cors_headers(resp, request)
    logger.error(f"Global unhandled exception: {exc}", exc_info=True)
    resp = JSONResponse(
        status_code=500,
        content={"detail": f"Server error: {str(exc)}"}
    )
    return _add_cors_headers(resp, request)

from fastapi.exceptions import RequestValidationError, ResponseValidationError
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc}", exc_info=True)
    resp = JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )
    return _add_cors_headers(resp, request)

@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request: Request, exc: ResponseValidationError):
    logger.error(f"Response validation error: {exc}", exc_info=True)
    resp = JSONResponse(
        status_code=500,
        content={"detail": f"Response validation error: {str(exc)}", "errors": exc.errors()}
    )
    return _add_cors_headers(resp, request)

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    # Try getting existing request ID from client headers, else generate unique UUID
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)



# Register routers
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(brand.router)
app.include_router(conversations.router)
app.include_router(webhooks.router)
app.include_router(approvals.router)
app.include_router(health.router)
app.include_router(analytics.router)

from fastapi.staticfiles import StaticFiles
import os
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory="static/uploads"), name="uploads")

@app.get("/")
def read_root():
    return {
        "app": "Closely AI API Gateway",
        "status": "healthy",
        "version": "2.3-release"
    }

@app.get("/health")
def health():
    return {"status": "ok", "app": "Closely AI API Gateway"}
