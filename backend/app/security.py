from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db, tenant_var, log_admin_access
from . import models

from fastapi import Request

def mask_sensitive_data(val: Optional[str]) -> str:
    """
    Sanitizes phone numbers, Bearer tokens, and secrets from application logs.
    """
    if not val:
        return ""
    s_val = str(val).strip()
    if len(s_val) <= 6:
        return "***REDACTED***"
    return f"{s_val[:3]}****{s_val[-3:]}"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

def get_token(request: Request) -> str:
    # Prefer Authorization header over cookies (critical for tenant isolation and API client priority)
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ")[1]
    
    token = request.cookies.get("access_token")
    if not token:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(get_token), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # Query without tenant restriction first to authenticate the user
    db.is_admin = True
    log_admin_access("user_authentication_lookup", {"user_id": mask_sensitive_data(user_id)})
    try:
        from sqlalchemy import text
        from sqlalchemy.orm import joinedload
        import uuid as _uuid
        db.execute(text("SET LOCAL app.current_tenant = ''"))
        user_uuid = _uuid.UUID(str(user_id)) if not isinstance(user_id, _uuid.UUID) else user_id
        user = db.query(models.User).options(joinedload(models.User.organization)).filter(models.User.id == user_uuid).first()
    finally:
        db.is_admin = False
        
    if user is None or user.organization_id is None or (user.organization and user.organization.deleted_at is not None):
        raise credentials_exception
        
    # Set both context variable and session attribute
    tenant_var.set(user.organization_id)
    db.organization_id = user.organization_id
    # Force the local variable update in PostgreSQL immediately to enforce RLS
    from sqlalchemy import text
    try:
        db.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(user.organization_id)})
    except Exception:
        pass
    return user

def get_current_org(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> models.Organization:
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to any organization"
        )
    if current_user.organization and current_user.organization.deleted_at is None:
        return current_user.organization
    org = db.query(models.Organization).filter(
        models.Organization.id == current_user.organization_id,
        models.Organization.deleted_at.is_(None)
    ).first()
    if not org:
        raise credentials_exception
    return org

def require_role(*allowed_roles: str):
    def role_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        return current_user
    return role_checker

