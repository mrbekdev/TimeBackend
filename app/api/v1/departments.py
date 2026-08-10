from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import require_admin, get_current_user
from app.models.domain import Department, User
from app.schemas.domain_schemas import DepartmentCreate, DepartmentOut

router = APIRouter(prefix="/departments", tags=["Departments"])

@router.get("", response_model=List[DepartmentOut])
@router.get("/", response_model=List[DepartmentOut])
def list_departments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Department).all()

@router.post("", response_model=DepartmentOut)
@router.post("/", response_model=DepartmentOut)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    existing = db.query(Department).filter(Department.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Department name already exists")
    
    dept = Department(name=payload.name, description=payload.description)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept

@router.delete("/{id}")
def delete_department(
    id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    dept = db.query(Department).filter(Department.id == id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    db.delete(dept)
    db.commit()
    return {"message": "Department deleted successfully"}
