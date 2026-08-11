import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import auth, employees, departments, store, attendance, dashboard, reports, notifications
from app.seed import init_db

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc"
)

# CORS setup for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://aminovwork.uz",
        "http://aminovwork.uz"
    ],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploaded static face images
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(settings.FACES_FOLDER, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_FOLDER)), name="uploads")

# Include Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(employees.router, prefix=settings.API_V1_STR)
app.include_router(departments.router, prefix=settings.API_V1_STR)
app.include_router(store.router, prefix=settings.API_V1_STR)
app.include_router(attendance.router, prefix=settings.API_V1_STR)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)
app.include_router(reports.router, prefix=settings.API_V1_STR)
app.include_router(notifications.router, prefix=settings.API_V1_STR)

def run_db_migrations():
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE store_settings ADD COLUMN late_penalty_per_min FLOAT DEFAULT 500.0"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE store_settings ADD COLUMN early_bonus_per_min FLOAT DEFAULT 500.0"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE attendances ADD COLUMN early_arrival_minutes INTEGER DEFAULT 0"))
            except Exception:
                pass
            conn.commit()
    except Exception as e:
        print("Migration check notice:", e)

@app.on_event("startup")
def startup_event():
    run_db_migrations()
    init_db()
    try:
        from app.core.database import SessionLocal
        from app.services.face_service import migrate_face_encodings
        db = SessionLocal()
        migrate_face_encodings(db)
        db.close()
    except Exception as e:
        print("Startup face encoding migration error:", e)


@app.get("/")
def root():
    return {
        "system": settings.PROJECT_NAME,
        "status": "online",
        "docs": f"{settings.API_V1_STR}/docs"
    }
