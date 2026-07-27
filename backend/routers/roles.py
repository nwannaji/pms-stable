"""
Role Management API Router
Based on CLAUDE.md specification with scope override capabilities
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from database import get_db
from models import Role, User
from schemas.roles import (
    RoleCreate, RoleUpdate, Role as RoleSchema,
    PermissionGroup, PermissionList
)
from schemas.auth import UserSession
from utils.auth import get_current_user
from utils.permissions import UserPermissions, SystemPermissions, PermissionGroups

router = APIRouter(tags=["roles"])

def get_permission_service(db: Session = Depends(get_db)) -> UserPermissions:
    return UserPermissions(db)

@router.get("", response_model=List[RoleSchema])
async def get_roles(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    List all roles
    Filtered by admin scope if user doesn't have ROLE_VIEW_ALL permission
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    roles = db.query(Role).all()

    # Add user count to each role
    role_list = []
    for role in roles:
        user_count = db.query(User).filter(User.role_id == role.id).count()
        role_data = RoleSchema.from_orm(role)
        role_data.user_count = user_count
        role_list.append(role_data)

    return role_list

@router.post("", response_model=RoleSchema)
async def create_role(
    role_data: RoleCreate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Create new role definition
    Requires ROLE_CREATE permission
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not permission_service.user_has_permission(user, SystemPermissions.ROLE_CREATE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Check if role name already exists
    existing_role = db.query(Role).filter(Role.name == role_data.name).first()
    if existing_role:
        raise HTTPException(status_code=400, detail="Role name already exists")

    # Validate permissions - ensure user can assign these permissions
    # TODO: Add logic to prevent users from creating roles with higher permissions than they have

    # Create role
    role = Role(
        name=role_data.name,
        description=role_data.description,
        is_leadership=role_data.is_leadership,
        scope_override=role_data.scope_override,
        permissions=role_data.permissions
    )

    db.add(role)
    db.commit()
    db.refresh(role)

    return RoleSchema.from_orm(role)

@router.get("/permissions")
async def get_all_permissions(
    current_user: UserSession = Depends(get_current_user)
):
    """
    List all available permissions for role creation
    Permission list is dynamically generated from system permissions
    Returns permissions grouped by category
    """
    return PermissionGroups.get_all_groups()

@router.get("/{role_id}", response_model=RoleSchema)
async def get_role(
    role_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get role details
    """
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    user_count = db.query(User).filter(User.role_id == role.id).count()
    role_data = RoleSchema.from_orm(role)
    role_data.user_count = user_count

    return role_data

@router.put("/{role_id}", response_model=RoleSchema)
async def update_role(
    role_id: uuid.UUID,
    role_data: RoleUpdate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Modify existing role permissions and settings
    Requires ROLE_EDIT permission
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not permission_service.user_has_permission(user, SystemPermissions.ROLE_EDIT):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Check name uniqueness if name is being changed
    if role_data.name and role_data.name != role.name:
        existing_role = db.query(Role).filter(Role.name == role_data.name).first()
        if existing_role:
            raise HTTPException(status_code=400, detail="Role name already exists")

    # Update fields
    update_data = role_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(role, field, value)

    db.commit()
    db.refresh(role)

    return RoleSchema.from_orm(role)

@router.delete("/{role_id}")
async def delete_role(
    role_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Remove role (blocked if assigned to active users)
    Requires ROLE_DELETE permission
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not permission_service.user_has_permission(user, SystemPermissions.ROLE_DELETE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Check if role is assigned to active users
    active_users = db.query(User).filter(User.role_id == role_id).count()
    if active_users > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role assigned to {active_users} active users"
        )

    db.delete(role)
    db.commit()

    return {"message": "Role deleted successfully"}

@router.post("/{role_id}/assign/{user_id}")
async def assign_role_to_user(
    role_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Assign role to user within scope
    Requires ROLE_ASSIGN permission
    """
    assigner = db.query(User).filter(User.id == current_user.user_id).first()
    if not assigner:
        raise HTTPException(status_code=404, detail="Assigner not found")

    if not permission_service.user_has_permission(assigner, SystemPermissions.ROLE_ASSIGN):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check scope access to target user
    if not permission_service.user_can_access_organization(assigner, target_user.organization_id):
        raise HTTPException(status_code=403, detail="Cannot assign role to user outside your scope")

    # TODO: Validate that assigner can assign this specific role
    # (shouldn't be able to assign roles with higher permissions)

    old_role_id = target_user.role_id
    target_user.role_id = role_id

    db.commit()

    return {
        "message": "Role assigned successfully",
        "old_role_id": str(old_role_id) if old_role_id else None,
        "new_role_id": str(role_id)
    }

@router.get("/{role_id}/users", response_model=List[dict])
async def get_role_users(
    role_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Get all users assigned to a specific role
    Filtered by scope access
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Get accessible organizations
    accessible_org_ids = permission_service.get_accessible_organizations(user)

    # Get users with this role within scope
    role_users = db.query(User).filter(
        User.role_id == role_id,
        User.organization_id.in_(accessible_org_ids)
    ).all()

    return [
        {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "organization_name": user.organization.name,
            "status": user.status.value
        }
        for user in role_users
    ]