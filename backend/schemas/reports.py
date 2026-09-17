"""
Report schemas for preview and export.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel


class ReportType(str, Enum):
    USER_ACTIVITY = "user_activity"
    LOGINS = "logins"
    GOALS = "goals"
    INITIATIVES = "initiatives"
    REVIEWS_PERFORMANCE = "reviews_performance"
    NOTIFICATIONS = "notifications"
    ORG_SUMMARY = "org_summary"


class ReportSection(BaseModel):
    """One tabular section — one Excel sheet per section."""
    title: str
    columns: List[str]
    rows: List[List[Any]]


class ReportPreview(BaseModel):
    report_type: ReportType
    generated_at: datetime
    filters: Dict[str, Any]
    total_rows: int
    sections: List[ReportSection]


class ReportTypeInfo(BaseModel):
    id: ReportType
    name: str
    description: str
    sections: List[str]