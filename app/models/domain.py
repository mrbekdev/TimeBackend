from datetime import datetime, date, time
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, Time, DateTime, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    EMPLOYEE = "EMPLOYEE"

class AttendanceStatusEnum(str, enum.Enum):
    ON_TIME = "ON_TIME"
    LATE = "LATE"
    EARLY_LEAVE = "EARLY_LEAVE"
    EARLY_ARRIVAL = "EARLY_ARRIVAL"
    ABSENT = "ABSENT"
    OVERTIME = "OVERTIME"

class NotificationTypeEnum(str, enum.Enum):
    LATE_WARNING = "LATE_WARNING"
    OUTSIDE_STORE = "OUTSIDE_STORE"
    MISSING_CHECKOUT = "MISSING_CHECKOUT"
    ATTENDANCE_SUCCESS = "ATTENDANCE_SUCCESS"
    ADMIN_ALERT = "ADMIN_ALERT"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(RoleEnum), default=RoleEnum.EMPLOYEE, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    employees = relationship("Employee", back_populates="department")

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(30), nullable=True)
    position = Column(String(100), nullable=False, default="Sales Specialist")
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    store_id = Column(Integer, ForeignKey("store_settings.id", ondelete="SET NULL"), nullable=True)
    monthly_salary = Column(Float, default=0.0, nullable=False)
    employment_date = Column(Date, default=date.today, nullable=False)
    work_start_time = Column(Time, default=time(9, 0), nullable=False)
    work_end_time = Column(Time, default=time(18, 0), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    profile_photo = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="employee")
    department = relationship("Department", back_populates="employees")
    store = relationship("StoreSettings", back_populates="employees")
    face_encodings = relationship("FaceEncoding", back_populates="employee", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="employee", cascade="all, delete-orphan")

class FaceEncoding(Base):
    __tablename__ = "face_encodings"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    image_path = Column(String(255), nullable=False)
    encoding_data = Column(JSON, nullable=False)  # List of float encoding values
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="face_encodings")

class StoreSettings(Base):
    __tablename__ = "store_settings"

    id = Column(Integer, primary_key=True, index=True)
    store_name = Column(String(150), default="TechStore Electronics Hub", nullable=False)
    address = Column(String(255), default="128 Tech Boulevard, Electronics City", nullable=False)
    latitude = Column(Float, default=41.311081, nullable=False)  # Default coordinates
    longitude = Column(Float, default=69.240562, nullable=False)
    radius_meters = Column(Float, default=150.0, nullable=False) # Allowed radius in meters
    working_days = Column(String(100), default="Monday,Tuesday,Wednesday,Thursday,Friday,Saturday", nullable=False)
    timezone = Column(String(50), default="Asia/Tashkent", nullable=False)
    late_tolerance_min = Column(Integer, default=15, nullable=False)
    early_leave_tolerance_min = Column(Integer, default=15, nullable=False)
    late_penalty_per_min = Column(Float, default=500.0, nullable=False) # Jarima summa (so'm / min)
    early_bonus_per_min = Column(Float, default=500.0, nullable=False)  # Bonus summa (so'm / min)
    overtime_policy = Column(String(100), default="Standard 1.5x Hourly Rate", nullable=False)
    face_confidence_threshold = Column(Float, default=0.75, nullable=False) # 75% similarity threshold
    is_active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employees = relationship("Employee", back_populates="store")
    attendances = relationship("Attendance", back_populates="store")

class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    store_id = Column(Integer, ForeignKey("store_settings.id", ondelete="SET NULL"), nullable=True)
    date = Column(Date, default=date.today, index=True, nullable=False)
    check_in_time = Column(DateTime, nullable=True)
    check_out_time = Column(DateTime, nullable=True)
    status = Column(SQLEnum(AttendanceStatusEnum), default=AttendanceStatusEnum.ON_TIME, nullable=False)
    worked_hours = Column(Float, default=0.0, nullable=False)
    late_minutes = Column(Integer, default=0, nullable=False)
    early_leave_minutes = Column(Integer, default=0, nullable=False)
    early_arrival_minutes = Column(Integer, default=0, nullable=False)
    overtime_minutes = Column(Integer, default=0, nullable=False)
    check_in_lat = Column(Float, nullable=True)
    check_in_lng = Column(Float, nullable=True)
    check_out_lat = Column(Float, nullable=True)
    check_out_lng = Column(Float, nullable=True)
    check_in_distance = Column(Float, nullable=True)
    check_out_distance = Column(Float, nullable=True)
    check_in_score = Column(Float, nullable=True)
    check_out_score = Column(Float, nullable=True)
    device_info = Column(String(255), nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="attendances")
    store = relationship("StoreSettings", back_populates="attendances")
    logs = relationship("AttendanceLog", back_populates="attendance", cascade="all, delete-orphan")

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id = Column(Integer, primary_key=True, index=True)
    attendance_id = Column(Integer, ForeignKey("attendances.id", ondelete="CASCADE"), nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(50), nullable=False) # CHECK_IN or CHECK_OUT
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    distance = Column(Float, nullable=True)
    recognition_score = Column(Float, nullable=True)
    status = Column(String(50), nullable=False)
    device = Column(String(255), nullable=True)
    browser = Column(String(255), nullable=True)
    ip_address = Column(String(50), nullable=True)

    attendance = relationship("Attendance", back_populates="logs")
    employee = relationship("Employee")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(SQLEnum(NotificationTypeEnum), default=NotificationTypeEnum.ADMIN_ALERT, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="notifications")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    entity = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")
