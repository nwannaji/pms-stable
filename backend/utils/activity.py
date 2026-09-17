"""
Activity logging service for analytics and audit reporting.

Usage (inside any router, after the successful DB mutation):

    from utils.activity import record_activity, get_client_meta

    ip, user_agent = get_client_meta(request)
    record_activity(
        db, action=ActivityAction.GOAL_CREATE, user=current_user,
        entity_type="goal", entity_id=goal.id, request=request,
        details={"title": goal.title},
    )

Logging is best-effort: failures are swallowed and logged so analytics
can never break a business flow.
"""

import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from models import ActivityLog

logger = logging.getLogger(__name__)


def get_client_meta(request) -> Tuple[str, str]:
    """
    Extract (ip_address, user_agent) from a FastAPI Request.

    Behind the IIS reverse proxy request.client.host is the proxy loopback
    IP, so X-Forwarded-For (first hop) is preferred when present.
    """
    ip_address = None
    user_agent = None
    if request is not None:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        elif request.client is not None:
            ip_address = request.client.host
        user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


def record_activity(
    db: Session,
    *,
    action,
    user=None,
    user_id=None,
    user_email: str = None,
    entity_type: str = None,
    entity_id=None,
    details: dict = None,
    request=None,
    commit: bool = True,
) -> None:
    """
    Record a single activity event. Never raises.

    - `action`: an ActivityAction enum member (models.ActivityAction)
    - `user`: a UserSession/User-like object with .id/.email, or None
    - `user_id`/`user_email`: explicit overrides (failed logins pass
      user_email only — there is no user row to reference)
    - `details`: JSON-serializable dict of extra context
    - `commit`: set False to let the caller's surrounding transaction
      commit the row alongside its own writes
    """
    try:
        ip_address, user_agent = get_client_meta(request)

        resolved_id = user_id
        resolved_email = user_email
        if user is not None:
            if resolved_id is None:
                # ORM User rows use .id; UserSession uses .user_id
                resolved_id = getattr(user, "id", None) or getattr(user, "user_id", None)
            if resolved_email is None:
                resolved_email = getattr(user, "email", None)

        entry = ActivityLog(
            user_id=resolved_id,
            user_email=resolved_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(entry)
        if commit:
            db.commit()
    except Exception:
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass
        logger.warning("Failed to record activity for action=%s", getattr(action, "value", action), exc_info=True)