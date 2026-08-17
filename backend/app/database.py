import contextvars
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Query
from .config import settings

logger = logging.getLogger(__name__)

# Create engine with optimized connection pooling for high concurrency
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
    pool_recycle=1800,
    pool_timeout=30
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

from sqlalchemy.orm import Session, with_loader_criteria
from sqlalchemy import text

@event.listens_for(Session, "after_begin")
def set_tenant_in_transaction(session, transaction, connection):
    if getattr(session, "is_admin", False):
        connection.execute(text("SET LOCAL app.current_tenant = ''"))
        return
        
    org_id = getattr(session, "organization_id", None) or tenant_var.get()
    if org_id is not None:
        connection.execute(
            text("SET LOCAL app.current_tenant = :org_id"),
            {"org_id": str(org_id)}
        )
    else:
        # Fail-closed: set to a dummy UUID to prevent global RLS bypass
        connection.execute(text("SET LOCAL app.current_tenant = '00000000-0000-0000-0000-000000000000'"))

@event.listens_for(Session, "do_orm_execute")
def do_orm_execute_tenant_filter(orm_execute_state):
    session = orm_execute_state.session
    if getattr(session, "is_admin", False):
        return
        
    options = []
    
    # Automatically apply soft-delete filtering globally for any mapped class with deleted_at attribute
    for mapper in Base.registry.mappers:
        model_cls = mapper.class_
        if hasattr(model_cls, "deleted_at"):
            options.append(
                with_loader_criteria(
                    model_cls,
                    lambda target_cls: target_cls.deleted_at.is_(None),
                    include_aliases=True
                )
            )
            
    org_id = getattr(session, "organization_id", None) or tenant_var.get()
    
    if org_id is not None:
        import uuid
        if isinstance(org_id, str):
            try:
                org_id = uuid.UUID(org_id)
            except ValueError:
                pass
        if (
            orm_execute_state.is_select
            and not orm_execute_state.is_column_load
            and not orm_execute_state.is_relationship_load
        ):
            # Gather tenant-aware classes dynamically to avoid circular imports
            tenant_classes = []
            for mapper in Base.registry.mappers:
                cls = mapper.class_
                if hasattr(cls, "organization_id"):
                    tenant_classes.append(cls)
            
            # Apply criteria to all tenant-aware classes
            for cls in tenant_classes:
                options.append(
                    with_loader_criteria(
                        cls,
                        lambda target_cls: target_cls.organization_id == org_id,
                        include_aliases=True
                    )
                )
                
    if options:
        orm_execute_state.statement = orm_execute_state.statement.options(*options)

@event.listens_for(engine, "checkin")
def reset_tenant_on_checkin(dbapi_connection, connection_record):
    """
    Guarantees that when a connection is returned to the pool,
    any session-scoped app.current_tenant variable is reset to prevent pool pollution.
    """
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("RESET app.current_tenant;")
        dbapi_connection.commit()
        cursor.close()
    except Exception:
        pass

def log_admin_access(action: str, details: dict):
    """
    Logs administrative privilege elevation (is_admin=True) to audit logs.
    """
    logger.info(f"[ADMIN_AUDIT] Action: {action} | Details: {details}")

def get_db():
    db = SessionLocal()
    db.organization_id = None
    try:
        yield db
    finally:
        try:
            from sqlalchemy import text
            db.execute(text("RESET app.current_tenant"))
        except Exception:
            pass
        db.close()

