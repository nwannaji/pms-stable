"""
Authentication API Router
Based on CLAUDE.md specification with onboarding flow
Supports refresh token pattern for extended sessions
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import timedelta, datetime, timezone
from pydantic import BaseModel
from typing import Optional
import logging
import os

from database import get_db
from models import User, UserStatus
from schemas.auth import (
    LoginRequest, LoginResponse, OnboardingRequest,
    PasswordResetRequest, PasswordChangeRequest, UserSession
)
from utils.auth import (
    authenticate_user, create_access_token, get_current_user,
    verify_password, get_password_hash, generate_onboarding_token,
    ACCESS_TOKEN_EXPIRE_MINUTES, get_role_version,
    create_refresh_token, validate_refresh_token, revoke_refresh_token,
    revoke_all_user_refresh_tokens, REFRESH_TOKEN_EXPIRE_DAYS
)
from utils.permissions import UserPermissions
from utils.limiter import limiter

router = APIRouter(tags=["authentication"])


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Access token expiry in seconds

@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    User login with email and password
    Returns access token, refresh token, and user context
    """
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active"
        )

    # Create access token with role version for cache invalidation
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role_version": get_role_version(user)
        },
        expires_delta=access_token_expires
    )

    # Create refresh token
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None
    refresh_token_obj = create_refresh_token(
        db=db,
        user_id=user.id,
        user_agent=user_agent,
        ip_address=client_ip
    )

    # Get user permissions
    permission_service = UserPermissions(db)
    user_perms = permission_service.get_user_effective_permissions(user)

    # Compute full name from separate fields
    name_parts = [user.first_name]
    if user.middle_name:
        name_parts.append(user.middle_name)
    name_parts.append(user.last_name)
    full_name = " ".join(name_parts)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_obj.token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
        "refresh_expires_in": REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # in seconds
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": full_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "middle_name": user.middle_name,
            "organization_name": user.organization.name,
            "role_name": user.role.name,
            "status": user.status.value
        },
        "permissions": user_perms["permissions"],
        "scope": user_perms["effective_scope"]
    }

class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None
    logout_all_devices: bool = False


@router.post("/logout")
async def logout(
    logout_data: Optional[LogoutRequest] = None,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    User logout - revokes refresh token(s)
    If logout_all_devices is True, revokes all refresh tokens for the user
    """
    if logout_data and logout_data.logout_all_devices:
        # Revoke all refresh tokens for this user
        revoke_all_user_refresh_tokens(db, current_user.user_id)
        return {"message": "Successfully logged out from all devices"}
    elif logout_data and logout_data.refresh_token:
        # Revoke the specific refresh token
        revoke_refresh_token(db, logout_data.refresh_token)
        return {"message": "Successfully logged out"}
    else:
        return {"message": "Successfully logged out"}

@router.post("/onboard")
@limiter.limit("10/minute")
async def onboard_user(
    request: Request,
    onboarding_data: OnboardingRequest,
    db: Session = Depends(get_db)
):
    """
    Token-based first-time user setup OR password reset
    - For new users: Set initial password and complete onboarding
    - For existing users: Reset password (when initiated via forgot-password flow)
    Users receive email with secure token → set password → gain system access
    """
    user = db.query(User).filter(User.onboarding_token == onboarding_data.token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired onboarding token"
        )

    # Check if token is expired
    if user.onboarding_token_expires_at and user.onboarding_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token has expired. Please request a new password reset link."
        )

    # Determine if this is onboarding or password reset
    is_password_reset = bool(user.password_hash)

    # Set/update password and clear onboarding token
    user.password_hash = get_password_hash(onboarding_data.password)
    user.onboarding_token = None
    user.onboarding_token_expires_at = None

    # Only set email_verified_at and status if this is initial onboarding
    if not is_password_reset:
        user.email_verified_at = datetime.now(timezone.utc)
        user.status = UserStatus.ACTIVE

    db.commit()

    message = "Password reset successful" if is_password_reset else "User successfully onboarded"
    return {"message": message}

@router.post("/reset-password")
async def reset_password(
    reset_data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Password reset via email
    Generates new onboarding token and sends email
    """
    user = db.query(User).filter(User.email == reset_data.email).first()
    if not user:
        # Don't reveal if email exists for security
        return {"message": "If the email exists, a reset link has been sent"}

    # Generate new onboarding token with 7-day expiration
    user.onboarding_token = generate_onboarding_token()
    user.onboarding_token_expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    try:
        db.commit()
    except Exception:
        db.rollback()

    # Send password reset email in background to avoid proxy timeouts
    reset_token = user.onboarding_token
    background_tasks.add_task(_send_password_reset_email_bg, user.email, user.name, reset_token)

    return {"message": "If the email exists, a reset link has been sent"}

def _send_password_reset_email_bg(user_email: str, user_name: str, reset_token: str):
    """Send password reset email in background to avoid proxy timeouts"""
    import logging
    logger = logging.getLogger(__name__)
    try:
        from utils.email_service import EmailService
        EmailService.send_password_reset_email(user_email, user_name, reset_token)
        logger.info(f"✓ Password reset email sent to {user_email}")
    except Exception as e:
        logger.error(f"✗ Failed to send password reset email to {user_email}: {e}", exc_info=True)

@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change password for authenticated user
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify current password
    if not verify_password(password_data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Update password
    user.password_hash = get_password_hash(password_data.new_password)
    db.commit()

    return {"message": "Password changed successfully"}

@router.get("/me", response_model=UserSession)
async def get_current_user_info(current_user: UserSession = Depends(get_current_user)):
    """
    Get current user session information
    """
    return current_user

@router.get("/session", response_model=UserSession)
async def get_session_data(current_user: UserSession = Depends(get_current_user)):
    """
    Get complete session data for localStorage storage
    This endpoint provides all user context including permissions
    """
    return current_user

@router.post("/refresh")
async def refresh_access_token(
    refresh_data: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token
    Does NOT require valid access token - allows refreshing expired sessions
    """
    # Validate refresh token
    refresh_token_obj = validate_refresh_token(db, refresh_data.refresh_token)
    if not refresh_token_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Get user from refresh token
    user = db.query(User).filter(User.id == refresh_token_obj.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.status != UserStatus.ACTIVE:
        # Revoke the refresh token if user is no longer active
        revoke_refresh_token(db, refresh_data.refresh_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active"
        )

    # Create new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role_version": get_role_version(user)
        },
        expires_delta=access_token_expires
    )

    # Optionally rotate refresh token for better security
    # Revoke old token and create new one
    revoke_refresh_token(db, refresh_data.refresh_token)
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None
    new_refresh_token = create_refresh_token(
        db=db,
        user_id=user.id,
        user_agent=user_agent,
        ip_address=client_ip
    )

    # Get user permissions
    permission_service = UserPermissions(db)
    user_perms = permission_service.get_user_effective_permissions(user)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token.token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_expires_in": REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        "permissions": user_perms["permissions"],
        "scope": user_perms["effective_scope"]
    }


@router.get("/smtp-check")
async def smtp_check(current_user: UserSession = Depends(get_current_user)):
    """
    Diagnostic endpoint to check SMTP configuration and connectivity.
    Requires authentication. Returns SMTP config summary and connection test result.
    """
    import smtplib
    import ssl
    import socket
    import os as _os
    from utils.email_service import SMTP_HOST, SMTP_PORT, SMTP_USERNAME, FROM_EMAIL

    result = {
        "smtp_host": SMTP_HOST,
        "smtp_port": SMTP_PORT,
        "smtp_username": SMTP_USERNAME,
        "from_email": FROM_EMAIL,
        "password_set": bool(_os.getenv("SMTP_PASSWORD")),
        "frontend_url": _os.getenv("FRONTEND_URL", "http://localhost:3000"),
        "tests": []
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    _SMTP_PASSWORD = _os.getenv("SMTP_PASSWORD", "")

    # Test 1: DNS resolution
    try:
        ip = socket.gethostbyname(SMTP_HOST)
        result["tests"].append({"test": "dns_resolution", "status": "ok", "ip": ip})
    except socket.gaierror as e:
        result["tests"].append({"test": "dns_resolution", "status": "fail", "error": str(e)})
        result["overall"] = "fail — cannot resolve SMTP host"
        return result

    # Test 2: TCP connectivity
    try:
        sock = socket.create_connection((SMTP_HOST, SMTP_PORT), timeout=10)
        sock.close()
        result["tests"].append({"test": "tcp_connectivity", "status": "ok", "port": SMTP_PORT})
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        result["tests"].append({"test": "tcp_connectivity", "status": "fail", "error": str(e)})
        result["overall"] = "fail — cannot connect to SMTP server"
        return result

    # Test 3: STARTTLS on configured port
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, _SMTP_PASSWORD)
            result["tests"].append({"test": "starttls_login", "status": "ok", "port": SMTP_PORT})
            result["overall"] = "ok"
            return result
    except Exception as e:
        result["tests"].append({"test": "starttls_login", "status": "fail", "port": SMTP_PORT, "error": str(e)})

    # Test 4: SMTP_SSL on configured port
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=15) as server:
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, _SMTP_PASSWORD)
            result["tests"].append({"test": "smtp_ssl_login", "status": "ok", "port": SMTP_PORT})
            result["overall"] = "ok"
            return result
    except Exception as e:
        result["tests"].append({"test": "smtp_ssl_login", "status": "fail", "port": SMTP_PORT, "error": str(e)})

    # Test 5: Plain SMTP on configured port
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, _SMTP_PASSWORD)
            result["tests"].append({"test": "plain_smtp_login", "status": "ok", "port": SMTP_PORT})
            result["overall"] = "ok"
            return result
    except Exception as e:
        result["tests"].append({"test": "plain_smtp_login", "status": "fail", "port": SMTP_PORT, "error": str(e)})

    # Test 6: STARTTLS on port 587 (standard)
    if SMTP_PORT != 587:
        try:
            with smtplib.SMTP(SMTP_HOST, 587, timeout=15) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                if SMTP_USERNAME:
                    server.login(SMTP_USERNAME, _SMTP_PASSWORD)
                result["tests"].append({"test": "starttls_587", "status": "ok"})
                result["overall"] = "ok"
                return result
        except Exception as e:
            result["tests"].append({"test": "starttls_587", "status": "fail", "error": str(e)})

    # Test 7: Plain on port 25
    if SMTP_PORT != 25:
        try:
            with smtplib.SMTP(SMTP_HOST, 25, timeout=15) as server:
                server.ehlo()
                result["tests"].append({"test": "plain_25", "status": "ok"})
                result["overall"] = "ok"
                return result
        except Exception as e:
            result["tests"].append({"test": "plain_25", "status": "fail", "error": str(e)})

    result["overall"] = "fail — all SMTP connection methods failed"
    return result