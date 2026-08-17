from datetime import datetime, date, time, timedelta
from typing import Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.domain import (
    Employee, StoreSettings, FaceEncoding, Attendance, 
    AttendanceLog, AttendanceStatusEnum, Notification, NotificationTypeEnum, User
)
from app.core.time_utils import get_uzb_now, get_uzb_today
from app.services.geo_service import calculate_haversine_distance
from app.services.face_service import base64_to_cv2, extract_face_encoding, compare_face_encodings

def get_store_settings(db: Session, store_id: Optional[int] = None) -> StoreSettings:
    if store_id:
        store = db.query(StoreSettings).filter(StoreSettings.id == store_id).first()
        if store:
            return store
    
    settings = db.query(StoreSettings).first()
    if not settings:
        # Create default store settings if none exists
        settings = StoreSettings(
            store_name="Дўкон #1 (Асосий)",
            address="Филиал #1",
            latitude=41.311081,
            longitude=69.240562,
            radius_meters=150.0
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

def process_check_in(
    db: Session,
    employee: Employee,
    image_base64: str,
    lat: float,
    lng: float,
    device_info: str = "Web Camera",
    ip_address: str = "127.0.0.1"
) -> Attendance:
    store = get_store_settings(db, store_id=employee.store_id)
    today = get_uzb_today()
    now = get_uzb_now()

    # 1. Geofence Distance Check
    distance = calculate_haversine_distance(lat, lng, store.latitude, store.longitude)
    if distance > store.radius_meters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You are outside the allowed attendance area for {store.store_name}. Distance to store is {distance:.1f}m (Allowed: {store.radius_meters:.1f}m)."
        )

    # 2. Check duplicate Check-In for today
    existing_attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date == today
    ).first()

    if existing_attendance and existing_attendance.check_in_time is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already checked in for today."
        )

    # 3. Face Recognition Verification
    try:
        cv2_img = base64_to_cv2(image_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid image payload format.")

    query_encoding, face_count, face_msg = extract_face_encoding(cv2_img)
    if face_count != 1 or query_encoding is None:
        raise HTTPException(status_code=400, detail=face_msg)

    # Load employee registered face encodings
    registered = db.query(FaceEncoding).filter(FaceEncoding.employee_id == employee.id).all()
    if not registered:
        raise HTTPException(
            status_code=400,
            detail="No face encodings registered for your profile. Contact Admin to upload 5-10 face photos."
        )

    reg_encodings = [item.encoding_data for item in registered]
    score, is_match, comp_msg = compare_face_encodings(query_encoding, reg_encodings, threshold=store.face_confidence_threshold)

    if not is_match:
        raise HTTPException(
            status_code=400,
            detail=f"Face recognition failed. Confidence score {score * 100:.1f}% is below required threshold ({store.face_confidence_threshold * 100:.1f}%)."
        )

    # 4. Calculate Attendance Status & Late/Early Minutes
    work_start_dt = datetime.combine(today, employee.work_start_time)

    late_minutes = 0
    early_arrival_minutes = 0
    att_status = AttendanceStatusEnum.ON_TIME

    if now > work_start_dt:
        late_minutes = int((now - work_start_dt).total_seconds() / 60)
        att_status = AttendanceStatusEnum.LATE
    elif now < work_start_dt:
        early_arrival_minutes = int((work_start_dt - now).total_seconds() / 60)
        att_status = AttendanceStatusEnum.EARLY_ARRIVAL

    # 5. Save or Update Attendance Record
    if not existing_attendance:
        attendance = Attendance(
            employee_id=employee.id,
            store_id=store.id,
            date=today,
            check_in_time=now,
            status=att_status,
            late_minutes=late_minutes,
            early_arrival_minutes=early_arrival_minutes,
            check_in_lat=lat,
            check_in_lng=lng,
            check_in_distance=distance,
            check_in_score=score,
            device_info=device_info,
            ip_address=ip_address
        )
        db.add(attendance)
    else:
        attendance = existing_attendance
        attendance.check_in_time = now
        attendance.status = att_status
        attendance.late_minutes = late_minutes
        attendance.early_arrival_minutes = early_arrival_minutes
        attendance.check_in_lat = lat
        attendance.check_in_lng = lng
        attendance.check_in_distance = distance
        attendance.check_in_score = score
        attendance.device_info = device_info
        attendance.ip_address = ip_address

    db.commit()
    db.refresh(attendance)

    # 6. Log Event
    log = AttendanceLog(
        attendance_id=attendance.id,
        employee_id=employee.id,
        action="CHECK_IN",
        timestamp=now,
        latitude=lat,
        longitude=lng,
        distance=distance,
        recognition_score=score,
        status=att_status.value,
        device=device_info,
        ip_address=ip_address
    )
    db.add(log)

    # Send Notification if Late
    if att_status == AttendanceStatusEnum.LATE:
        notif = Notification(
            user_id=employee.user_id,
            title="Late Check-In Warning",
            message=f"You checked in {late_minutes} minutes past scheduled work time ({employee.work_start_time.strftime('%H:%M')}).",
            type=NotificationTypeEnum.LATE_WARNING
        )
        db.add(notif)

    db.commit()
    return attendance

def process_check_out(
    db: Session,
    employee: Employee,
    image_base64: str,
    lat: float,
    lng: float,
    device_info: str = "Web Camera",
    ip_address: str = "127.0.0.1"
) -> Attendance:
    store = get_store_settings(db, store_id=employee.store_id)
    today = get_uzb_today()
    now = get_uzb_now()

    # 1. Check existing attendance record
    attendance = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date == today
    ).first()

    if not attendance or not attendance.check_in_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must perform Check In before checking out."
        )

    if attendance.check_out_time is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already checked out for today."
        )

    # 2. Geofence Check against employee's assigned store
    distance = calculate_haversine_distance(lat, lng, store.latitude, store.longitude)
    if distance > store.radius_meters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Сиз танланган дўкон ({store.store_name}) ҳудудидан ташқаридасиз! Дўконгача масофа: {distance:.1f}м (Рухсат берилган: {store.radius_meters:.1f}м). Давомат белгиланмади!"
        )

    # 3. Face Recognition Verification
    try:
        cv2_img = base64_to_cv2(image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image format.")

    query_encoding, face_count, face_msg = extract_face_encoding(cv2_img)
    if face_count != 1 or query_encoding is None:
        raise HTTPException(status_code=400, detail=face_msg)

    registered = db.query(FaceEncoding).filter(FaceEncoding.employee_id == employee.id).all()
    reg_encodings = [item.encoding_data for item in registered]
    score, is_match, comp_msg = compare_face_encodings(query_encoding, reg_encodings, threshold=store.face_confidence_threshold)

    if not is_match:
        raise HTTPException(
            status_code=400,
            detail=f"Face recognition failed. Confidence score {score * 100:.1f}% is below required threshold ({store.face_confidence_threshold * 100:.1f}%)."
        )

    # 4. Calculate Worked Hours, Early Leave, & Overtime
    work_end_dt = datetime.combine(today, employee.work_end_time)

    worked_seconds = (now - attendance.check_in_time).total_seconds()
    worked_hours = round(worked_seconds / 3600.0, 2)

    early_leave_minutes = 0
    if now < work_end_dt:
        early_leave_minutes = int((work_end_dt - now).total_seconds() / 60)
        attendance.status = AttendanceStatusEnum.EARLY_LEAVE

    overtime_minutes = 0
    if now > work_end_dt:
        overtime_minutes = int((now - work_end_dt).total_seconds() / 60)
        if attendance.status != AttendanceStatusEnum.LATE and attendance.status != AttendanceStatusEnum.EARLY_LEAVE:
            attendance.status = AttendanceStatusEnum.OVERTIME

    attendance.check_out_time = now
    attendance.worked_hours = worked_hours
    attendance.early_leave_minutes = early_leave_minutes
    attendance.overtime_minutes = overtime_minutes
    attendance.check_out_lat = lat
    attendance.check_out_lng = lng
    attendance.check_out_distance = distance
    attendance.check_out_score = score

    db.commit()
    db.refresh(attendance)

    # 5. Log Event
    log = AttendanceLog(
        attendance_id=attendance.id,
        employee_id=employee.id,
        action="CHECK_OUT",
        timestamp=now,
        latitude=lat,
        longitude=lng,
        distance=distance,
        recognition_score=score,
        status=attendance.status.value,
        device=device_info,
        ip_address=ip_address
    )
    db.add(log)
    db.commit()

    return attendance
