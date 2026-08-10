from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import require_employee, require_admin, get_current_user
from app.models.domain import Employee, User, Attendance, AttendanceLog, FaceEncoding, AttendanceStatusEnum
from app.schemas.domain_schemas import (
    AttendanceVerificationRequest, AttendanceOut, AttendanceLogOut,
    KioskAttendanceRequest, KioskEmployeeSummary,
    ExpressAttendanceRequest, ExpressAttendanceResponse,
    ManualAttendanceRequest
)
from app.services.attendance_service import process_check_in, process_check_out, get_store_settings
from app.services.geo_service import calculate_haversine_distance
from app.services.face_service import base64_to_cv2, extract_face_encoding, compare_face_encodings

router = APIRouter(prefix="/attendance", tags=["Attendance Flow"])

@router.post("/express-scan", response_model=ExpressAttendanceResponse)
def express_scan(
    payload: ExpressAttendanceRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    store = get_store_settings(db)
    ip_address = request.client.host if request.client else "127.0.0.1"

    # 1. Geofence Check
    distance = calculate_haversine_distance(payload.latitude, payload.longitude, store.latitude, store.longitude)
    if distance > store.radius_meters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Siz do'kon davomat zonasidan tashqaridasiz. Masofa: {distance:.1f}m (Ruxsat: {store.radius_meters:.1f}m)."
        )

    # 2. Extract Face Encoding
    try:
        cv2_img = base64_to_cv2(payload.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Rasm tayyorlashda xatolik yuz berdi.")

    query_encoding, face_count, face_msg = extract_face_encoding(cv2_img)
    if face_count != 1 or query_encoding is None:
        raise HTTPException(status_code=400, detail=face_msg)

    # 3. Match Employee
    matched_employee: Optional[Employee] = None
    best_score = 0.0

    if payload.employee_id:
        emp = db.query(Employee).filter(Employee.id == payload.employee_id, Employee.is_active == True).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Ishchi profil topilmadi.")
        
        registered = db.query(FaceEncoding).filter(FaceEncoding.employee_id == emp.id).all()
        if not registered:
            raise HTTPException(status_code=400, detail=f"{emp.first_name} {emp.last_name} uchun bazada FaceID yuklanmagan.")

        reg_encodings = [item.encoding_data for item in registered]
        score, is_match, msg = compare_face_encodings(query_encoding, reg_encodings, threshold=store.face_confidence_threshold)
        if is_match:
            matched_employee = emp
            best_score = score
    else:
        # Scan across all active store employees
        active_employees = db.query(Employee).filter(Employee.is_active == True).all()
        for emp in active_employees:
            registered = db.query(FaceEncoding).filter(FaceEncoding.employee_id == emp.id).all()
            if not registered:
                continue
            reg_encodings = [item.encoding_data for item in registered]
            score, is_match, msg = compare_face_encodings(query_encoding, reg_encodings, threshold=store.face_confidence_threshold)
            if is_match and score > best_score:
                best_score = score
                matched_employee = emp

    if not matched_employee or best_score < store.face_confidence_threshold:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Yuz tanilmadi yoki bazaga mos kelmadi. FaceID moslik darajasi: {(best_score * 100):.1f}% (Talab etilgan: {(store.face_confidence_threshold * 100):.1f}%)."
        )

    # 4. Enforce Daily Rules & Action
    if payload.action == "CHECK_IN":
        att = process_check_in(
            db=db,
            employee=matched_employee,
            image_base64=payload.image_base64,
            lat=payload.latitude,
            lng=payload.longitude,
            device_info="Passless FaceID Express Terminal",
            ip_address=ip_address
        )
        act_text = "Ishga kelish"
        time_str = att.check_in_time.strftime("%H:%M") if att.check_in_time else "N/A"
    else:
        att = process_check_out(
            db=db,
            employee=matched_employee,
            image_base64=payload.image_base64,
            lat=payload.latitude,
            lng=payload.longitude,
            device_info="Passless FaceID Express Terminal",
            ip_address=ip_address
        )
        act_text = "Ishdan ketish"
        time_str = att.check_out_time.strftime("%H:%M") if att.check_out_time else "N/A"

    dept_name = matched_employee.department.name if matched_employee.department else "General"
    emp_full_name = f"{matched_employee.first_name} {matched_employee.last_name}"

    return ExpressAttendanceResponse(
        employee_id=matched_employee.id,
        employee_name=emp_full_name,
        position=matched_employee.position,
        department_name=dept_name,
        action=payload.action,
        date=att.date,
        time=time_str,
        status=att.status.value,
        score=best_score,
        distance=distance,
        message=f"Xush kelibsiz {emp_full_name}! {act_text} soat {time_str} da muvaffaqiyatli qayd etildi."
    )

@router.get("/kiosk-employees", response_model=List[KioskEmployeeSummary])
def list_kiosk_employees(db: Session = Depends(get_db)):
    today = date.today()
    employees = db.query(Employee).filter(Employee.is_active == True).all()

    summaries = []
    for emp in employees:
        att = db.query(Attendance).filter(
            Attendance.employee_id == emp.id,
            Attendance.date == today
        ).first()

        checked_in = att is not None and att.check_in_time is not None
        checked_out = att is not None and att.check_out_time is not None
        dept_name = emp.department.name if emp.department else "General"

        summaries.append(KioskEmployeeSummary(
            id=emp.id,
            first_name=emp.first_name,
            last_name=emp.last_name,
            position=emp.position,
            department_name=dept_name,
            profile_photo=emp.profile_photo,
            checked_in_today=checked_in,
            checked_out_today=checked_out
        ))
    return summaries

@router.post("/check-in", response_model=AttendanceOut)
def check_in(
    payload: AttendanceVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
    employee: Employee = Depends(require_employee)
):
    ip_address = request.client.host if request.client else "127.0.0.1"
    att = process_check_in(
        db=db,
        employee=employee,
        image_base64=payload.image_base64,
        lat=payload.latitude,
        lng=payload.longitude,
        device_info=payload.device_info or "Web Camera",
        ip_address=ip_address
    )
    
    dept_name = employee.department.name if employee.department else "General"
    return AttendanceOut(
        id=att.id,
        employee_id=att.employee_id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        department_name=dept_name,
        date=att.date,
        check_in_time=att.check_in_time,
        check_out_time=att.check_out_time,
        status=att.status,
        worked_hours=att.worked_hours,
        late_minutes=att.late_minutes,
        early_leave_minutes=att.early_leave_minutes,
        overtime_minutes=att.overtime_minutes,
        check_in_lat=att.check_in_lat,
        check_in_lng=att.check_in_lng,
        check_in_distance=att.check_in_distance,
        check_in_score=att.check_in_score,
        device_info=att.device_info,
        ip_address=att.ip_address
    )

@router.post("/check-out", response_model=AttendanceOut)
def check_out(
    payload: AttendanceVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
    employee: Employee = Depends(require_employee)
):
    ip_address = request.client.host if request.client else "127.0.0.1"
    att = process_check_out(
        db=db,
        employee=employee,
        image_base64=payload.image_base64,
        lat=payload.latitude,
        lng=payload.longitude,
        device_info=payload.device_info or "Web Camera",
        ip_address=ip_address
    )

    dept_name = employee.department.name if employee.department else "General"
    return AttendanceOut(
        id=att.id,
        employee_id=att.employee_id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        department_name=dept_name,
        date=att.date,
        check_in_time=att.check_in_time,
        check_out_time=att.check_out_time,
        status=att.status,
        worked_hours=att.worked_hours,
        late_minutes=att.late_minutes,
        early_leave_minutes=att.early_leave_minutes,
        overtime_minutes=att.overtime_minutes,
        check_in_lat=att.check_in_lat,
        check_in_lng=att.check_in_lng,
        check_in_distance=att.check_in_distance,
        check_in_score=att.check_in_score,
        device_info=att.device_info,
        ip_address=att.ip_address
    )

@router.get("/my-history", response_model=List[AttendanceOut])
def get_my_history(
    db: Session = Depends(get_db),
    employee: Employee = Depends(require_employee)
):
    records = db.query(Attendance).filter(
        Attendance.employee_id == employee.id
    ).order_by(Attendance.date.desc()).limit(100).all()

    dept_name = employee.department.name if employee.department else "General"
    emp_name = f"{employee.first_name} {employee.last_name}"

    out = []
    for att in records:
        out.append(AttendanceOut(
            id=att.id,
            employee_id=att.employee_id,
            employee_name=emp_name,
            department_name=dept_name,
            date=att.date,
            check_in_time=att.check_in_time,
            check_out_time=att.check_out_time,
            status=att.status,
            worked_hours=att.worked_hours,
            late_minutes=att.late_minutes,
            early_leave_minutes=att.early_leave_minutes,
            overtime_minutes=att.overtime_minutes,
            check_in_lat=att.check_in_lat,
            check_in_lng=att.check_in_lng,
            check_in_distance=att.check_in_distance,
            check_in_score=att.check_in_score,
            device_info=att.device_info,
            ip_address=att.ip_address
        ))
    return out

@router.get("/all-logs", response_model=List[AttendanceLogOut])
def list_all_logs(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    logs = db.query(AttendanceLog).order_by(AttendanceLog.id.desc()).limit(200).all()
    out = []
    for log in logs:
        emp_name = f"{log.employee.first_name} {log.employee.last_name}" if log.employee else f"Ходим #{log.employee_id}"
        out.append(AttendanceLogOut(
            id=log.id,
            employee_id=log.employee_id,
            employee_name=emp_name,
            action=log.action,
            timestamp=log.timestamp,
            latitude=log.latitude,
            longitude=log.longitude,
            distance=log.distance,
            recognition_score=log.recognition_score,
            status=log.status,
            device=log.device
        ))
    return out


@router.post("/manual-mark", response_model=AttendanceOut)
def manual_mark_attendance(
    payload: ManualAttendanceRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    employee = db.query(Employee).filter(Employee.id == payload.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Ходим топилмади.")

    today = payload.date
    attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date == today
    ).first()

    # Parse check_in_time
    check_in_dt = None
    if payload.check_in_time:
        try:
            h, m = map(int, payload.check_in_time.split(":"))
            check_in_dt = datetime.combine(today, datetime.min.time().replace(hour=h, minute=m))
        except Exception:
            pass

    # Parse check_out_time
    check_out_dt = None
    if payload.check_out_time:
        try:
            h, m = map(int, payload.check_out_time.split(":"))
            check_out_dt = datetime.combine(today, datetime.min.time().replace(hour=h, minute=m))
        except Exception:
            pass

    # Status mapping
    status_val = AttendanceStatusEnum.ON_TIME
    if payload.status:
        try:
            status_val = AttendanceStatusEnum(payload.status)
        except Exception:
            pass

    worked_hours = 0.0
    if check_in_dt and check_out_dt and check_out_dt > check_in_dt:
        worked_hours = round((check_out_dt - check_in_dt).total_seconds() / 3600.0, 2)

    if not attendance:
        attendance = Attendance(
            employee_id=employee.id,
            date=today,
            check_in_time=check_in_dt,
            check_out_time=check_out_dt,
            status=status_val,
            worked_hours=worked_hours,
            device_info="Қўлда Давомат (Админ)",
            ip_address="127.0.0.1"
        )
        db.add(attendance)
    else:
        if check_in_dt:
            attendance.check_in_time = check_in_dt
        if check_out_dt:
            attendance.check_out_time = check_out_dt
        attendance.status = status_val
        attendance.worked_hours = worked_hours
        attendance.device_info = "Қўлда Давомат (Админ)"

    db.commit()
    db.refresh(attendance)

    # Log Event
    log = AttendanceLog(
        attendance_id=attendance.id,
        employee_id=employee.id,
        action="MANUAL_ADMIN_MARK",
        timestamp=datetime.now(),
        status=status_val.value,
        device=f"Admin Manual ({payload.notes or 'Қўлда киритилди'})"
    )
    db.add(log)
    db.commit()

    dept_name = employee.department.name if employee.department else "General"
    return AttendanceOut(
        id=attendance.id,
        employee_id=attendance.employee_id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        department_name=dept_name,
        date=attendance.date,
        check_in_time=attendance.check_in_time,
        check_out_time=attendance.check_out_time,
        status=attendance.status,
        worked_hours=attendance.worked_hours,
        late_minutes=attendance.late_minutes,
        early_leave_minutes=attendance.early_leave_minutes,
        overtime_minutes=attendance.overtime_minutes,
        check_in_lat=attendance.check_in_lat,
        check_in_lng=attendance.check_in_lng,
        check_in_distance=attendance.check_in_distance,
        check_in_score=attendance.check_in_score,
        device_info=attendance.device_info,
        ip_address=attendance.ip_address
    )

