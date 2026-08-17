import os
import uuid
import base64
import io
from datetime import datetime, time
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.core.deps import require_admin, get_current_user
from app.models.domain import User, Employee, Department, FaceEncoding, RoleEnum
from app.schemas.domain_schemas import EmployeeCreate, EmployeeUpdate, EmployeeOut
from app.services.face_service import base64_to_cv2, extract_face_encoding
import cv2
import numpy as np

router = APIRouter(prefix="/employees", tags=["Employees"])

class FaceSnapshotsRequest(BaseModel):
    images_base64: List[str]

def parse_time_str(time_str: str) -> time:
    try:
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))
    except Exception:
        return time(9, 0)

@router.get("", response_model=List[EmployeeOut])
@router.get("/", response_model=List[EmployeeOut])
def list_employees(
    store_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Employee)
    if store_id:
        query = query.filter(Employee.store_id == store_id)
    employees = query.all()
    out = []
    for emp in employees:
        u = emp.user
        dept = emp.department
        st = emp.store
        face_count = len(emp.face_encodings)
        out.append(EmployeeOut(
            id=emp.id,
            user_id=emp.user_id,
            username=u.username if u else "",
            user=u,
            first_name=emp.first_name,
            last_name=emp.last_name,
            phone=emp.phone,
            position=emp.position,
            department_id=emp.department_id,
            department=dept,
            store_id=emp.store_id,
            store=st,
            store_name=st.store_name if st else None,
            monthly_salary=emp.monthly_salary,
            employment_date=emp.employment_date,
            work_start_time=emp.work_start_time.strftime("%H:%M"),
            work_end_time=emp.work_end_time.strftime("%H:%M"),
            is_active=emp.is_active,
            profile_photo=emp.profile_photo,
            face_count=face_count,
            face_encodings=emp.face_encodings,
            created_at=emp.created_at
        ))
    return out

@router.post("", response_model=EmployeeOut)
@router.post("/", response_model=EmployeeOut)
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    existing_user = db.query(User).filter(User.username == payload.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered.")

    user = User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        role=RoleEnum.EMPLOYEE,
        is_active=payload.is_active
    )
    db.add(user)
    db.flush()

    start_t = parse_time_str(payload.work_start_time)
    end_t = parse_time_str(payload.work_end_time)

    emp = Employee(
        user_id=user.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        position=payload.position,
        department_id=payload.department_id,
        store_id=payload.store_id,
        monthly_salary=payload.monthly_salary,
        employment_date=payload.employment_date or datetime.utcnow().date(),
        work_start_time=start_t,
        work_end_time=end_t,
        is_active=payload.is_active
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)

    st = emp.store

    return EmployeeOut(
        id=emp.id,
        user_id=emp.user_id,
        username=user.username,
        user=user,
        first_name=emp.first_name,
        last_name=emp.last_name,
        phone=emp.phone,
        position=emp.position,
        department_id=emp.department_id,
        department=emp.department,
        store_id=emp.store_id,
        store=st,
        store_name=st.store_name if st else None,
        monthly_salary=emp.monthly_salary,
        employment_date=emp.employment_date,
        work_start_time=emp.work_start_time.strftime("%H:%M"),
        work_end_time=emp.work_end_time.strftime("%H:%M"),
        is_active=emp.is_active,
        profile_photo=emp.profile_photo,
        face_count=0,
        face_encodings=[],
        created_at=emp.created_at
    )

@router.put("/{id}", response_model=EmployeeOut)
def update_employee(
    id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    emp = db.query(Employee).filter(Employee.id == id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    if payload.first_name is not None: emp.first_name = payload.first_name
    if payload.last_name is not None: emp.last_name = payload.last_name
    if payload.phone is not None: emp.phone = payload.phone
    if payload.position is not None: emp.position = payload.position
    if payload.department_id is not None: emp.department_id = payload.department_id
    if payload.store_id is not None: emp.store_id = payload.store_id
    if payload.monthly_salary is not None: emp.monthly_salary = payload.monthly_salary
    if payload.work_start_time is not None: emp.work_start_time = parse_time_str(payload.work_start_time)
    if payload.work_end_time is not None: emp.work_end_time = parse_time_str(payload.work_end_time)
    if payload.is_active is not None: 
        emp.is_active = payload.is_active
        if emp.user:
            emp.user.is_active = payload.is_active

    if payload.password and emp.user:
        emp.user.password_hash = get_password_hash(payload.password)

    db.commit()
    db.refresh(emp)

    st = emp.store

    return EmployeeOut(
        id=emp.id,
        user_id=emp.user_id,
        username=emp.user.username if emp.user else "",
        user=emp.user,
        first_name=emp.first_name,
        last_name=emp.last_name,
        phone=emp.phone,
        position=emp.position,
        department_id=emp.department_id,
        department=emp.department,
        store_id=emp.store_id,
        store=st,
        store_name=st.store_name if st else None,
        monthly_salary=emp.monthly_salary,
        employment_date=emp.employment_date,
        work_start_time=emp.work_start_time.strftime("%H:%M"),
        work_end_time=emp.work_end_time.strftime("%H:%M"),
        is_active=emp.is_active,
        profile_photo=emp.profile_photo,
        face_count=len(emp.face_encodings),
        face_encodings=emp.face_encodings,
        created_at=emp.created_at
    )

@router.delete("/{id}")
def delete_employee(
    id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    emp = db.query(Employee).filter(Employee.id == id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    user = emp.user
    db.delete(emp)
    if user:
        db.delete(user)
    db.commit()
    return {"message": "Employee and associated account deleted"}

@router.post("/{id}/register-camera-faces")
def register_camera_faces(
    id: int,
    payload: FaceSnapshotsRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    emp = db.query(Employee).filter(Employee.id == id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Ishchi topilmadi.")

    if not payload.images_base64:
        raise HTTPException(status_code=400, detail="Kamida 1 ta rasm tushirishingiz kerak.")

    saved_encodings = []
    processed_count = 0

    for b64_img in payload.images_base64:
        try:
            cv2_img = base64_to_cv2(b64_img)
        except Exception:
            continue

        encoding, face_count, msg = extract_face_encoding(cv2_img)
        if face_count != 1 or encoding is None:
            continue

        filename = f"emp_{emp.id}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(settings.FACES_FOLDER, filename)
        cv2.imwrite(filepath, cv2_img)

        rel_path = f"/uploads/faces/{filename}"
        if not emp.profile_photo:
            emp.profile_photo = rel_path

        face_obj = FaceEncoding(
            employee_id=emp.id,
            image_path=rel_path,
            encoding_data=encoding
        )
        db.add(face_obj)
        saved_encodings.append(face_obj)
        processed_count += 1

    if processed_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Olingan rasmlarda yuz aniqlanmadi. Kameraga to'g'ri qarab 3-5 ta rasm tushiring."
        )

    db.commit()
    return {
        "message": f"Successfully registered {processed_count} camera face encodings for {emp.first_name} {emp.last_name}",
        "processed_count": processed_count,
        "total_registered": len(emp.face_encodings)
    }

@router.post("/{id}/upload-faces")
async def upload_employee_faces(
    id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    emp = db.query(Employee).filter(Employee.id == id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    saved_encodings = []
    processed_count = 0

    for file in files:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            continue

        encoding, face_count, msg = extract_face_encoding(img)
        if face_count != 1 or encoding is None:
            continue

        filename = f"emp_{emp.id}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(settings.FACES_FOLDER, filename)
        cv2.imwrite(filepath, img)

        rel_path = f"/uploads/faces/{filename}"
        if not emp.profile_photo:
            emp.profile_photo = rel_path

        face_obj = FaceEncoding(
            employee_id=emp.id,
            image_path=rel_path,
            encoding_data=encoding
        )
        db.add(face_obj)
        saved_encodings.append(face_obj)
        processed_count += 1

    if processed_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yuklangan rasmlarda yuz aniqlanmadi."
        )

    db.commit()
    return {
        "message": f"Successfully registered {processed_count} face encodings for employee {emp.first_name} {emp.last_name}",
        "processed_count": processed_count,
        "total_registered": len(emp.face_encodings)
    }

@router.delete("/{id}/faces/{face_id}")
@router.delete("/{id}/faces/{face_id}/")
@router.delete("/{id}/face-encodings/{face_id}")
@router.delete("/{id}/face-encodings/{face_id}/")
def delete_employee_face(
    id: int,
    face_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    emp = db.query(Employee).filter(Employee.id == id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Ishchi topilmadi.")

    face = db.query(FaceEncoding).filter(FaceEncoding.id == face_id, FaceEncoding.employee_id == id).first()
    if not face:
        raise HTTPException(status_code=404, detail="Yuz rasmi topilmadi.")

    # Remove physical file if present
    if face.image_path:
        clean_path = face.image_path.lstrip("/uploads/faces/").lstrip("uploads/faces/")
        file_on_disk = os.path.join(settings.FACES_FOLDER, clean_path)
        if os.path.exists(file_on_disk):
            try:
                os.remove(file_on_disk)
            except Exception:
                pass

    db.delete(face)
    db.commit()
    db.refresh(emp)

    # Reset profile photo if deleted face was profile photo
    if not emp.face_encodings:
        emp.profile_photo = None
        db.commit()

    return {
        "message": "Yuz rasmi muvaffaqiyatli o'chirildi.",
        "remaining_count": len(emp.face_encodings)
    }

@router.delete("/{id}/faces")
@router.delete("/{id}/faces/")
@router.delete("/{id}/face-encodings")
@router.delete("/{id}/face-encodings/")
def delete_all_employee_faces(
    id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    emp = db.query(Employee).filter(Employee.id == id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Ishchi topilmadi.")

    for face in emp.face_encodings:
        if face.image_path:
            clean_path = face.image_path.lstrip("/uploads/faces/").lstrip("uploads/faces/")
            file_on_disk = os.path.join(settings.FACES_FOLDER, clean_path)
            if os.path.exists(file_on_disk):
                try:
                    os.remove(file_on_disk)
                except Exception:
                    pass
        db.delete(face)

    emp.profile_photo = None
    db.commit()
    db.refresh(emp)

    return {
        "message": "Barcha yuz rasmlari o'chirildi.",
        "remaining_count": 0
    }
