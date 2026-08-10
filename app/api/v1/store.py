from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import require_admin, get_current_user
from app.models.domain import StoreSettings, User
from app.schemas.domain_schemas import StoreSettingsUpdate, StoreSettingsOut
from app.services.attendance_service import get_store_settings

router = APIRouter(prefix="/store", tags=["Store Settings"])

@router.get("", response_model=StoreSettingsOut)
@router.get("/", response_model=StoreSettingsOut)
def get_store(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_store_settings(db)

@router.put("", response_model=StoreSettingsOut)
@router.put("/", response_model=StoreSettingsOut)
def update_store(
    payload: StoreSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    store = get_store_settings(db)
    store.store_name = payload.store_name
    store.address = payload.address
    store.latitude = payload.latitude
    store.longitude = payload.longitude
    store.radius_meters = payload.radius_meters
    store.working_days = payload.working_days
    store.timezone = payload.timezone
    store.late_tolerance_min = payload.late_tolerance_min
    store.early_leave_tolerance_min = payload.early_leave_tolerance_min
    store.late_penalty_per_min = payload.late_penalty_per_min
    store.early_bonus_per_min = payload.early_bonus_per_min
    store.overtime_policy = payload.overtime_policy
    store.face_confidence_threshold = payload.face_confidence_threshold

    db.commit()
    db.refresh(store)
    return store
