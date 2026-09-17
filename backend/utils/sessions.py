"""
Login session tracking service.

One row per platform login (models.LoginSession). The frontend pings
POST /api/auth/heartbeat every ~2 min while a dashboard tab is visible,
which keeps last_active_at fresh. Session duration is computed at read
time as COALESCE(logout_at, last_active_at) - login_at — never stored.

Like utils.activity, every helper here is best-effort: failures are
swallowed and logged so session tracking can never break a business flow.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import LoginSession, User
from utils.activity import get_client_meta

logger = logging.getLogger(__name__)

# A ping interval of ~2 min means an open session whose last_active_at is
# older than this is a closed browser / sleeping laptop, not an idle user.
STALE_AFTER_SECONDS = 600


def _full_name(user: "User") -> str:
    parts = [user.first_name]
    if getattr(user, "middle_name", None):
        parts.append(user.middle_name)
    if user.last_name:
        parts.append(user.last_name)
    return " ".join(p for p in parts if p)


def start_login_session(db: Session, *, user: "User", request=None) -> None:
    """Create a LoginSession row on successful login. Never raises."""
    try:
        ip_address, user_agent = get_client_meta(request)
        db.add(LoginSession(
            user_id=user.id,
            organization_id=getattr(user, "organization_id", None),
            user_email=user.email,
            user_name=_full_name(user),
            ip_address=ip_address,
            user_agent=user_agent,
        ))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("Failed to start login session", exc_info=True)


def close_session_on_logout(db: Session, *, user_id, all_devices: bool = False) -> None:
    """Close the user's open LoginSession row(s) on logout. Never raises."""
    try:
        open_rows = (
            db.query(LoginSession)
            .filter(LoginSession.user_id == user_id,
                    LoginSession.logout_at.is_(None))
        )
        if not all_devices:
            # Single-device logout closes only the most recent open row.
            open_rows = (
                open_rows.order_by(LoginSession.login_at.desc()).limit(1)
            )
        rows = open_rows.all()
        if not rows:
            return
        for row in rows:
            row.logout_at = datetime.now(timezone.utc)
            row.ended_reason = "logout"
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("Failed to close login session on logout", exc_info=True)


def heartbeat(db: Session, *, user: "UserSession" = None, user_id=None, request=None) -> None:
    """
    Refresh the user's open session. Never raises.

    Common path (warm session): 1 SELECT + 1 UPDATE of last_active_at.
    Stale path (browser closed / laptop slept > STALE_AFTER_SECONDS): the
    open row is closed with logout_at = its last_active_at (the offline gap
    is NOT credited as time on platform) and a new session row is inserted.
    """
    try:
        now = datetime.now(timezone.utc)
        if user_id is None and user is not None:
            user_id = getattr(user, "user_id", None) or getattr(user, "id", None)
        session_row = (
            db.query(LoginSession)
            .filter(LoginSession.user_id == user_id,
                    LoginSession.logout_at.is_(None))
            .order_by(LoginSession.login_at.desc())
            .first()
        )

        if session_row is not None:
            last_active = session_row.last_active_at
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)

            if now - last_active <= timedelta(seconds=STALE_AFTER_SECONDS):
                session_row.last_active_at = now
                db.commit()
                return

            # Stale: close the old row, crediting only up to its last ping.
            session_row.logout_at = session_row.last_active_at
            session_row.ended_reason = "stale"

        ip_address, user_agent = get_client_meta(request)
        db.add(LoginSession(
            user_id=user_id,
            user_email=getattr(user, "email", None) if user is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            login_at=now,
            last_active_at=now,
        ))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("Heartbeat failed to update login session", exc_info=True)