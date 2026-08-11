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
    store_id: Optional[int] = None,
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
    if store_id:
        query = query.filter(Employee.store_id == store_id)
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
        
        # Translate Department Name
        dept_translated = dept
        if dept and dept != "General":
            dept_lower = dept.lower()
            if "sales" in dept_lower:
                dept_translated = "Савдо зали"
            elif "warehouse" in dept_lower:
                dept_translated = "Омборхона"
            elif "admin" in dept_lower:
                dept_translated = "Маъмурият"
            elif "finance" in dept_lower or "account" in dept_lower:
                dept_translated = "Бухгалтерия"
            elif "cashier" in dept_lower:
                dept_translated = "Касса бўлими"

        emp_name = f"{emp.first_name} {emp.last_name}" if emp else f"ID: {att.employee_id}"
        
        in_str = att.check_in_time.strftime("%Y-%m-%d %H:%M:%S") if att.check_in_time else "—"
        out_str = att.check_out_time.strftime("%Y-%m-%d %H:%M:%S") if att.check_out_time else "—"

        # Status Translation
        status_val = att.status.value if hasattr(att.status, "value") else str(att.status)
        status_translated = status_val
        if status_val == "LATE" or (att.late_minutes and att.late_minutes > 0):
            status_translated = "Кечикди"
        elif status_val == "EARLY_LEAVE" or (att.early_leave_minutes and att.early_leave_minutes > 0):
            status_translated = "Эрта кетди"
        elif status_val in ["ON_TIME", "PRESENT"]:
            status_translated = "Ўз вақтида"
        elif status_val == "EARLY_ARRIVAL":
            status_translated = "Вақтли келди"
        elif status_val == "ABSENT":
            status_translated = "Келмади"
        elif status_val == "OVERTIME":
            status_translated = "Овертайм"

        rows.append({
            "Давомат ID": att.id,
            "Ходим": emp_name,
            "Бўлим": dept_translated,
            "Лавозим": emp.position if emp else "—",
            "Сана": str(att.date),
            "Статус": status_translated,
            "Келиш вақти": in_str,
            "Кетиш вақти": out_str,
            "Иш соати": att.worked_hours or 0,
            "Кечикиш (дақиқа)": att.late_minutes or 0,
            "Эрта кетиш (дақиқа)": att.early_leave_minutes or 0,
            "Вақтли келиш (дақиқа)": getattr(att, "early_arrival_minutes", 0) or 0,
            "Овертайм (дақиқа)": att.overtime_minutes or 0,
            "Масофа (метр)": round(att.check_in_distance or 0.0, 1),
            "FaceID Мослик %": f"{((att.check_in_score or 0) * 100):.1f}%"
        })
    return rows

def generate_csv_report(data: List[Dict[str, Any]]) -> str:
    if not data:
        return "Кўрсатилган фильтр бўйича давомат маълумотлари топилмади."
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()

def generate_excel_report(data: List[Dict[str, Any]]) -> bytes:
    if not data:
        df = pd.DataFrame([{"Хабар": "Маълумот топилмади"}])
    else:
        df = pd.DataFrame(data)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Давомат Ҳисоботи')
    return output.getvalue()

def generate_pdf_report(data: List[Dict[str, Any]], title: str = "Давомат Ҳисоботи") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15, leftMargin=15, topMargin=20, bottomMargin=20)
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
    story.append(Paragraph(f"Ҳисобот вақти: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 15))

    if not data:
        story.append(Paragraph("Кўрсатилган фильтр бўйича маълумот топилмади.", styles['Normal']))
    else:
        # Table Headers in Uzbek
        headers = ["Ходим", "Бўлим", "Сана", "Статус", "Келиш", "Кетиш", "Иш соати", "Кечикиш (мин)"]
        table_data = [headers]

        for row in data:
            check_in_val = str(row.get("Келиш вақти") or row.get("Check In") or "")
            check_out_val = str(row.get("Кетиш вақти") or row.get("Check Out") or "")
            table_data.append([
                str(row.get("Ходим") or row.get("Employee") or ""),
                str(row.get("Бўлим") or row.get("Department") or ""),
                str(row.get("Сана") or row.get("Date") or ""),
                str(row.get("Статус") or row.get("Status") or ""),
                check_in_val.split(" ")[-1] if " " in check_in_val else check_in_val,
                check_out_val.split(" ")[-1] if " " in check_out_val else check_out_val,
                f"{row.get('Иш соати') or row.get('Worked Hours') or 0} соат",
                f"{row.get('Кечикиш (дақиқа)') or row.get('Late (Min)') or 0} мин"
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
