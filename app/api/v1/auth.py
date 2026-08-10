from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.deps import get_current_user
from app.models.domain import User, Employee, RoleEnum
from app.schemas.domain_schemas import Token, LoginRequest, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")

    employee_id = None
    if user.employee:
        employee_id = user.employee.id

    access_token = create_access_token(
        subject=user.username,
        role=user.role.value,
        employee_id=employee_id
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role.value,
        username=user.username,
        employee_id=employee_id
    )

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
