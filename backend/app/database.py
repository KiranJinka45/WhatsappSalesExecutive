import contextvars
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Query
from .config import settings

# Create engine (psycopg2-binary will be used)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# ContextVar to store the current tenant (organization_id) - kept as fallback
tenant_var = contextvars.ContextVar("tenant_id", default=None)
# ContextVar to store correlation trace request ID
request_id_var = contextvars.ContextVar("request_id", default=None)

@event.listens_for(Query, "before_compile", retval=True)
def before_compile_tenant_filter(query):
    # Try session-scoped organization_id first
    session = query.session
    org_id = getattr(session, "organization_id", None)
    
    # Fallback to ContextVar (useful for background tasks or threads)
    if org_id is None:
        org_id = tenant_var.get()
        
    if org_id is None:
        return query

    # Apply with_loader_criteria to safely filter all loads of subclasses
    from sqlalchemy.orm import with_loader_criteria
    for desc in query.column_descriptions:
        entity = desc.get("entity")
        if entity and hasattr(entity, "organization_id"):
            query = query.options(
                with_loader_criteria(
                    entity,
                    lambda target: target.organization_id == org_id
                )
            )
    return query

def get_db():
    db = SessionLocal()
    db.organization_id = None
    try:
        yield db
    finally:
        db.close()

