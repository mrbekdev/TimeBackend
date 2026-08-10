from datetime import datetime, date, time
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr
from app.models.domain import RoleEnum, AttendanceStatusEnum, NotificationTypeEnum

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    employee_id: Optional[int] = None

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    employee_id: Optional[int] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# --- Department Schemas ---
class DepartmentBase(BaseModel):
    name: str
    description: Optional[str] = None

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentOut(DepartmentBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# --- User & Employee Schemas ---
class UserOut(BaseModel):
    id: int
    username: str
    role: RoleEnum
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    phone: Optional[str] = None
    position: str = "Sales Specialist"
    department_id: Optional[int] = None
    monthly_salary: float = 0.0
    employment_date: Optional[date] = None
    work_start_time: str = "09:00"
    work_end_time: str = "18:00"
    is_active: bool = True

class EmployeeCreate(EmployeeBase):
    username: str
    password: str

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department_id: Optional[int] = None
    monthly_salary: Optional[float] = None
    work_start_time: Optional[str] = None
    work_end_time: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class FaceEncodingOut(BaseModel):
    id: int
    image_path: str
    created_at: datetime

    class Config:
        from_attributes = True

class EmployeeOut(EmployeeBase):
    id: int
    user_id: int
    username: str
    user: UserOut
    department: Optional[DepartmentOut] = None
    profile_photo: Optional[str] = None
    face_count: int = 0
    face_encodings: List[FaceEncodingOut] = []
    created_at: datetime

    class Config:
        from_attributes = True

# Public Employee Summary for Kiosk Dropdown
class KioskEmployeeSummary(BaseModel):
    id: int
    first_name: str
    last_name: str
    position: str
    department_name: Optional[str] = "General"
    profile_photo: Optional[str] = None
    checked_in_today: bool = False
    checked_out_today: bool = False

# --- Store Settings Schemas ---
class StoreSettingsBase(BaseModel):
    store_name: str
    address: str
    latitude: float
    longitude: float
    radius_meters: float
    working_days: str
    timezone: str
    late_tolerance_min: int
    early_leave_tolerance_min: int
    late_penalty_per_min: float = 500.0
    early_bonus_per_min: float = 500.0
    overtime_policy: str
    face_confidence_threshold: float

class StoreSettingsUpdate(StoreSettingsBase):
    pass

class StoreSettingsOut(StoreSettingsBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Express FaceID Attendance Schemas ---
class ExpressAttendanceRequest(BaseModel):
    image_base64: str
    latitude: float
    longitude: float
    action: str  # CHECK_IN or CHECK_OUT
    employee_id: Optional[int] = None

class ExpressAttendanceResponse(BaseModel):
    employee_id: int
    employee_name: str
    position: str
    department_name: str
    action: str
    date: date
    time: str
    status: str
    score: float
    distance: float
    message: str

class AttendanceVerificationRequest(BaseModel):
    image_base64: str
    latitude: float
    longitude: float
    device_info: Optional[str] = "Web Camera & Browser"

class KioskAttendanceRequest(BaseModel):
    employee_id: int
    image_base64: str
    latitude: float
    longitude: float
    action: str  # CHECK_IN or CHECK_OUT
    device_info: Optional[str] = "Store Kiosk Camera"

class ManualAttendanceRequest(BaseModel):
    employee_id: int
    date: date
    check_in_time: Optional[str] = "09:00"
    check_out_time: Optional[str] = "18:00"
    status: Optional[str] = "ON_TIME"
    notes: Optional[str] = "Қўлда киритилди (Админ)"

class AttendanceOut(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    department_name: Optional[str] = None
    date: date
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    status: AttendanceStatusEnum
    worked_hours: float
    late_minutes: int
    early_leave_minutes: int
    early_arrival_minutes: int = 0
    overtime_minutes: int
    check_in_lat: Optional[float] = None
    check_in_lng: Optional[float] = None
    check_in_distance: Optional[float] = None
    check_in_score: Optional[float] = None
    device_info: Optional[str] = None
    ip_address: Optional[str] = None

    class Config:
        from_attributes = True

class AttendanceLogOut(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    action: str
    timestamp: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance: Optional[float] = None
    recognition_score: Optional[float] = None
    status: str
    device: Optional[str] = None

    class Config:
        from_attributes = True


# --- Dashboard & Report Schemas ---
class AdminDashboardStats(BaseModel):
    total_employees: int
    present_today: int
    absent_today: int
    late_today: int
    working_now: int
    attendance_percentage: float
    monthly_late_count: int
    monthly_overtime_hours: float
    recent_attendances: List[AttendanceOut] = []

class EmployeeDashboardStats(BaseModel):
    today_status: Optional[AttendanceOut] = None
    monthly_present: int
    monthly_absent: int
    monthly_late_minutes: int
    monthly_early_minutes: int = 0
    monthly_worked_hours: float
    attendance_percentage: float
    penalty_amount: float = 0.0
    bonus_amount: float = 0.0
    estimated_salary: float
    schedule: str

class NotificationOut(BaseModel):
    id: int
    title: str
    message: str
    type: NotificationTypeEnum
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ReportFilter(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    department_id: Optional[int] = None
    employee_id: Optional[int] = None
