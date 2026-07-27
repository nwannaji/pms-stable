from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
import json
import uuid
from datetime import datetime

from database import get_db
from models import User
from utils.websocket_manager import manager, MessageTypes
from utils.auth import verify_token
from redis_client import cache

router = APIRouter()
security = HTTPBearer()

async def get_current_user_websocket(websocket: WebSocket, token: str):
    """Get current user from WebSocket token."""
    try:
        token_data = verify_token(token)
        # Note: In WebSocket, we need to create a new DB session
        from database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == token_data.username).first()
            if not user or not user.is_active:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return None
            return user
        finally:
            db.close()
    except:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """Main WebSocket endpoint for real-time communication."""
    # Authenticate user
    user = await get_current_user_websocket(websocket, token)
    if not user:
        return
    
    connection_id = str(uuid.uuid4())
    
    try:
        # Connect user
        await manager.connect(websocket, user.id, connection_id)
        
        # Send welcome message
        welcome_message = {
            "type": "connection_established",
            "data": {
                "user_id": user.id,
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        # Main message loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Update user activity
                await manager.update_user_activity(user.id)
                
                # Handle different message types
                await handle_websocket_message(websocket, user, message, connection_id)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                # Send error message for invalid JSON
                error_message = {
                    "type": "error",
                    "data": {
                        "message": "Invalid JSON format",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                await websocket.send_text(json.dumps(error_message))
            except Exception as e:
                # Log error and send generic error message
                print(f"WebSocket error for user {user.id}: {e}")
                error_message = {
                    "type": "error",
                    "data": {
                        "message": "An error occurred processing your message",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                try:
                    await websocket.send_text(json.dumps(error_message))
                except:
                    break
    
    except Exception as e:
        print(f"WebSocket connection error: {e}")
    
    finally:
        # Disconnect user
        await manager.disconnect(user.id, connection_id)

async def handle_websocket_message(websocket: WebSocket, user: User, message: dict, connection_id: str):
    """Handle incoming WebSocket messages."""
    message_type = message.get("type")
    data = message.get("data", {})
    
    if message_type == MessageTypes.PING:
        # Respond to ping with pong
        pong_message = {
            "type": MessageTypes.PONG,
            "data": {
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        await websocket.send_text(json.dumps(pong_message))
    
    elif message_type == "join_room":
        # Join a room for group communication
        room_name = data.get("room")
        if room_name:
            await manager.join_room(user.id, room_name)
            
            # Confirm room join
            response = {
                "type": "room_joined",
                "data": {
                    "room": room_name,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            await websocket.send_text(json.dumps(response))
    
    elif message_type == "leave_room":
        # Leave a room
        room_name = data.get("room")
        if room_name:
            await manager.leave_room(user.id, room_name)
            
            # Confirm room leave
            response = {
                "type": "room_left",
                "data": {
                    "room": room_name,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            await websocket.send_text(json.dumps(response))
    
    elif message_type == "chat_message":
        # Handle chat message
        room_name = data.get("room")
        message_content = data.get("message")
        
        if room_name and message_content:
            chat_message = {
                "type": MessageTypes.CHAT_MESSAGE,
                "data": {
                    "room": room_name,
                    "message": message_content,
                    "sender": {
                        "id": user.id,
                        "name": f"{user.first_name} {user.last_name}",
                        "username": user.username
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            # Broadcast to room (excluding sender)
            await manager.broadcast_to_room(chat_message, room_name, exclude_user=user.id)
    
    elif message_type == "typing_indicator":
        # Handle typing indicator
        room_name = data.get("room")
        is_typing = data.get("is_typing", False)
        
        if room_name:
            typing_message = {
                "type": MessageTypes.TYPING_INDICATOR,
                "data": {
                    "room": room_name,
                    "user": {
                        "id": user.id,
                        "name": f"{user.first_name} {user.last_name}"
                    },
                    "is_typing": is_typing,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            # Broadcast to room (excluding sender)
            await manager.broadcast_to_room(typing_message, room_name, exclude_user=user.id)
    
    elif message_type == "get_online_users":
        # Send list of online users
        online_users = await manager.get_online_users()
        
        response = {
            "type": "online_users",
            "data": {
                "users": online_users,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        await websocket.send_text(json.dumps(response))
    
    elif message_type == "subscribe_notifications":
        # Subscribe to notification types
        notification_types = data.get("types", [])
        
        # Store subscription preferences in cache
        cache_key = f"notification_subscriptions:{user.id}"
        cache.set(cache_key, notification_types, ttl=86400)  # 24 hours
        
        response = {
            "type": "subscriptions_updated",
            "data": {
                "notification_types": notification_types,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        await websocket.send_text(json.dumps(response))
    
    else:
        # Unknown message type
        error_message = {
            "type": "error",
            "data": {
                "message": f"Unknown message type: {message_type}",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        await websocket.send_text(json.dumps(error_message))

# REST endpoints for WebSocket management
@router.get("/online-users")
async def get_online_users(current_user: User = Depends(get_current_user_websocket)):
    """Get list of currently online users."""
    online_users = await manager.get_online_users()
    return {"online_users": online_users}

@router.post("/broadcast")
async def broadcast_message(
    message: dict,
    current_user: User = Depends(get_current_user_websocket)
):
    """Broadcast message to all online users (SuperAdmin only)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SuperAdmin can broadcast messages"
        )
    
    online_users = await manager.get_online_users()
    await manager.broadcast_to_users(message, online_users)
    
    return {
        "message": "Message broadcasted successfully",
        "recipients": len(online_users)
    }

@router.post("/send-notification")
async def send_notification_to_user(
    user_id: int,
    notification: dict,
    current_user: User = Depends(get_current_user_websocket)
):
    """Send notification to a specific user."""
    # Check permissions (implement based on your requirements)
    
    notification_message = {
        "type": MessageTypes.NOTIFICATION,
        "data": {
            **notification,
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    await manager.send_personal_message(notification_message, user_id)
    
    return {"message": "Notification sent successfully"}