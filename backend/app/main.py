import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, request_id_var
from .routers import auth, catalog, brand, conversations, webhooks, health, analytics
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
    # Initialize pgvector extension in Postgres dynamically
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
    except Exception as e:
        print(f"Failed to create pgvector extension: {e}. If using SQLite, this is normal and will be skipped.")

    # Initialize Database tables
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Failed to create database tables on startup: {e}. Tables may already exist in production (Supabase).")
    
    # Fail-safe to add detected_language column if it doesn't exist
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS detected_language VARCHAR(50);"))
            conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS whatsapp_business_account_id VARCHAR(100);"))
            conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS whatsapp_phone_number_id VARCHAR(100);"))
            conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS whatsapp_access_token TEXT;"))
            conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS is_whatsapp_connected INTEGER DEFAULT 0;"))
            conn.commit()
    except Exception as e:
        print(f"Altering database tables failed: {e}. If using SQLite or tables already have columns, this is normal.")

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
            print(f"Failed to start background worker: {e}. Messages will be processed synchronously.")
        
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
        logger.error(f"Unhandled server exception in middleware: {exc}", exc_info=True)
        resp = JSONResponse(status_code=500, content={"detail": f"Internal server error: {str(exc)}"})
        return _add_cors_headers(resp, request)

import traceback
recent_errors = []

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(f"Global unhandled exception: {exc}\n{tb}", exc_info=True)
    recent_errors.append({"type": "Exception", "error": str(exc), "traceback": tb, "timestamp": str(datetime.now())})
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
        status_code=400,
        content={"detail": "Invalid request payload", "errors": exc.errors()}
    )
    return _add_cors_headers(resp, request)

@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request: Request, exc: ResponseValidationError):
    tb = traceback.format_exc()
    logger.error(f"Response validation error: {exc}\n{tb}", exc_info=True)
    recent_errors.append({"type": "ResponseValidationError", "error": str(exc), "traceback": tb, "timestamp": str(datetime.now())})
    resp = JSONResponse(
        status_code=500,
        content={"detail": f"Response validation error: {str(exc)}", "errors": exc.errors()}
    )
    return _add_cors_headers(resp, request)

@app.get("/debug-errors")
def get_debug_errors(secret: str = None):
    if secret != "diagnose123":
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"errors": recent_errors}

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    # Try getting existing request ID from client headers, else generate unique UUID
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as exc:
        tb = traceback.format_exc()
        recent_errors.append({"type": "MiddlewareError", "error": str(exc), "traceback": tb, "timestamp": str(datetime.now())})
        logger.error(f"Unhandled exception in request {request_id}: {exc}\n{tb}", exc_info=True)
        resp = JSONResponse(status_code=500, content={"detail": f"Internal server error: {str(exc)}"})
        return _add_cors_headers(resp, request)
    finally:
        request_id_var.reset(token)


# Register routers
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(brand.router)
app.include_router(conversations.router)
app.include_router(webhooks.router)
app.include_router(health.router)
app.include_router(analytics.router)

@app.get("/")
def read_root():
    return {
        "app": "Closely AI API Gateway",
        "status": "healthy",
        "version": "2.0"
    }

@app.get("/health")
def health():
    return {"status": "ok", "app": "Closely AI API Gateway"}
