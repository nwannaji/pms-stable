"""
Reports API Router
Report type listing, preview, and Excel/JSON export.
"""

import json
from datetime import date, datetime, timezone
from typing import Optional, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from database import get_db
from schemas.auth import UserSession
from schemas.reports import ReportType, ReportPreview, ReportTypeInfo
from utils.auth import get_current_user
from utils.activity import record_activity
from utils.permissions import SystemPermissions
from utils.report_data import (
    build_report_sections, count_report_rows, REPORT_TYPE_INFO,
)
from utils.excel import build_workbook, XLSX_MEDIA_TYPE
from models import ActivityAction

router = APIRouter(prefix="/reports", tags=["Reports"])


def _require_report_permission(current_user: UserSession):
    if not (SystemPermissions.REPORTS_GENERATE in current_user.permissions
            or SystemPermissions.SYSTEM_ADMIN in current_user.permissions):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to generate reports (reports_generate required)")


def _report_name(report_type: ReportType, ext: str) -> str:
    return f"pms-{report_type.value.replace('_', '-')}-report-{date.today():%Y-%m-%d}.{ext}"


def _content_disposition(filename: str) -> str:
    """ASCII filename + RFC 5987 UTF-8 form (most reliable behind IIS)."""
    ascii_name = filename.encode("ascii", "ignore").decode() or filename
    return (f"attachment; filename=\"{ascii_name}\"; "
            f"filename*=UTF-8''{quote(filename)}")


@router.get("/types", response_model=list[ReportTypeInfo])
def list_report_types(
    current_user: UserSession = Depends(get_current_user),
):
    """List available report types (any authenticated user)."""
    return [ReportTypeInfo(**info) for info in REPORT_TYPE_INFO]


@router.get("/preview", response_model=ReportPreview)
def preview_report(
    type: ReportType = Query(...),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    organization_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserSession = Depends(get_current_user),
    db=Depends(get_db),
):
    """Preview the first rows of a report before exporting."""
    _require_report_permission(current_user)

    sections = build_report_sections(db, type, date_from, date_to, organization_id)

    # Truncate rows to the preview limit, distributed across sections
    preview_sections = []
    for section in sections:
        preview_sections.append(section.model_copy(
            update={"rows": section.rows[:limit]}))

    return ReportPreview(
        report_type=type,
        generated_at=datetime.now(timezone.utc),
        filters={
            "date_from": date_from, "date_to": date_to,
            "organization_id": str(organization_id) if organization_id else None,
        },
        total_rows=count_report_rows(sections),
        sections=preview_sections,
    )


@router.get("/export")
def export_report(
    type: ReportType = Query(...),
    format: Literal["xlsx", "json"] = Query("xlsx"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    organization_id: Optional[UUID] = Query(None),
    current_user: UserSession = Depends(get_current_user),
    db=Depends(get_db),
    request: Request = None,
):
    """Download a report as an Excel workbook or JSON document."""
    _require_report_permission(current_user)

    sections = build_report_sections(db, type, date_from, date_to, organization_id)
    total_rows = count_report_rows(sections)

    filters = {
        "date_from": date_from, "date_to": date_to,
        "organization_id": str(organization_id) if organization_id else None,
    }

    record_activity(
        db, action=ActivityAction.REPORT_EXPORT, user=current_user,
        entity_type="report", request=request, details={
            "type": type.value, "format": format,
            "rows": total_rows, "filters": filters,
        },
    )

    if format == "json":
        payload = ReportPreview(
            report_type=type,
            generated_at=datetime.now(timezone.utc),
            filters=filters,
            total_rows=total_rows,
            sections=sections,
        )
        content = json.dumps(payload.model_dump(mode="json"), default=str)
        filename = _report_name(type, "json")
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": _content_disposition(filename)},
        )

    workbook = build_workbook(
        sections, title=f"PMS {type.value.replace('_', ' ').title()} Report",
        filters=filters, generated_by=current_user.email,
    )
    filename = _report_name(type, "xlsx")
    return StreamingResponse(
        iter([workbook]),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": _content_disposition(filename),
                 "Content-Length": str(len(workbook))},
    )