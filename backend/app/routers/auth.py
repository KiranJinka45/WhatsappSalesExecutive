from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, security

router = APIRouter(prefix="/api/auth", tags=["auth"], responses={400: {"description": "Bad Request"}})

@router.post("/signup", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED, responses={400: {"description": "Bad Request"}, 409: {"description": "Conflict"}})
def signup(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    from ..database import tenant_var
    token_reset = tenant_var.set(None)
    db.organization_id = None
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
        return new_user
    finally:
        tenant_var.reset(token_reset)

@router.post("/login", response_model=schemas.Token, responses={401: {"description": "Unauthorized"}})
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    from ..database import tenant_var
    token_reset = tenant_var.set(None)
    db.organization_id = None
    try:
        user = db.query(models.User).filter(models.User.email == form_data.username).first()
    finally:
        tenant_var.reset(token_reset)

    if not user or not security.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = security.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.UserOut, responses={401: {"description": "Unauthorized"}})
def read_users_me(current_user: models.User = Depends(security.get_current_user)):
    return current_user
