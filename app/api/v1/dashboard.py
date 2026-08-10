from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import require_admin, require_employee, get_current_user
from app.models.domain import User, Employee
from app.schemas.domain_schemas import AdminDashboardStats, EmployeeDashboardStats
from app.services.dashboard_service import get_admin_dashboard_metrics, get_employee_dashboard_metrics

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/admin", response_model=AdminDashboardStats)
def admin_dashboard(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    return get_admin_dashboard_metrics(db)

@router.get("/employee", response_model=EmployeeDashboardStats)
def employee_dashboard(
    db: Session = Depends(get_db),
    employee: Employee = Depends(require_employee)
):
    return get_employee_dashboard_metrics(db, employee)
