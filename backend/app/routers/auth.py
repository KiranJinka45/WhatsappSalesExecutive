from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, security

router = APIRouter(prefix="/api/auth", tags=["auth"], responses={400: {"description": "Bad Request"}})

from fastapi import APIRouter, Depends, HTTPException, status, Response

@router.post("/signup", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED, responses={400: {"description": "Bad Request"}, 409: {"description": "Conflict"}})
def signup(user_in: schemas.UserCreate, response: Response, db: Session = Depends(get_db)):
    db.is_admin = True
    try:
        # Check if user already exists
        existing_user = db.query(models.User).filter(models.User.email == user_in.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists"
            )
            
        # Check organization
        org_name = user_in.organization_name or f"{user_in.name}'s Boutique"
        org = models.Organization(name=org_name)
        db.add(org)
        db.commit()
        db.refresh(org)
        
        # Create user
        new_user = models.User(
            organization_id=org.id,
            email=user_in.email,
            password_hash=security.get_password_hash(user_in.password),
            name=user_in.name,
            role="owner"
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        access_token = security.create_access_token(data={"sub": str(new_user.id)})
        response.set_cookie(
            key="access_token",
            value=f"{access_token}",
            httponly=True,
            samesite="strict",
            secure=True,
            max_age=security.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return new_user
    finally:
        db.is_admin = False

from ..rate_limiter import InMemoryRateLimiter

login_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60, name="login")

@router.post("/login", response_model=schemas.LoginResponse, responses={401: {"description": "Unauthorized"}})
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    limiter: None = Depends(login_limiter)
):
    db.is_admin = True
    try:
        user = db.query(models.User).filter(models.User.email == form_data.username).first()
    finally:
        db.is_admin = False

    if not user or not security.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = security.create_access_token(data={"sub": str(user.id)})
    response.set_cookie(
        key="access_token",
        value=f"{access_token}",
        httponly=True,
        samesite="strict",
        secure=True,
        max_age=security.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return {"status": "success", "message": "Successfully authenticated", "access_token": access_token}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token", httponly=True, samesite="strict", secure=True)
    return {"status": "success"}

@router.get("/me", response_model=schemas.UserOut, responses={401: {"description": "Unauthorized"}})
def read_users_me(current_user: models.User = Depends(security.get_current_user)):
    return current_user
