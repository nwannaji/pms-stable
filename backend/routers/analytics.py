"""
Analytics API Router
Org-wide usage analytics (permission-gated) and personal analytics.

All aggregations are done in SQL (func.count / group_by / date_trunc),
with Redis caching of the expensive composite responses.
"""

from datetime import datetime, timedelta, timezone, date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, distinct, desc
from sqlalchemy.orm import Session

from database import get_db
from models import (
    User, UserStatus, Organization, Role, Goal, GoalStatus, Initiative,
    InitiativeStatus, InitiativeAssignment, ActivityLog, ActivityAction, Notification,
    NotificationType, ReviewCycle, ReviewAssignment, PerformanceRecord,
    PerformanceRating, LoginSession,
)
from schemas.auth import UserSession
from schemas.analytics import (
    DailyPoint, NamedCount, TopUser, OrgOverview, GoalBreakdown,
    InitiativeBreakdown, CycleStat, PerformanceBreakdown, BusinessAnalytics,
    MyAnalytics, WeeklyEngagement, SessionStats,
)
from utils.auth import get_current_user
from utils.permissions import UserPermissions, SystemPermissions
from redis_client import cache

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def can_view_org_analytics(user: UserSession, db: Session) -> bool:
    """Org-wide analytics requires reports/audit capability or global scope."""
    if (SystemPermissions.REPORTS_GENERATE in user.permissions
            or SystemPermissions.SYSTEM_ADMIN in user.permissions
            or SystemPermissions.AUDIT_ACCESS in user.permissions):
        return True
    if user.effective_scope == "global":
        return True
    return False


def _cached(key: str, ttl: int, fn):
    """Cache a JSON-serializable response dict via the redis/in-memory layer."""
    try:
        hit = cache.get(key)
        if hit is not None:
            return hit
    except Exception:
        hit = None
    value = fn()
    try:
        cache.set(key, value, ttl=ttl)
    except Exception:
        pass
    return value


def _enum_name(value) -> str:
    """Group-by buckets come back as enum instances — normalize to names."""
    if value is None:
        return "unknown"
    return value.value if hasattr(value, "value") else str(value)


def _day_range(days: int):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return start, end


def _activity_timeseries(db: Session, user_id=None, days: int = 30) -> list:
    """
    Daily login/failed-login/active-user counts over the last N days.
    One grouped SQL query (FILTER aggregates), gap-filled in Python.
    """
    start, _ = _day_range(days)

    base = db.query(
        func.date_trunc("day", ActivityLog.created_at).label("day"),
        func.count(ActivityLog.id).filter(
            ActivityLog.action == ActivityAction.LOGIN).label("logins"),
        func.count(ActivityLog.id).filter(
            ActivityLog.action == ActivityAction.LOGIN_FAILED).label("failed"),
        func.count(func.distinct(ActivityLog.user_id)).label("active"),
    ).filter(ActivityLog.created_at >= start)

    if user_id is not None:
        base = base.filter(ActivityLog.user_id == user_id)

    rows = base.group_by("day").order_by("day").all()

    by_day = {}
    for day, logins, failed, active in rows:
        if day is not None:
            by_day[day.date()] = (logins or 0, failed or 0, active or 0)

    today = datetime.now(timezone.utc).date()
    result = []
    for offset in range(days - 1, -1, -1):
        d = today - timedelta(days=offset)
        logins, failed, active = by_day.get(d, (0, 0, 0))
        result.append(DailyPoint(date=d, logins=logins, failed_logins=failed,
                                 active_users=active))
    return result


# Per-session duration in seconds, computed at read time and capped at 12h
# (a forgotten open tab overnight must not inflate the stats).
def _session_duration_expr():
    return func.least(
        func.extract("epoch",
                     func.coalesce(LoginSession.logout_at, LoginSession.last_active_at)
                     - LoginSession.login_at),
        43200,
    )


def _weekly_engagement(db: Session, days: int = 30) -> list:
    """
    ISO-weekly aggregates over the last N days: distinct logins-per-week
    staff, login counts, and session duration stats. Two grouped SQL
    queries merged + gap-filled in Python (weeks start Monday).
    """
    start, _ = _day_range(days)
    today = datetime.now(timezone.utc).date()
    # First Monday of the window
    first_monday = start.date() - timedelta(days=start.date().weekday())

    counts = dict()
    rows = db.query(
        func.date_trunc("week", LoginSession.login_at).label("week"),
        func.count(LoginSession.id).label("logins"),
        func.count(func.distinct(LoginSession.user_id)).label("users"),
    ).filter(LoginSession.login_at >= start).group_by("week").all()
    for week, logins, users in rows:
        if week is not None:
            counts[week.date()] = (logins or 0, users or 0)

    durations = dict()
    rows = db.query(
        func.date_trunc("week", LoginSession.login_at).label("week"),
        func.avg(_session_duration_expr()).label("avg_secs"),
        func.sum(_session_duration_expr()).label("total_secs"),
    ).filter(LoginSession.login_at >= start).group_by("week").all()
    for week, avg_secs, total_secs in rows:
        if week is not None:
            durations[week.date()] = (
                float(avg_secs or 0), float(total_secs or 0))

    result = []
    monday = first_monday
    while monday <= today:
        logins, users = counts.get(monday, (0, 0))
        avg_secs, total_secs = durations.get(monday, (0.0, 0.0))
        result.append(WeeklyEngagement(
            week_start=monday,
            logins=logins,
            active_users=users,
            avg_session_minutes=round(avg_secs / 60, 1),
            total_session_hours=round(total_secs / 3600, 1),
        ))
        monday += timedelta(days=7)
    return result


def _session_stats(db: Session, days: int = 30) -> "SessionStats":
    """Overall session duration stats over the selected period."""
    start, _ = _day_range(days)
    row = db.query(
        func.count(LoginSession.id).label("count"),
        func.avg(_session_duration_expr()).label("avg_secs"),
        func.sum(_session_duration_expr()).label("total_secs"),
    ).filter(
        LoginSession.login_at >= start,
        LoginSession.user_id.isnot(None),
    ).first()

    count = int(row.count or 0) if row else 0
    avg_secs = float(row.avg_secs or 0) if row else 0.0
    total_secs = float(row.total_secs or 0) if row else 0.0
    return SessionStats(
        sessions_count=count,
        avg_session_minutes=round(avg_secs / 60, 1),
        total_session_hours=round(total_secs / 3600, 1),
    )


def _goal_breakdown(db: Session, organization_id=None, user_id=None) -> GoalBreakdown:
    """Goal counts by status/scope/type + avg progress, overdue, achieved."""
    query = db.query(Goal)
    if organization_id is not None:
        query = query.filter(Goal.organization_id == organization_id)
    if user_id is not None:
        query = query.filter((Goal.owner_id == user_id) | (Goal.created_by == user_id))

    total = query.count()

    def grouped(column):
        rows = query.with_entities(column, func.count(Goal.id)).group_by(column).all()
        return [NamedCount(name=_enum_name(v), count=c) for v, c in rows]

    by_status = grouped(Goal.status)
    by_scope = grouped(Goal.scope)
    by_type = grouped(Goal.type)

    avg_progress = query.with_entities(
        func.coalesce(func.avg(Goal.progress_percentage), 0.0)).scalar() or 0.0

    achieved = query.filter(Goal.achieved == True).count()  # noqa: E712

    open_statuses = [GoalStatus.ACTIVE, GoalStatus.PENDING_APPROVAL]
    overdue = query.filter(
        Goal.end_date.isnot(None),
        Goal.end_date < date.today(),
        Goal.status.in_(open_statuses),
    ).count()

    return GoalBreakdown(
        total=total, by_status=by_status, by_scope=by_scope, by_type=by_type,
        avg_progress=round(float(avg_progress), 1), overdue=overdue, achieved=achieved,
    )


def _initiative_breakdown(db: Session, organization_id=None, user_id=None) -> InitiativeBreakdown:
    """Initiative counts by status/urgency + overdue + completion rate."""
    query = db.query(Initiative)
    if organization_id is not None:
        query = query.join(
            InitiativeAssignment, InitiativeAssignment.initiative_id == Initiative.id
        ).join(User, InitiativeAssignment.user_id == User.id
        ).filter(User.organization_id == organization_id)
    if user_id is not None:
        query = query.filter(
            (Initiative.created_by == user_id)
            | Initiative.id.in_(
                db.query(InitiativeAssignment.initiative_id)
                .filter(InitiativeAssignment.user_id == user_id)
            )
        )

    total = query.count()

    def grouped(column):
        rows = query.with_entities(column, func.count(Initiative.id)).group_by(column).all()
        return [NamedCount(name=_enum_name(v), count=c) for v, c in rows]

    by_status = grouped(Initiative.status)
    by_urgency = grouped(Initiative.urgency)

    completed = query.filter(Initiative.status == InitiativeStatus.COMPLETED).count()
    overdue = query.filter(
        Initiative.due_date < datetime.now(timezone.utc),
        Initiative.status.notin_([InitiativeStatus.COMPLETED, InitiativeStatus.REJECTED]),
    ).count()

    return InitiativeBreakdown(
        total=total, by_status=by_status, by_urgency=by_urgency,
        overdue=overdue, completed=completed,
        completion_rate=round(completed / total * 100, 1) if total else 0.0,
    )


def _notifications_by_type(db: Session, user_id=None, days: int = 30) -> list:
    start, _ = _day_range(days)
    query = db.query(Notification.type, func.count(Notification.id)) \
        .filter(Notification.created_at >= start)
    if user_id is not None:
        query = query.filter(Notification.user_id == user_id)
    rows = query.group_by(Notification.type).all()
    return [NamedCount(name=_enum_name(v), count=c) for v, c in rows]


def _review_cycle_stats(db: Session, days: int = 90) -> list:
    """Participation/completion per review cycle (two aggregate queries, no N+1)."""
    start, _ = _day_range(days)
    cycles = db.query(ReviewCycle).filter(
        ReviewCycle.created_at >= start).order_by(ReviewCycle.created_at.desc()).all()
    if not cycles:
        return []
    cycle_ids = [c.id for c in cycles]

    rows = db.query(
        ReviewAssignment.cycle_id,
        func.count(ReviewAssignment.id).label("total"),
        func.count(ReviewAssignment.id).filter(
            ReviewAssignment.status == 'completed').label("completed"),
    ).filter(ReviewAssignment.cycle_id.in_(cycle_ids)) \
        .group_by(ReviewAssignment.cycle_id).all()

    stats_by_cycle = {r.cycle_id: r for r in rows}
    result = []
    for cycle in cycles:
        row = stats_by_cycle.get(cycle.id)
        total = row.total if row else 0
        completed = row.completed if row else 0
        result.append(CycleStat(
            cycle_id=str(cycle.id),
            cycle_name=cycle.name,
            period=cycle.period,
            assignments=total,
            completed=completed,
            completion_rate=round(completed / total * 100, 1) if total else 0.0,
        ))
    return result


def _performance_breakdown(db: Session, organization_id=None, user_id=None) -> PerformanceBreakdown:
    query = db.query(PerformanceRecord)
    if organization_id is not None:
        query = query.join(User, PerformanceRecord.user_id == User.id) \
            .filter(User.organization_id == organization_id)
    if user_id is not None:
        query = query.filter(PerformanceRecord.user_id == user_id)

    records = query.count()
    rows = query.with_entities(PerformanceRecord.overall_rating, func.count(PerformanceRecord.id)) \
        .group_by(PerformanceRecord.overall_rating).all()
    by_rating = [NamedCount(name=_enum_name(v), count=c) for v, c in rows]
    return PerformanceBreakdown(records=records, by_rating=by_rating)


def _latest_performance(db: Session, user_id) -> dict | None:
    record = db.query(PerformanceRecord).filter(
        PerformanceRecord.user_id == user_id
    ).order_by(PerformanceRecord.period_start.desc()).first()
    if not record:
        return None
    return {
        "period": record.period,
        "overall_rating": _enum_name(record.overall_rating),
        "goal_achievement_rate": record.goal_achievement_rate,
        "task_completion_rate": record.task_completion_rate,
        "peer_feedback_score": record.peer_feedback_score,
    }


@router.get("/overview", response_model=OrgOverview)
def get_org_overview(
    days: int = Query(30, ge=1, le=365),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """System-wide usage analytics. Requires reports_generate/system_admin/audit_access or global scope."""
    if not can_view_org_analytics(current_user, db):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view org analytics")

    key = f"analytics:overview:v2:{days}"
    return _cached(key, 120, lambda: _build_org_overview(db, days))


def _build_org_overview(db: Session, days: int) -> dict:
    start30, _ = _day_range(30)
    start7, _ = _day_range(7)

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.status == UserStatus.ACTIVE).scalar() or 0
    new_users_30d = db.query(func.count(User.id)).filter(User.created_at >= start30).scalar() or 0

    timeseries = _activity_timeseries(db, days=days)

    logins_today = next(
        (p.logins for p in timeseries if p.date == datetime.now(timezone.utc).date()), 0)

    login_rows = db.query(
        func.count(ActivityLog.id).filter(ActivityLog.action == ActivityAction.LOGIN).label("logins"),
        func.count(ActivityLog.id).filter(
            ActivityLog.action == ActivityAction.LOGIN_FAILED).label("failed"),
    ).filter(ActivityLog.created_at >= start30).first()
    logins_30d = login_rows.logins if login_rows else 0
    failed_logins_30d = login_rows.failed if login_rows else 0

    active_7d = db.query(func.count(func.distinct(ActivityLog.user_id))) \
        .filter(ActivityLog.created_at >= start7,
                ActivityLog.user_id.isnot(None)).scalar() or 0
    active_30d = db.query(func.count(func.distinct(ActivityLog.user_id))) \
        .filter(ActivityLog.created_at >= start30,
                ActivityLog.user_id.isnot(None)).scalar() or 0

    def grouped_users(column):
        rows = db.query(column, func.count(User.id)).group_by(column).all()
        return [NamedCount(name=_enum_name(v), count=c) for v, c in rows]

    users_by_status = grouped_users(User.status)
    users_by_level = [
        NamedCount(name=f"Level {v}", count=c)
        for v, c in db.query(User.level, func.count(User.id)).group_by(User.level).all()
        if v is not None
    ]
    users_by_role = [
        NamedCount(name=r, count=c)
        for r, c in db.query(Role.name, func.count(User.id))
        .join(User, User.role_id == Role.id).group_by(Role.name).all()
    ]
    users_by_organization = [
        NamedCount(name=o, count=c)
        for o, c in db.query(Organization.name, func.count(User.id))
        .join(User, User.organization_id == Organization.id)
        .group_by(Organization.name).all()
    ]

    top_rows = db.query(
        User.id, User.name, User.email,
        Organization.name.label("org"), Role.name.label("role"),
        func.count(ActivityLog.id).label("activity_count"),
        func.max(User.last_login).label("last_login"),
    ).join(ActivityLog, ActivityLog.user_id == User.id) \
        .outerjoin(Organization, User.organization_id == Organization.id) \
        .outerjoin(Role, User.role_id == Role.id) \
        .filter(ActivityLog.created_at >= start30) \
        .group_by(User.id, User.name, User.email, Organization.name, Role.name, User.last_login) \
        .order_by(desc("activity_count")) \
        .limit(10).all()

    top_active_users = [
        TopUser(
            user_id=str(r.id), name=r.name, email=r.email,
            organization_name=r.org, role_name=r.role,
            activity_count=r.activity_count, last_login=r.last_login,
        ) for r in top_rows
    ]

    # Session tracking — best-effort so a missing table can never 500 the overview
    try:
        weekly_engagement = _weekly_engagement(db, days=days)
        session_stats = _session_stats(db, days=days)
    except Exception:
        weekly_engagement, session_stats = [], None

    overview = OrgOverview(
        total_users=total_users,
        active_users=active_users,
        inactive_users=total_users - active_users,
        new_users_30d=new_users_30d,
        logins_today=logins_today,
        logins_30d=logins_30d,
        failed_logins_30d=failed_logins_30d,
        active_users_7d=active_7d,
        active_users_30d=active_30d,
        timeseries=timeseries,
        users_by_status=users_by_status,
        users_by_level=users_by_level,
        users_by_role=users_by_role,
        users_by_organization=users_by_organization,
        top_active_users=top_active_users,
        notifications_by_type=_notifications_by_type(db, days=30),
        weekly_engagement=weekly_engagement,
        session_stats=session_stats,
    )
    return overview.model_dump(mode="json")


@router.get("/business", response_model=BusinessAnalytics)
def get_business_analytics(
    days: int = Query(90, ge=1, le=365),
    organization_id: UUID | None = Query(None),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Business-object analytics: goals, initiatives, review cycles, performance."""
    if not can_view_org_analytics(current_user, db):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view org analytics")

    key = f"analytics:business:{days}:{organization_id or 'all'}"
    return _cached(key, 120, lambda: _build_business_analytics(db, days, organization_id))


def _build_business_analytics(db: Session, days: int, organization_id) -> dict:
    analytics = BusinessAnalytics(
        goals=_goal_breakdown(db, organization_id=organization_id),
        initiatives=_initiative_breakdown(db, organization_id=organization_id),
        reviews=_review_cycle_stats(db, days=days),
        performance=_performance_breakdown(db, organization_id=organization_id),
    )
    return analytics.model_dump(mode="json")


@router.get("/me", response_model=MyAnalytics)
def get_my_analytics(
    days: int = Query(30, ge=1, le=90),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Personal analytics for the current user (logins, goals, initiatives)."""
    user_id = current_user.user_id
    key = f"analytics:me:{user_id}:{days}"
    return _cached(key, 60, lambda: _build_my_analytics(db, user_id, days))


def _build_my_analytics(db: Session, user_id, days: int) -> dict:
    total_logins = db.query(func.count(ActivityLog.id)).filter(
        ActivityLog.user_id == user_id,
        ActivityLog.action == ActivityAction.LOGIN,
    ).scalar() or 0

    me = db.query(User).filter(User.id == user_id).first()
    latest = _latest_performance(db, user_id)

    analytics = MyAnalytics(
        last_login=me.last_login if me else None,
        total_logins=total_logins,
        logins_timeseries=_activity_timeseries(db, user_id=user_id, days=days),
        goals=_goal_breakdown(db, user_id=user_id),
        initiatives=_initiative_breakdown(db, user_id=user_id),
        notifications_by_type=_notifications_by_type(db, user_id=user_id, days=days),
        latest_performance=latest,
    )
    return analytics.model_dump(mode="json")


@router.get("/users/{user_id}/activity")
def get_user_activity(
    user_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activity timeseries for a specific user. Self, or admin/user_view_all."""
    is_self = str(user_id) == str(current_user.user_id)
    is_admin = SystemPermissions.SYSTEM_ADMIN in current_user.permissions
    has_view_all = "user_view_all" in current_user.permissions
    if not (is_self or is_admin or has_view_all):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view this user's activity")

    key = f"analytics:user:{user_id}:{days}"
    return _cached(key, 60, lambda: _build_user_activity(db, user_id, days))


def _build_user_activity(db: Session, user_id, days: int) -> dict:
    timeseries = _activity_timeseries(db, user_id=user_id, days=days)
    total_logins = db.query(func.count(ActivityLog.id)).filter(
        ActivityLog.user_id == user_id,
        ActivityLog.action == ActivityAction.LOGIN,
    ).scalar() or 0

    top_actions = [
        NamedCount(name=_enum_name(a), count=c)
        for a, c in db.query(ActivityLog.action, func.count(ActivityLog.id))
        .filter(ActivityLog.user_id == user_id,
                ActivityLog.created_at >= _day_range(days)[0])
        .group_by(ActivityLog.action).all()
    ]

    return {
        "total_logins": total_logins,
        "timeseries": [p.model_dump(mode="json") for p in timeseries],
        "top_actions": [n.model_dump() for n in top_actions],
    }