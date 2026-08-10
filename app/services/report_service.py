import io
import csv
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import pandas as pd

from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.models.domain import Employee, Attendance, Department, AttendanceStatusEnum

def build_report_query(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    department_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    report_type: str = "daily"
):
    query = db.query(Attendance).join(Employee)

    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)

    if report_type == "late":
        query = query.filter(Attendance.late_minutes > 0)
    elif report_type == "overtime":
        query = query.filter(Attendance.overtime_minutes > 0)

    return query.order_by(Attendance.date.desc(), Attendance.id.desc()).all()

def format_report_data(attendances: List[Attendance]) -> List[Dict[str, Any]]:
    rows = []
    for att in attendances:
        emp = att.employee
        dept = emp.department.name if emp and emp.department else "General"
        emp_name = f"{emp.first_name} {emp.last_name}" if emp else f"ID: {att.employee_id}"
        
        in_str = att.check_in_time.strftime("%Y-%m-%d %H:%M:%S") if att.check_in_time else "N/A"
        out_str = att.check_out_time.strftime("%Y-%m-%d %H:%M:%S") if att.check_out_time else "N/A"

        rows.append({
            "Attendance ID": att.id,
            "Employee": emp_name,
            "Department": dept,
            "Position": emp.position if emp else "N/A",
            "Date": str(att.date),
            "Status": att.status.value,
            "Check In": in_str,
            "Check Out": out_str,
            "Worked Hours": att.worked_hours,
            "Late (Min)": att.late_minutes,
            "Early Leave (Min)": att.early_leave_minutes,
            "Early Arrival (Min)": getattr(att, "early_arrival_minutes", 0) or 0,
            "Overtime (Min)": att.overtime_minutes,
            "Distance (m)": att.check_in_distance or 0.0,
            "Face Confidence": f"{((att.check_in_score or 0) * 100):.1f}%"
        })
    return rows

def generate_csv_report(data: List[Dict[str, Any]]) -> str:
    if not data:
        return "No attendance records found for selected filter."
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()

def generate_excel_report(data: List[Dict[str, Any]]) -> bytes:
    if not data:
        df = pd.DataFrame([{"Message": "No data found"}])
    else:
        df = pd.DataFrame(data)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance Report')
    return output.getvalue()

def generate_pdf_report(data: List[Dict[str, Any]], title: str = "Attendance Report") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=12
    )

    story.append(Paragraph(f"TimeWork - {title}", title_style))
    story.append(Paragraph(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 15))

    if not data:
        story.append(Paragraph("No records found for the given criteria.", styles['Normal']))
    else:
        # Table Headers
        headers = ["Emp Name", "Dept", "Date", "Status", "Check In", "Check Out", "Worked (h)", "Late (m)"]
        table_data = [headers]

        for row in data:
            table_data.append([
                row.get("Employee", ""),
                row.get("Department", ""),
                row.get("Date", ""),
                row.get("Status", ""),
                row.get("Check In", "").split(" ")[-1] if row.get("Check In") != "N/A" else "N/A",
                row.get("Check Out", "").split(" ")[-1] if row.get("Check Out") != "N/A" else "N/A",
                str(row.get("Worked Hours", 0)),
                str(row.get("Late (Min)", 0))
            ])

        t = Table(table_data, colWidths=[100, 70, 65, 65, 60, 60, 55, 50])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(t)

    doc.build(story)
    return buffer.getvalue()
