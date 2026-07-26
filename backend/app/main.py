import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, request_id_var
from .routers import auth, catalog, brand, conversations, webhooks, health, analytics
from sqlalchemy import text
from .config import settings
import logging
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
            conn.commit()
    except Exception as e:
        print(f"Altering messages table failed: {e}. If using SQLite or table already has the column, this is normal.")

    # Start Redis Worker in a daemon background thread for queue processing
    worker_instance = None
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

# CORS configuration (registered first to be outermost)
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://closely-frontend.onrender.com",
]

# Read optional ALLOWED_ORIGINS env var if present (comma-separated)
extra_origins = os.getenv("ALLOWED_ORIGINS")
if extra_origins:
    allowed_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if os.getenv("ALLOW_ALL_CORS") else allowed_origins,
    allow_origin_regex=r"https://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def ensure_cors_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method == "OPTIONS":
        response = JSONResponse(status_code=200, content={"status": "ok"})
    else:
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(f"Unhandled server exception: {exc}", exc_info=True)
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})

    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"
    return response


def contains_null_byte(val) -> bool:
    if isinstance(val, str):
        return "\x00" in val
    elif isinstance(val, dict):
        return any(contains_null_byte(v) for v in val.values()) or any(contains_null_byte(k) for k in val.keys())
    elif isinstance(val, list):
        return any(contains_null_byte(item) for item in val)
    return False

@app.middleware("http")
async def block_null_bytes(request: Request, call_next):
    # Always allow OPTIONS preflight requests to pass cleanly to CORSMiddleware
    if request.method == "OPTIONS":
        return await call_next(request)

    # Check path and query parameters for NUL characters (including URL-decoded)
    import urllib.parse
    decoded_path = urllib.parse.unquote(request.url.path)
    decoded_query = urllib.parse.unquote(request.url.query)
    if "\x00" in decoded_path or "\x00" in decoded_query:
        return JSONResponse(status_code=400, content={"detail": "NUL characters are not allowed"})
        
    # Check headers
    for key, val in request.headers.items():
        if "\x00" in val:
            return JSONResponse(status_code=400, content={"detail": "NUL characters are not allowed"})

    # Check request body if not a multipart file upload
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        body = await request.body()
        if b"\x00" in body:
            return JSONResponse(status_code=400, content={"detail": "NUL characters are not allowed"})
            
        # Parse JSON-escaped NULs
        if "application/json" in content_type and body:
            try:
                import json
                parsed = json.loads(body)
                if contains_null_byte(parsed):
                    return JSONResponse(status_code=400, content={"detail": "NUL characters are not allowed"})
            except Exception:
                pass
                
        # Parse form-urlencoded escaped NULs
        if "application/x-www-form-urlencoded" in content_type and body:
            try:
                parsed_str = body.decode("utf-8", errors="ignore")
                decoded_str = urllib.parse.unquote(parsed_str)
                if "\x00" in decoded_str:
                    return JSONResponse(status_code=400, content={"detail": "NUL characters are not allowed"})
            except Exception:
                pass

    return await call_next(request)

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
