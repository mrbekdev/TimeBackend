from datetime import datetime, date, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.domain import Employee, Attendance, AttendanceStatusEnum, User, StoreSettings
from app.schemas.domain_schemas import AdminDashboardStats, EmployeeDashboardStats, AttendanceOut

def get_admin_dashboard_metrics(db: Session) -> AdminDashboardStats:
    today = date.today()
    total_employees = db.query(Employee).filter(Employee.is_active == True).count()

    attendances_today = db.query(Attendance).filter(Attendance.date == today).all()
    present_today = len(attendances_today)
    absent_today = max(0, total_employees - present_today)
    
    late_today = sum(1 for a in attendances_today if a.status == AttendanceStatusEnum.LATE or a.late_minutes > 0)
    working_now = sum(1 for a in attendances_today if a.check_in_time is not None and a.check_out_time is None)

    attendance_pct = round((present_today / total_employees * 100.0), 1) if total_employees > 0 else 0.0

    # Monthly aggregations
    first_day_month = today.replace(day=1)
    monthly_attendances = db.query(Attendance).filter(Attendance.date >= first_day_month).all()
    
    monthly_late_count = sum(1 for a in monthly_attendances if a.late_minutes > 0)
    monthly_overtime_hours = round(sum(a.overtime_minutes for a in monthly_attendances) / 60.0, 1)

    # Recent attendances formatted
    recent_query = db.query(Attendance).order_by(Attendance.id.desc()).limit(10).all()
    recent_list = []
    for att in recent_query:
        emp = att.employee
        dept_name = emp.department.name if emp and emp.department else "General"
        emp_name = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"
        
        recent_list.append(AttendanceOut(
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
            early_arrival_minutes=getattr(att, 'early_arrival_minutes', 0),
            overtime_minutes=att.overtime_minutes,
            check_in_lat=att.check_in_lat,
            check_in_lng=att.check_in_lng,
            check_in_distance=att.check_in_distance,
            check_in_score=att.check_in_score,
            device_info=att.device_info,
            ip_address=att.ip_address
        ))

    return AdminDashboardStats(
        total_employees=total_employees,
        present_today=present_today,
        absent_today=absent_today,
        late_today=late_today,
        working_now=working_now,
        attendance_percentage=attendance_pct,
        monthly_late_count=monthly_late_count,
        monthly_overtime_hours=monthly_overtime_hours,
        recent_attendances=recent_list
    )

def get_employee_dashboard_metrics(db: Session, employee: Employee) -> EmployeeDashboardStats:
    today = date.today()
    
    # Today attendance
    today_att = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date == today
    ).first()

    today_out = None
    if today_att:
        today_out = AttendanceOut(
            id=today_att.id,
            employee_id=today_att.employee_id,
            employee_name=f"{employee.first_name} {employee.last_name}",
            department_name=employee.department.name if employee.department else "General",
            date=today_att.date,
            check_in_time=today_att.check_in_time,
            check_out_time=today_att.check_out_time,
            status=today_att.status,
            worked_hours=today_att.worked_hours,
            late_minutes=today_att.late_minutes,
            early_leave_minutes=today_att.early_leave_minutes,
            early_arrival_minutes=getattr(today_att, 'early_arrival_minutes', 0),
            overtime_minutes=today_att.overtime_minutes,
            check_in_lat=today_att.check_in_lat,
            check_in_lng=today_att.check_in_lng,
            check_in_distance=today_att.check_in_distance,
            check_in_score=today_att.check_in_score,
            device_info=today_att.device_info,
            ip_address=today_att.ip_address
        )

    # Monthly Stats
    first_day_month = today.replace(day=1)
    monthly_records = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date >= first_day_month
    ).all()

    monthly_present = len(monthly_records)
    monthly_worked_hours = round(sum(r.worked_hours for r in monthly_records), 1)
    monthly_late_minutes = sum(r.late_minutes for r in monthly_records)
    monthly_early_minutes = sum((getattr(r, 'early_arrival_minutes', 0) + r.overtime_minutes) for r in monthly_records)

    # Total working days up to today in current month
    passed_days = today.day
    working_days_count = max(1, passed_days)
    monthly_absent = max(0, working_days_count - monthly_present)

    att_pct = round((monthly_present / working_days_count) * 100.0, 1)

    # Store settings for late penalty rate and early bonus rate (in So'm)
    store = db.query(StoreSettings).first()
    late_penalty_rate = store.late_penalty_per_min if (store and store.late_penalty_per_min is not None) else 500.0
    early_bonus_rate = store.early_bonus_per_min if (store and store.early_bonus_per_min is not None) else 500.0

    penalty_amount = monthly_late_minutes * late_penalty_rate
    bonus_amount = monthly_early_minutes * early_bonus_rate

    # Estimated pro-rated salary calculation (in So'm)
    # Base daily rate = monthly_salary / 22 working days
    base_daily = employee.monthly_salary / 22.0
    earned_base = monthly_present * base_daily
    estimated_salary = max(0.0, round(earned_base - penalty_amount + bonus_amount, 2))

    start_str = employee.work_start_time.strftime("%H:%M")
    end_str = employee.work_end_time.strftime("%H:%M")
    schedule = f"Monday - Saturday: {start_str} - {end_str}"

    return EmployeeDashboardStats(
        today_status=today_out,
        monthly_present=monthly_present,
        monthly_absent=monthly_absent,
        monthly_late_minutes=monthly_late_minutes,
        monthly_early_minutes=monthly_early_minutes,
        monthly_worked_hours=monthly_worked_hours,
        attendance_percentage=att_pct,
        penalty_amount=round(penalty_amount, 2),
        bonus_amount=round(bonus_amount, 2),
        estimated_salary=estimated_salary,
        schedule=schedule
    )
