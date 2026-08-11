from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.domain import User
from app.services.report_service import (
    build_report_query, format_report_data,
    generate_csv_report, generate_excel_report, generate_pdf_report
)

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])

@router.get("/data")
def get_report_data(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    department_id: Optional[int] = None,
    store_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    report_type: str = "daily",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    records = build_report_query(
        db, start_date=start_date, end_date=end_date,
        department_id=department_id, store_id=store_id, employee_id=employee_id,
        report_type=report_type
    )
    formatted = format_report_data(records)
    return {"count": len(formatted), "data": formatted}

@router.get("/export/csv")
def export_csv(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    department_id: Optional[int] = None,
    store_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    report_type: str = "daily",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    records = build_report_query(db, start_date, end_date, department_id, store_id, employee_id, report_type)
    formatted = format_report_data(records)
    csv_str = generate_csv_report(formatted)

    filename = f"attendance_report_{report_type}_{date.today()}.csv"
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/excel")
def export_excel(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    department_id: Optional[int] = None,
    store_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    report_type: str = "daily",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    records = build_report_query(db, start_date, end_date, department_id, store_id, employee_id, report_type)
    formatted = format_report_data(records)
    excel_bytes = generate_excel_report(formatted)

    filename = f"attendance_report_{report_type}_{date.today()}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/pdf")
def export_pdf(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    department_id: Optional[int] = None,
    store_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    report_type: str = "daily",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    records = build_report_query(db, start_date, end_date, department_id, store_id, employee_id, report_type)
    formatted = format_report_data(records)
    pdf_bytes = generate_pdf_report(formatted, title=f"{report_type.capitalize()} Report")

    filename = f"attendance_report_{report_type}_{date.today()}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )
