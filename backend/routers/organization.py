"""
Organization Management API Router
Based on CLAUDE.md specification
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from database import get_db
from models import Organization, User, OrganizationLevel
from schemas.organization import (
    OrganizationCreate, OrganizationUpdate, Organization as OrganizationSchema,
    OrganizationWithChildren, OrganizationTree, OrganizationStats
)
from schemas.auth import UserSession
from utils.permissions import UserPermissions, SystemPermissions
from utils.auth import get_current_user

router = APIRouter(tags=["organizations"])

def get_permission_service(db: Session = Depends(get_db)) -> UserPermissions:
    return UserPermissions(db)

@router.get("", response_model=List[OrganizationSchema])
async def get_organizations(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service),
    level: Optional[str] = Query(None, description="Filter by organization level (GLOBAL, DIRECTORATE, DEPARTMENT, DIVISION, UNIT)"),
    parent_id: Optional[uuid.UUID] = Query(None, description="Filter by parent organization ID"),
):
    """
    Get list of organizations accessible to current user.
    Optionally filter by level and/or parent_id.
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    accessible_org_ids = permission_service.get_accessible_organizations(user)
    query = db.query(Organization).filter(Organization.id.in_(accessible_org_ids))

    if level is not None:
        level_upper = level.upper()
        try:
            level_enum = OrganizationLevel(level_upper)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid level '{level}'. Must be one of: GLOBAL, DIRECTORATE, DEPARTMENT, DIVISION, UNIT")
        query = query.filter(Organization.level == level_enum)

    if parent_id is not None:
        query = query.filter(Organization.parent_id == parent_id)

    orgs = query.all()
    for org in orgs:
        org.user_count = db.query(User).filter(User.organization_id == org.id).count()
        org.child_count = db.query(Organization).filter(Organization.parent_id == org.id).count()
    return orgs

@router.get("/tree", response_model=OrganizationTree)
async def get_organization_tree(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Get complete organizational hierarchy tree
    Returns nested structure based on user's access scope
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user can view complete organization structure
    if not permission_service.user_has_permission(user, SystemPermissions.ORGANIZATION_VIEW_ALL):
        # Return only user's accessible organizations
        accessible_org_ids = permission_service.get_accessible_organizations(user)
        # Find the root of user's accessible tree
        root_org = None
        for org_id in accessible_org_ids:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            if org and (not org.parent_id or org.parent_id not in accessible_org_ids):
                root_org = org
                break
    else:
        # Return complete tree starting from global organization
        root_org = db.query(Organization).filter(Organization.level == OrganizationLevel.GLOBAL).first()

    if not root_org:
        raise HTTPException(status_code=404, detail="No accessible organization found")

    def build_tree(org: Organization) -> OrganizationWithChildren:
        children = db.query(Organization).filter(Organization.parent_id == org.id).all()
        return OrganizationWithChildren(
            **org.__dict__,
            children=[build_tree(child) for child in children]
        )

    tree = build_tree(root_org)
    return OrganizationTree(organization=tree)

@router.post("", response_model=OrganizationSchema)
async def create_organization(
    organization_data: OrganizationCreate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Create new organizational unit
    Requires ORGANIZATION_CREATE permission
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not permission_service.user_has_permission(user, SystemPermissions.ORGANIZATION_CREATE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Validate organizational hierarchy rules
    if organization_data.level == OrganizationLevel.GLOBAL:
        # Check if global organization already exists
        existing_global = db.query(Organization).filter(Organization.level == OrganizationLevel.GLOBAL).first()
        if existing_global:
            raise HTTPException(status_code=400, detail="Global organization already exists")
        if organization_data.parent_id:
            raise HTTPException(status_code=400, detail="Global organization cannot have a parent")
    else:
        if not organization_data.parent_id:
            raise HTTPException(status_code=400, detail="Non-global organizations must have a parent")

        # Validate parent exists and user can access it
        parent = db.query(Organization).filter(Organization.id == organization_data.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent organization not found")

        if not permission_service.user_can_access_organization(user, parent.id):
            raise HTTPException(status_code=403, detail="Cannot create organization under inaccessible parent")

        # Validate level hierarchy (5 levels: Global → Directorate → Department → Division → Unit)
        level_order = {
            OrganizationLevel.GLOBAL: 0,
            OrganizationLevel.DIRECTORATE: 1,
            OrganizationLevel.DEPARTMENT: 2,
            OrganizationLevel.DIVISION: 3,  # NEW
            OrganizationLevel.UNIT: 4  # Updated from 3 to 4
        }

        if level_order[organization_data.level] != level_order[parent.level] + 1:
            raise HTTPException(status_code=400, detail="Invalid organizational level for parent")

    # Check for name uniqueness within parent
    siblings = db.query(Organization).filter(Organization.parent_id == organization_data.parent_id).all()
    if any(sibling.name == organization_data.name for sibling in siblings):
        raise HTTPException(status_code=400, detail="Organization name must be unique within parent")

    # Create organization
    organization = Organization(
        name=organization_data.name,
        description=organization_data.description,
        level=organization_data.level,
        parent_id=organization_data.parent_id
    )

    db.add(organization)
    db.commit()
    db.refresh(organization)

    return organization

@router.put("/{organization_id}", response_model=OrganizationSchema)
async def update_organization(
    organization_id: uuid.UUID,
    organization_data: OrganizationUpdate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Update organizational unit details
    Requires ORGANIZATION_EDIT permission and scope access
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not permission_service.user_has_permission(user, SystemPermissions.ORGANIZATION_EDIT):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not permission_service.user_can_access_organization(user, organization.id):
        raise HTTPException(status_code=403, detail="Cannot access this organization")

    # Update fields
    if organization_data.name is not None:
        # Check name uniqueness within parent
        siblings = db.query(Organization).filter(
            Organization.parent_id == organization.parent_id,
            Organization.id != organization.id
        ).all()
        if any(sibling.name == organization_data.name for sibling in siblings):
            raise HTTPException(status_code=400, detail="Organization name must be unique within parent")
        organization.name = organization_data.name

    if organization_data.description is not None:
        organization.description = organization_data.description

    db.commit()
    db.refresh(organization)

    return organization

@router.delete("/{organization_id}")
async def delete_organization(
    organization_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Delete organizational unit with dependency checking
    Requires ORGANIZATION_DELETE permission
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not permission_service.user_has_permission(user, SystemPermissions.ORGANIZATION_DELETE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not permission_service.user_can_access_organization(user, organization.id):
        raise HTTPException(status_code=403, detail="Cannot access this organization")

    # Check for dependencies
    children = db.query(Organization).filter(Organization.parent_id == organization_id).count()
    if children > 0:
        raise HTTPException(status_code=400, detail="Cannot delete organization with child organizations")

    users = db.query(User).filter(User.organization_id == organization_id).count()
    if users > 0:
        raise HTTPException(status_code=400, detail="Cannot delete organization with active users")

    db.delete(organization)
    db.commit()

    return {"message": "Organization deleted successfully"}

@router.get("/{organization_id}/children", response_model=List[OrganizationSchema])
async def get_organization_children(
    organization_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Get direct children of organizational unit
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not permission_service.user_can_access_organization(user, organization.id):
        raise HTTPException(status_code=403, detail="Cannot access this organization")

    children = db.query(Organization).filter(Organization.parent_id == organization_id).all()
    return children

@router.get("/stats", response_model=OrganizationStats)
async def get_organization_stats(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Get organizational statistics
    Returns stats based on user's access scope
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    accessible_org_ids = permission_service.get_accessible_organizations(user)

    # Get organizations within scope
    organizations = db.query(Organization).filter(Organization.id.in_(accessible_org_ids)).all()

    # Calculate statistics
    total_organizations = len(organizations)
    by_level = {}
    for level in OrganizationLevel:
        by_level[level.value] = sum(1 for org in organizations if org.level == level)

    # Get users within scope
    users = db.query(User).filter(User.organization_id.in_(accessible_org_ids)).all()
    total_users = len(users)

    users_by_level = {}
    for level in OrganizationLevel:
        users_by_level[level.value] = sum(1 for user in users if user.organization.level == level)

    return OrganizationStats(
        total_organizations=total_organizations,
        by_level=by_level,
        total_users=total_users,
        users_by_level=users_by_level
    )