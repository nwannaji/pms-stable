"""
Notification API Router
Handles notification CRUD operations and WebSocket connections for real-time updates
"""

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import Optional
from datetime import datetime
import json
from uuid import UUID

from database import get_db
from models import Notification, NotificationType, NotificationPriority, User, UserStatus
from schemas.notifications import (
    NotificationResponse, NotificationListResponse,
    NotificationUpdate, NotificationStats
)
from schemas.auth import UserSession
from utils.auth import get_current_user
from utils.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket endpoint for real-time notifications
    Connect with: ws://host/api/notifications/ws?token=<jwt_token>

    Note: We do NOT use Depends(get_db) here because WebSocket connections
    are long-lived. A dependency-injected DB session would expire mid-connection.
    Instead, we create short-lived sessions only when needed for DB operations.
    """
    # Validate token and get user
    # Use a short-lived DB session for authentication only
    from database import SessionLocal
    from jose import jwt, JWTError
    from utils.auth import SECRET_KEY, ALGORITHM
    import uuid as uuid_mod

    auth_db = SessionLocal()
    user_id = None
    try:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id_str: str = payload.get("sub")
            if user_id_str is None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            user_id = uuid_mod.UUID(user_id_str)
        except JWTError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Verify user exists and is active
        user = auth_db.query(User).filter(User.id == user_id).first()
        if not user or user.status != UserStatus.ACTIVE:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    finally:
        # Close the authentication DB session immediately
        auth_db.close()

    # Connect user
    await manager.connect(websocket, user_id)

    try:
        # Send initial connection success message
        await websocket.send_json({
            "type": "connection_established",
            "message": "Connected to notification service",
            "user_id": str(user_id)
        })

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()

            # Handle ping/pong for connection keep-alive
            if data == "ping":
                await websocket.send_text("pong")

            # Handle JSON ping from frontend
            elif data.startswith("{"):
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                except (json.JSONDecodeError, KeyError):
                    pass

            # Handle mark as read requests
            elif data.startswith("mark_read:"):
                # Use a short-lived DB session for this operation
                op_db = SessionLocal()
                try:
                    notification_id = UUID(data.split(":")[1])
                    notification = op_db.query(Notification).filter(
                        Notification.id == notification_id,
                        Notification.user_id == user_id
                    ).first()

                    if notification:
                        notification.is_read = True
                        notification.read_at = datetime.utcnow()
                        op_db.commit()

                        await websocket.send_json({
                            "type": "marked_read",
                            "notification_id": str(notification_id)
                        })
                except Exception as e:
                    logger.error(f"Error marking notification as read: {e}")
                finally:
                    op_db.close()

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info(f"User {user_id} disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    skip: int = 0,
    limit: int = 20,
    unread_only: bool = False,
    notification_type: Optional[NotificationType] = None,
    priority: Optional[NotificationPriority] = None,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's notifications with pagination and filtering
    """
    # Build query
    query = db.query(Notification).filter(Notification.user_id == current_user.user_id)

    # Apply filters
    if unread_only:
        query = query.filter(Notification.is_read == False)

    if notification_type:
        query = query.filter(Notification.type == notification_type)

    if priority:
        query = query.filter(Notification.priority == priority)

    # Remove expired notifications
    query = query.filter(
        or_(
            Notification.expires_at == None,
            Notification.expires_at > datetime.utcnow()
        )
    )

    # Get total count
    total = query.count()

    # Get unread count
    unread_count = db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.is_read == False,
        or_(
            Notification.expires_at == None,
            Notification.expires_at > datetime.utcnow()
        )
    ).count()

    # Get paginated results
    notifications = query.order_by(
        Notification.created_at.desc()
    ).offset(skip).limit(limit).all()

    # Enrich with trigger user names
    notification_responses = []
    for notif in notifications:
        notif_dict = {
            "id": notif.id,
            "type": notif.type,
            "priority": notif.priority,
            "title": notif.title,
            "message": notif.message,
            "action_url": notif.action_url,
            "data": notif.data,
            "user_id": notif.user_id,
            "triggered_by": notif.triggered_by,
            "is_read": notif.is_read,
            "read_at": notif.read_at,
            "created_at": notif.created_at,
            "expires_at": notif.expires_at,
            "triggered_by_name": None
        }

        if notif.triggered_by:
            trigger_user = db.query(User).filter(User.id == notif.triggered_by).first()
            if trigger_user:
                notif_dict["triggered_by_name"] = trigger_user.name

        notification_responses.append(NotificationResponse(**notif_dict))

    return NotificationListResponse(
        notifications=notification_responses,
        total=total,
        unread_count=unread_count,
        page=(skip // limit) + 1 if limit > 0 else 1,
        per_page=limit
    )


@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notification statistics for current user"""

    # Total count
    total_count = db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        or_(
            Notification.expires_at == None,
            Notification.expires_at > datetime.utcnow()
        )
    ).count()

    # Unread count
    unread_count = db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.is_read == False,
        or_(
            Notification.expires_at == None,
            Notification.expires_at > datetime.utcnow()
        )
    ).count()

    # By type
    type_counts = db.query(
        Notification.type,
        func.count(Notification.id)
    ).filter(
        Notification.user_id == current_user.user_id,
        or_(
            Notification.expires_at == None,
            Notification.expires_at > datetime.utcnow()
        )
    ).group_by(Notification.type).all()

    by_type = {str(t): c for t, c in type_counts}

    # By priority
    priority_counts = db.query(
        Notification.priority,
        func.count(Notification.id)
    ).filter(
        Notification.user_id == current_user.user_id,
        or_(
            Notification.expires_at == None,
            Notification.expires_at > datetime.utcnow()
        )
    ).group_by(Notification.priority).all()

    by_priority = {str(p): c for p, c in priority_counts}

    return NotificationStats(
        total_count=total_count,
        unread_count=unread_count,
        by_type=by_type,
        by_priority=by_priority
    )


@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a specific notification as read"""

    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.user_id
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.commit()
    db.refresh(notification)

    # Get trigger user name
    triggered_by_name = None
    if notification.triggered_by:
        trigger_user = db.query(User).filter(User.id == notification.triggered_by).first()
        if trigger_user:
            triggered_by_name = trigger_user.name

    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        priority=notification.priority,
        title=notification.title,
        message=notification.message,
        action_url=notification.action_url,
        data=notification.data,
        user_id=notification.user_id,
        triggered_by=notification.triggered_by,
        is_read=notification.is_read,
        read_at=notification.read_at,
        created_at=notification.created_at,
        expires_at=notification.expires_at,
        triggered_by_name=triggered_by_name
    )


@router.put("/mark-all-read")
async def mark_all_notifications_as_read(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all unread notifications as read"""

    count = db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.is_read == False
    ).update({
        "is_read": True,
        "read_at": datetime.utcnow()
    })

    db.commit()

    return {"message": f"{count} notifications marked as read"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a specific notification"""

    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.user_id
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    db.delete(notification)
    db.commit()

    return {"message": "Notification deleted successfully"}


@router.get("/connection-stats")
async def get_connection_stats(
    current_user: UserSession = Depends(get_current_user)
):
    """Get WebSocket connection statistics (for debugging)"""

    return {
        "active_users": manager.get_active_users_count(),
        "total_connections": manager.get_total_connections_count(),
        "user_online": manager.is_user_online(current_user.user_id)
    }
