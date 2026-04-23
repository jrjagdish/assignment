from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User, RoleEnum
from src.schemas import SignupRequest, LoginRequest, TokenResponse, MonitoringTokenRequest
from src.auth import (
    hash_password, verify_password,
    create_access_token, create_monitoring_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        institution_id=payload.institution_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(access_token=token)


@router.post("/monitoring-token", response_model=TokenResponse)
def get_monitoring_token(
    payload: MonitoringTokenRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Step 2 of monitoring officer auth.
    Caller must: (1) already have a valid standard JWT for a monitoring_officer account,
    and (2) supply the correct API key.
    Returns a short-lived (1-hour) scoped monitoring token.
    """
    from src.config import settings  # local import to avoid circular

    if current_user.role != RoleEnum.monitoring_officer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only monitoring_officer accounts can obtain a monitoring token",
        )
    if payload.key != settings.MONITORING_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    token = create_monitoring_token(current_user.id)
    return TokenResponse(access_token=token)
