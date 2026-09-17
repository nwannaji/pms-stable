"""
Analytics response schemas for org-wide and personal analytics.
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class DailyPoint(BaseModel):
    """One day of activity data (gap-filled with zeros for missing days)."""
    date: date
    logins: int = 0
    failed_logins: int = 0
    active_users: int = 0


class NamedCount(BaseModel):
    name: str
    count: int


class TopUser(BaseModel):
    user_id: str
    name: str
    email: str
    organization_name: Optional[str] = None
    role_name: Optional[str] = None
    activity_count: int
    last_login: Optional[datetime] = None


class WeeklyEngagement(BaseModel):
    """One ISO week of login/engagement data (gap-filled)."""
    week_start: date  # Monday
    logins: int = 0
    active_users: int = 0
    avg_session_minutes: float = 0.0
    total_session_hours: float = 0.0


class SessionStats(BaseModel):
    """Aggregated login-session durations over the selected period."""
    sessions_count: int = 0
    avg_session_minutes: float = 0.0
    total_session_hours: float = 0.0


class OrgOverview(BaseModel):
    """System-wide usage analytics (permission-gated)."""
    total_users: int
    active_users: int  # status == ACTIVE
    inactive_users: int
    new_users_30d: int
    logins_today: int
    logins_30d: int
    failed_logins_30d: int
    active_users_7d: int
    active_users_30d: int
    timeseries: List[DailyPoint]
    users_by_status: List[NamedCount]
    users_by_level: List[NamedCount]
    users_by_role: List[NamedCount]
    users_by_organization: List[NamedCount]
    top_active_users: List[TopUser]
    notifications_by_type: List[NamedCount]
    # Session-tracking fields (defaulted so stale cached payloads still validate)
    weekly_engagement: List[WeeklyEngagement] = []
    session_stats: Optional[SessionStats] = None


class GoalBreakdown(BaseModel):
    total: int
    by_status: List[NamedCount]
    by_scope: List[NamedCount]
    by_type: List[NamedCount]
    avg_progress: float
    overdue: int
    achieved: int


class InitiativeBreakdown(BaseModel):
    total: int
    by_status: List[NamedCount]
    by_urgency: List[NamedCount]
    overdue: int
    completed: int
    completion_rate: float


class CycleStat(BaseModel):
    cycle_id: str
    cycle_name: str
    period: str
    assignments: int
    completed: int
    completion_rate: float


class PerformanceBreakdown(BaseModel):
    records: int
    by_rating: List[NamedCount]


class BusinessAnalytics(BaseModel):
    goals: GoalBreakdown
    initiatives: InitiativeBreakdown
    reviews: List[CycleStat]
    performance: PerformanceBreakdown


class MyAnalytics(BaseModel):
    last_login: Optional[datetime] = None
    total_logins: int
    logins_timeseries: List[DailyPoint]
    goals: GoalBreakdown
    initiatives: InitiativeBreakdown
    notifications_by_type: List[NamedCount]
    latest_performance: Optional[Dict[str, Any]] = None