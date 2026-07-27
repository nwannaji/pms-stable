"""
Goal Tags/Labels Management API
Endpoints for creating, updating, and managing goal tags
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from database import get_db
from models import GoalTag, User
from schemas.goals import GoalTagCreate, GoalTag as GoalTagSchema
from utils.auth import get_current_user, UserSession

router = APIRouter(prefix="/api/goal-tags", tags=["Goal Tags"])


@router.get("", response_model=List[GoalTagSchema])
async def get_all_tags(
    db: Session = Depends(get_db),
    current_user: UserSession = Depends(get_current_user)
):
    """Get all goal tags"""
    tags = db.query(GoalTag).order_by(GoalTag.name).all()
    return tags


@router.post("", response_model=GoalTagSchema)
async def create_tag(
    tag_data: GoalTagCreate,
    db: Session = Depends(get_db),
    current_user: UserSession = Depends(get_current_user)
):
    """Create a new goal tag"""
    # Check if tag name already exists
    existing_tag = db.query(GoalTag).filter(GoalTag.name == tag_data.name).first()
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag with name '{tag_data.name}' already exists"
        )

    # Validate color format (should be hex color)
    if not tag_data.color.startswith('#'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Color must be a valid hex color code (e.g., #FF5733)"
        )

    tag = GoalTag(
        id=uuid.uuid4(),
        name=tag_data.name,
        color=tag_data.color,
        description=tag_data.description,
        created_by=current_user.user_id
    )

    db.add(tag)
    db.commit()
    db.refresh(tag)

    return tag


@router.put("/{tag_id}", response_model=GoalTagSchema)
async def update_tag(
    tag_id: str,
    tag_data: GoalTagCreate,
    db: Session = Depends(get_db),
    current_user: UserSession = Depends(get_current_user)
):
    """Update an existing goal tag"""
    tag = db.query(GoalTag).filter(GoalTag.id == tag_id).first()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )

    # Check if new name conflicts with existing tag
    if tag_data.name != tag.name:
        existing_tag = db.query(GoalTag).filter(
            GoalTag.name == tag_data.name,
            GoalTag.id != tag_id
        ).first()
        if existing_tag:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tag with name '{tag_data.name}' already exists"
            )

    # Validate color format
    if not tag_data.color.startswith('#'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Color must be a valid hex color code (e.g., #FF5733)"
        )

    tag.name = tag_data.name
    tag.color = tag_data.color
    tag.description = tag_data.description

    db.commit()
    db.refresh(tag)

    return tag


@router.delete("/{tag_id}")
async def delete_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    current_user: UserSession = Depends(get_current_user)
):
    """Delete a goal tag"""
    tag = db.query(GoalTag).filter(GoalTag.id == tag_id).first()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )

    # Get count of goals using this tag
    goal_count = len(tag.goals)

    db.delete(tag)
    db.commit()

    return {
        "message": f"Tag '{tag.name}' deleted successfully",
        "affected_goals": goal_count
    }
