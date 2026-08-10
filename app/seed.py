import os
from datetime import datetime, date, time
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.core.security import get_password_hash
from app.models.domain import (
    User, Employee, Department, StoreSettings, 
    FaceEncoding, RoleEnum, Attendance, AttendanceStatusEnum
)
import numpy as np

def init_db():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Seed Store Settings
        store = db.query(StoreSettings).first()
        if not store:
            store = StoreSettings(
                store_name="TechStore Electronics Central",
                address="128 Innovation Boulevard, Tech District",
                latitude=41.311081,
                longitude=69.240562,
                radius_meters=200.0,
                working_days="Monday,Tuesday,Wednesday,Thursday,Friday,Saturday",
                timezone="Asia/Tashkent",
                late_tolerance_min=15,
                early_leave_tolerance_min=15,
                overtime_policy="Standard 1.5x Hourly Rate",
                face_confidence_threshold=0.42
            )
            db.add(store)
            print("✓ Store settings initialized.")

        # 2. Seed Departments
        dept_names = ["Sales Floor", "Inventory & Logistics", "Customer Support", "Store Management", "Tech Service"]
        depts = {}
        for name in dept_names:
            d = db.query(Department).filter(Department.name == name).first()
            if not d:
                d = Department(name=name, description=f"{name} department of TechStore Electronics")
                db.add(d)
                db.flush()
            depts[name] = d
        print("✓ Departments initialized.")

        # 3. Seed Admin User
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role=RoleEnum.ADMIN,
                is_active=True
            )
            db.add(admin_user)
            db.flush()
            print("✓ Admin user created (admin / admin123).")

        # 4. Seed Demo Employees
        demo_employees = [
            {
                "username": "alex.wright",
                "password": "user123",
                "first_name": "Alexander",
                "last_name": "Wright",
                "phone": "+1 (555) 234-5678",
                "position": "Senior Electronics Sales Lead",
                "dept": depts["Sales Floor"],
                "salary": 1800.0,
                "start": time(9, 0),
                "end": time(18, 0)
            },
            {
                "username": "elena.rostova",
                "password": "user123",
                "first_name": "Elena",
                "last_name": "Rostova",
                "phone": "+1 (555) 345-6789",
                "position": "Inventory Specialist",
                "dept": depts["Inventory & Logistics"],
                "salary": 1500.0,
                "start": time(8, 30),
                "end": time(17, 30)
            },
            {
                "username": "david.chen",
                "password": "user123",
                "first_name": "David",
                "last_name": "Chen",
                "phone": "+1 (555) 456-7890",
                "position": "Technical Repair Specialist",
                "dept": depts["Tech Service"],
                "salary": 1950.0,
                "start": time(9, 0),
                "end": time(18, 0)
            }
        ]

        for data in demo_employees:
            u = db.query(User).filter(User.username == data["username"]).first()
            if not u:
                u = User(
                    username=data["username"],
                    password_hash=get_password_hash(data["password"]),
                    role=RoleEnum.EMPLOYEE,
                    is_active=True
                )
                db.add(u)
                db.flush()

                emp = Employee(
                    user_id=u.id,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    phone=data["phone"],
                    position=data["position"],
                    department_id=data["dept"].id,
                    monthly_salary=data["salary"],
                    employment_date=date(2025, 1, 15),
                    work_start_time=data["start"],
                    work_end_time=data["end"],
                    is_active=True
                )
                db.add(emp)
                db.flush()

                # Generate synthetic normalized feature vector for instant camera matching test
                dummy_vec = np.random.uniform(0.0, 1.0, 192)
                dummy_vec = (dummy_vec / np.linalg.norm(dummy_vec)).tolist()

                face = FaceEncoding(
                    employee_id=emp.id,
                    image_path="/uploads/faces/sample_face.jpg",
                    encoding_data=dummy_vec
                )
                db.add(face)
                print(f"✓ Employee created ({data['username']} / user123).")

        db.commit()
        print("✓ Database initialization and seeding completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
