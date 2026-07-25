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
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.APP_ENV,
            traces_sample_rate=1.0 if settings.APP_ENV != "production" else 0.1,
        )
except ImportError:
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
    Base.metadata.create_all(bind=engine)
    
    # Fail-safe to add detected_language column if it doesn't exist
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS detected_language VARCHAR(50);"))
            conn.commit()
    except Exception as e:
        print(f"Altering messages table failed: {e}. If using SQLite or table already has the column, this is normal.")

    # Start Redis Worker in a daemon background thread for queue processing
    import threading
    from .worker import Worker
    worker_instance = Worker()
    worker_thread = threading.Thread(target=worker_instance.run, daemon=True)
    worker_thread.start()
    print("Started Closely AI Worker daemon thread in background.")
        
    yield
    worker_instance.running = False


app = FastAPI(
    title="Closely AI API",
    description="Backend API for Closely AI - AI Sales Employee for Clothing Brands",
    version="2.0",
    lifespan=lifespan
)

# CORS configuration (registered first to be outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], # Vite dev server defaults
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
