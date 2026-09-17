"""
Shared report data builders used by both the preview endpoint and the
Excel/JSON export endpoint, so the two can never drift.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from models import (
    User, Goal, Initiative, InitiativeAssignment, InitiativeStatus,
    ActivityLog, ActivityAction, Notification, ReviewCycle, ReviewAssignment,
    PerformanceRecord,
)
from schemas.reports import ReportSection, ReportType


def _resolve_window(date_from: Optional[date], date_to: Optional[date]):
    """Convert date bounds to a [start, end) datetime window (UTC)."""
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc) if date_from else None
    end = (datetime.combine(date_to, time.min, tzinfo=timezone.utc)
           + timedelta(days=1)) if date_to else None
    return start, end


def _apply_window(query, column, date_from: Optional[date], date_to: Optional[date]):
    start, end = _resolve_window(date_from, date_to)
    if start:
        query = query.filter(column >= start)
    if end:
        query = query.filter(column < end)
    return query


def _enum(value) -> str:
    if value is None:
        return ""
    return value.value if hasattr(value, "value") else str(value)


def _user_name(user: User) -> str:
    return user.name if user else ""


# ---------------------------------------------------------------- user activity

def _activity_section(db: Session, date_from, date_to, limit: int) -> ReportSection:
    query = db.query(ActivityLog, User) \
        .outerjoin(User, ActivityLog.user_id == User.id) \
        .order_by(ActivityLog.created_at.desc())
    query = _apply_window(query, ActivityLog.created_at, date_from, date_to)
    rows = query.limit(10000).all()

    return ReportSection(
        title="User Activity",
        columns=["Timestamp", "User", "Email", "Action", "Entity Type",
                 "Entity ID", "Details", "IP Address"],
        rows=[
            [
                log.created_at,
                (user.name if user else ""),
                log.user_email or (user.email if user else ""),
                _enum(log.action),
                log.entity_type or "",
                log.entity_id or "",
                log.details or "",
                log.ip_address or "",
            ]
            for log, user in rows
        ],
    )


def _activity_by_action_section(db: Session, date_from, date_to) -> ReportSection:
    query = db.query(ActivityLog.action, func.count(ActivityLog.id))
    query = _apply_window(query, ActivityLog.created_at, date_from, date_to)
    rows = query.group_by(ActivityLog.action).order_by(func.count(ActivityLog.id).desc()).all()
    return ReportSection(
        title="Activity by Action",
        columns=["Action", "Count"],
        rows=[[_enum(a), c] for a, c in rows],
    )


# ---------------------------------------------------------------- logins

def _logins_section(db: Session, date_from, date_to, limit: int) -> ReportSection:
    query = db.query(ActivityLog, User) \
        .outerjoin(User, ActivityLog.user_id == User.id) \
        .filter(ActivityLog.action.in_([ActivityAction.LOGIN, ActivityAction.LOGIN_FAILED])) \
        .order_by(ActivityLog.created_at.desc())
    query = _apply_window(query, ActivityLog.created_at, date_from, date_to)
    rows = query.limit(10000).all()

    return ReportSection(
        title="Login Events",
        columns=["Timestamp", "User", "Email", "Result", "IP Address", "User Agent"],
        rows=[
            [
                log.created_at,
                (user.name if user else ""),
                log.user_email or (user.email if user else ""),
                ("Failed" if log.action == ActivityAction.LOGIN_FAILED else "Success"),
                log.ip_address or "",
                log.user_agent or "",
            ]
            for log, user in rows
        ],
    )


def _daily_logins_section(db: Session, date_from, date_to, days: int) -> ReportSection:
    from routers.analytics import _activity_timeseries
    points = _activity_timeseries(db, days=days)
    return ReportSection(
        title="Daily Logins",
        columns=["Date", "Logins", "Failed Logins", "Active Users"],
        rows=[[p.date, p.logins, p.failed_logins, p.active_users] for p in points],
    )


# ---------------------------------------------------------------- goals

def _goals_section(db: Session, date_from, date_to, organization_id) -> ReportSection:
    query = db.query(Goal) \
        .options(joinedload(Goal.owner), joinedload(Goal.organization)) \
        .order_by(Goal.created_at.desc())
    query = _apply_window(query, Goal.created_at, date_from, date_to)
    if organization_id:
        query = query.filter(Goal.organization_id == organization_id)
    goals = query.limit(10000).all()

    return ReportSection(
        title="Goals",
        columns=["Title", "Scope", "Type", "Status", "Progress %", "Achieved",
                 "Supervisor Score", "Quarter", "Year", "Start Date", "End Date",
                 "Owner", "Organization", "Created At"],
        rows=[
            [
                g.title,
                _enum(g.scope),
                _enum(g.type),
                _enum(g.status),
                g.progress_percentage,
                "Yes" if g.achieved else "No",
                g.supervisor_score,
                _enum(g.quarter),
                g.year,
                g.start_date,
                g.end_date,
                (g.owner.name if g.owner else ""),
                (g.organization.name if g.organization else ""),
                g.created_at,
            ]
            for g in goals
        ],
    )


def _goals_breakdown_sections(db: Session, date_from, date_to, organization_id) -> List[ReportSection]:
    sections = []
    query = db.query(Goal)
    query = _apply_window(query, Goal.created_at, date_from, date_to)
    if organization_id:
        query = query.filter(Goal.organization_id == organization_id)
    base = query
    for column, title in [
        (Goal.status, "Goals by Status"),
        (Goal.scope, "Goals by Scope"),
        (Goal.type, "Goals by Type"),
    ]:
        rows = base.with_entities(column, func.count(Goal.id)).group_by(column).all()
        sections.append(ReportSection(
            title=title,
            columns=["Value", "Count"],
            rows=[[_enum(v), c] for v, c in rows],
        ))
    avg = base.with_entities(func.coalesce(func.avg(Goal.progress_percentage), 0.0)).scalar()
    sections.append(ReportSection(
        title="Goals Summary",
        columns=["Metric", "Value"],
        rows=[
            ["Total goals", base.count()],
            ["Average progress (%)", round(float(avg or 0), 1)],
            ["Achieved", base.filter(Goal.achieved == True).count()],  # noqa: E712
        ],
    ))
    return sections


# ---------------------------------------------------------------- initiatives

def _initiatives_section(db: Session, date_from, date_to, organization_id) -> ReportSection:
    query = db.query(Initiative) \
        .options(joinedload(Initiative.creator), joinedload(Initiative.team_head)) \
        .order_by(Initiative.created_at.desc())
    query = _apply_window(query, Initiative.created_at, date_from, date_to)
    if organization_id:
        query = query.join(
            InitiativeAssignment, InitiativeAssignment.initiative_id == Initiative.id
        ).join(User, InitiativeAssignment.user_id == User.id
        ).filter(User.organization_id == organization_id).distinct()
    rows = query.limit(10000).all()

    return ReportSection(
        title="Initiatives",
        columns=["Title", "Type", "Urgency", "Status", "Due Date", "Score",
                 "Creator", "Team Head", "Completed At", "Created At"],
        rows=[
            [
                i.title,
                _enum(i.type),
                _enum(i.urgency),
                _enum(i.status),
                i.due_date,
                i.score,
                (i.creator.name if i.creator else ""),
                (i.team_head.name if i.team_head else ""),
                i.completed_at,
                i.created_at,
            ]
            for i in rows
        ],
    )


def _initiatives_breakdown_sections(db: Session, date_from, date_to) -> List[ReportSection]:
    base = db.query(Initiative)
    base = _apply_window(base, Initiative.created_at, date_from, date_to)
    sections = []
    for column, title in [
        (Initiative.status, "Initiatives by Status"),
        (Initiative.urgency, "Initiatives by Urgency"),
    ]:
        rows = base.with_entities(column, func.count(Initiative.id)).group_by(column).all()
        sections.append(ReportSection(title=title, columns=["Value", "Count"],
                                      rows=[[_enum(v), c] for v, c in rows]))
    total = base.count()
    completed = base.filter(Initiative.status == InitiativeStatus.COMPLETED).count()
    sections.append(ReportSection(
        title="Initiatives Summary",
        columns=["Metric", "Value"],
        rows=[
            ["Total initiatives", total],
            ["Completed", completed],
            ["Completion rate (%)", round(completed / total * 100, 1) if total else 0.0],
        ],
    ))
    return sections


# ---------------------------------------------------------------- reviews/performance

def _review_cycles_section(db: Session) -> ReportSection:
    cycles = db.query(ReviewCycle).order_by(ReviewCycle.created_at.desc()).limit(100).all()
    stats = db.query(
        ReviewAssignment.cycle_id,
        func.count(ReviewAssignment.id),
        func.count(ReviewAssignment.id).filter(ReviewAssignment.status == 'completed'),
    ).group_by(ReviewAssignment.cycle_id).all()
    by_cycle = {c: (t, d) for c, t, d in stats}

    return ReportSection(
        title="Review Cycles",
        columns=["Name", "Type", "Period", "Status", "Assignments", "Completed",
                 "Completion Rate (%)", "Start", "End"],
        rows=[
            [
                c.name, c.type, c.period, _enum(c.status),
                by_cycle.get(c.id, (0, 0))[0],
                by_cycle.get(c.id, (0, 0))[1],
                round(by_cycle.get(c.id, (0, 0))[1] / by_cycle.get(c.id, (0, 0))[0] * 100, 1)
                if by_cycle.get(c.id, (0, 0))[0] else 0.0,
                c.start_date, c.end_date,
            ]
            for c in cycles
        ],
    )


def _performance_records_section(db: Session, date_from, date_to, organization_id) -> ReportSection:
    query = db.query(PerformanceRecord, User) \
        .join(User, PerformanceRecord.user_id == User.id) \
        .order_by(PerformanceRecord.period_start.desc())
    if organization_id:
        query = query.filter(User.organization_id == organization_id)
    query = _apply_window(query, PerformanceRecord.period_start, date_from, date_to)
    rows = query.limit(10000).all()

    return ReportSection(
        title="Performance Records",
        columns=["User", "Period", "Overall Rating", "Goal Achievement Rate",
                 "Task Completion Rate", "Peer Feedback Score", "Created At"],
        rows=[
            [
                (user.name if user else ""),
                r.period,
                _enum(r.overall_rating),
                r.goal_achievement_rate,
                r.task_completion_rate,
                r.peer_feedback_score,
                r.created_at,
            ]
            for r, user in rows
        ],
    )


# ---------------------------------------------------------------- notifications

def _notifications_section(db: Session, date_from, date_to, limit: int) -> ReportSection:
    query = db.query(Notification, User) \
        .join(User, Notification.user_id == User.id) \
        .order_by(Notification.created_at.desc())
    query = _apply_window(query, Notification.created_at, date_from, date_to)
    rows = query.limit(10000).all()

    return ReportSection(
        title="Notifications",
        columns=["Created At", "User", "Type", "Priority", "Title", "Read"],
        rows=[
            [
                n.created_at,
                (user.name if user else ""),
                _enum(n.type),
                _enum(n.priority),
                n.title,
                "Yes" if n.is_read else "No",
            ]
            for n, user in rows
        ],
    )


def _notifications_by_type_section(db: Session, date_from, date_to) -> ReportSection:
    query = db.query(Notification.type, func.count(Notification.id))
    query = _apply_window(query, Notification.created_at, date_from, date_to)
    rows = query.group_by(Notification.type).all()
    return ReportSection(title="Notifications by Type", columns=["Type", "Count"],
                         rows=[[_enum(v), c] for v, c in rows])


# ---------------------------------------------------------------- users

def _users_section(db: Session) -> ReportSection:
    users = db.query(User) \
        .options(joinedload(User.organization), joinedload(User.role)) \
        .order_by(User.created_at.desc()).limit(10000).all()

    return ReportSection(
        title="Users",
        columns=["Name", "Email", "Organization", "Role", "Level", "Status",
                 "Job Title", "Last Login", "Created At"],
        rows=[
            [
                u.name,
                u.email,
                (u.organization.name if u.organization else ""),
                (u.role.name if u.role else ""),
                u.level,
                _enum(u.status),
                u.job_title or "",
                u.last_login,
                u.created_at,
            ]
            for u in users
        ],
    )


# ---------------------------------------------------------------- dispatcher

def build_report_sections(db: Session, report_type: ReportType,
                          date_from: Optional[date], date_to: Optional[date],
                          organization_id: Optional[UUID]) -> List[ReportSection]:
    """Build all sections for a report type (shared by preview and export)."""
    if report_type == ReportType.USER_ACTIVITY:
        return [
            _activity_section(db, date_from, date_to, None),
            _activity_by_action_section(db, date_from, date_to),
        ]
    if report_type == ReportType.LOGINS:
        from datetime import timedelta
        days = 30
        if date_from and date_to:
            days = (date_to - date_from).days + 1
        return [
            _logins_section(db, date_from, date_to, None),
            _daily_logins_section(db, date_from, date_to, max(1, min(days, 365))),
        ]
    if report_type == ReportType.GOALS:
        return [
            _goals_section(db, date_from, date_to, organization_id),
            *_goals_breakdown_sections(db, date_from, date_to, organization_id),
        ]
    if report_type == ReportType.INITIATIVES:
        return [
            _initiatives_section(db, date_from, date_to, organization_id),
            *_initiatives_breakdown_sections(db, date_from, date_to),
        ]
    if report_type == ReportType.REVIEWS_PERFORMANCE:
        return [
            _review_cycles_section(db),
            _performance_records_section(db, date_from, date_to, organization_id),
        ]
    if report_type == ReportType.NOTIFICATIONS:
        return [
            _notifications_section(db, date_from, date_to, None),
            _notifications_by_type_section(db, date_from, date_to),
        ]
    if report_type == ReportType.ORG_SUMMARY:
        return [
            _users_section(db),
            _activity_by_action_section(db, date_from, date_to),
            _daily_logins_section(db, date_from, date_to, 30),
            *_goals_breakdown_sections(db, date_from, date_to, organization_id),
            *_initiatives_breakdown_sections(db, date_from, date_to),
            _review_cycles_section(db),
        ]
    raise ValueError(f"Unknown report type: {report_type}")


def count_report_rows(sections) -> int:
    return sum(len(s.rows) for s in sections)


REPORT_TYPE_INFO = [
    {"id": ReportType.USER_ACTIVITY, "name": "User Activity",
     "description": "All recorded user actions: logins, goal/initiative/review changes, exports",
     "sections": ["User Activity", "Activity by Action"]},
    {"id": ReportType.LOGINS, "name": "Login Report",
     "description": "Successful and failed logins by day with device/IP details",
     "sections": ["Login Events", "Daily Logins"]},
    {"id": ReportType.GOALS, "name": "Goals Report",
     "description": "All goals with progress, approval and achievement status",
     "sections": ["Goals", "Breakdowns", "Summary"]},
    {"id": ReportType.INITIATIVES, "name": "Initiatives Report",
     "description": "All initiatives with workflow status, urgency and completion",
     "sections": ["Initiatives", "Breakdowns", "Summary"]},
    {"id": ReportType.REVIEWS_PERFORMANCE, "name": "Reviews & Performance",
     "description": "Review cycle participation and consolidated performance records",
     "sections": ["Review Cycles", "Performance Records"]},
    {"id": ReportType.NOTIFICATIONS, "name": "Notifications Report",
     "description": "Notification volume by type and delivery/read status",
     "sections": ["Notifications", "By Type"]},
    {"id": ReportType.ORG_SUMMARY, "name": "Org Summary",
     "description": "One-sheet-per-domain overview of the whole system",
     "sections": ["Users", "Activity", "Goals", "Initiatives", "Reviews"]},
]