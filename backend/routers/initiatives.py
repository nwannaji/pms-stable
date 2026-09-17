"""
Initiative Management API Router
Based on CLAUDE.md specification with comprehensive initiative workflows
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
import uuid
import os
from datetime import datetime
import json

from database import get_db
from models import Initiative, InitiativeStatus, InitiativeType, User, InitiativeSubTask, InitiativeAssignment, ActivityAction
from utils.activity import record_activity
from schemas.initiatives import (
    InitiativeCreate, InitiativeUpdate, InitiativeStatusUpdate, InitiativeSubmission, InitiativeReview,
    InitiativeExtensionRequest, InitiativeExtensionReview, Initiative as InitiativeSchema,
    InitiativeWithAssignees, InitiativeForReview, InitiativeSubmissionDetail, InitiativeDocument, InitiativeExtension,
    InitiativeList, InitiativeStats, InitiativeUrgency, InitiativeAssignee, InitiativeApproval,
    SubTask, SubTaskCreate, SubTaskUpdate, SubTaskReorder
)
from schemas.auth import UserSession
from utils.auth import get_current_user
from utils.permissions import UserPermissions, SystemPermissions
from utils.initiative_workflows import InitiativeWorkflowService

router = APIRouter(prefix="/initiatives", tags=["initiatives"])

@router.get("/debug")
async def debug_endpoint():
    """Simple debug endpoint to test basic router functionality"""
    return {"message": "Initiatives router is working", "status": "ok"}

@router.get("/debug-auth")
async def debug_auth_endpoint(current_user: UserSession = Depends(get_current_user)):
    """Debug endpoint with authentication"""
    return {"message": "Auth working", "user": current_user.user_id}

@router.get("/debug-db")
async def debug_db_endpoint(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint with DB dependency"""
    user = db.query(User).filter(User.id == current_user.user_id).first()
    return {"message": "DB working", "user_name": user.name if user else "Not found"}

@router.post("/debug-create")
async def debug_create_endpoint(initiative_data: InitiativeCreate):
    """Debug initiative creation schema only"""
    return {
        "message": "Schema validation passed",
        "initiative_title": initiative_data.title,
        "team_head_id": str(initiative_data.team_head_id) if initiative_data.team_head_id else None,
        "urgency": initiative_data.urgency.value,
        "type": initiative_data.type.value
    }

def get_permission_service(db: Session = Depends(get_db)) -> UserPermissions:
    return UserPermissions(db)

def get_initiative_service(db: Session = Depends(get_db)) -> InitiativeWorkflowService:
    return InitiativeWorkflowService(db)


@router.get("", response_model=InitiativeList)
async def get_initiatives(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status_filter: Optional[List[InitiativeStatus]] = Query(None),
    initiative_type: Optional[InitiativeType] = None,
    urgency_filter: Optional[InitiativeUrgency] = None,
    assigned_to_me: bool = False,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """
    List initiatives with visibility rules based on permissions:
    - assigned_to_me=true: Only initiatives assigned to user (My Initiatives)
    - assigned_to_me=false: All initiatives user can access based on permissions
        - With initiative_view_all permission: See all initiatives in system
        - Without initiative_view_all: Only see initiatives you created, are assigned to, or lead

    NOTE: To see subordinate/supervisee initiatives, use GET /supervisees endpoint
    """
    from models import InitiativeAssignment
    from sqlalchemy.orm import joinedload

    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build base query with proper joins
    query = db.query(Initiative).options(
        joinedload(Initiative.assignments).joinedload(InitiativeAssignment.user),
        joinedload(Initiative.creator),
        joinedload(Initiative.team_head),
        joinedload(Initiative.goal)
    )

    user_initiative_ids_subquery = db.query(InitiativeAssignment.initiative_id).filter(InitiativeAssignment.user_id == user.id).subquery()

    # Apply visibility filter
    if assigned_to_me:
        # My Initiatives: Only initiatives assigned to this user
        query = query.filter(Initiative.id.in_(user_initiative_ids_subquery))
    else:
        # All Initiatives: Depends on permissions
        if "initiative_view_all" not in current_user.permissions:
            # Regular users: See ONLY initiatives they're directly involved with
            # (Created by them, assigned to them, or they are team head)
            # DOES NOT include supervisees' initiatives - use /supervisees for that
            visibility_filter = or_(
                Initiative.created_by == user.id,  # Created by user
                Initiative.id.in_(user_initiative_ids_subquery),  # Assigned to user
                Initiative.team_head_id == user.id  # User is team head
            )
            query = query.filter(visibility_filter)
        # If user has initiative_view_all, no filter applied - see everything

    # Apply status filter
    if status_filter:
        query = query.filter(Initiative.status.in_(status_filter))

    # Apply type filter
    if initiative_type:
        query = query.filter(Initiative.type == initiative_type)

    # Apply urgency filter
    if urgency_filter:
        query = query.filter(Initiative.urgency == urgency_filter)

    # Order by creation date (newest first)
    query = query.order_by(Initiative.created_at.desc())

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * per_page
    initiatives = query.offset(offset).limit(per_page).all()

    print(f"\n=== DEBUG: Found {total} total initiatives, returning {len(initiatives)} ===")

    # Convert to InitiativeWithAssignees with proper assignment data
    initiative_list = []
    for initiative in initiatives:
        # Convert initiative to dict, excluding assignments to avoid validation error
        initiative_dict = {
            'id': initiative.id,
            'title': initiative.title,
            'description': initiative.description,
            'type': initiative.type,
            'urgency': initiative.urgency,
            'due_date': initiative.due_date,
            'goal_id': initiative.goal_id,
            'status': initiative.status,
            'score': initiative.score,
            'feedback': initiative.feedback,
            'team_head_id': initiative.team_head_id,
            'created_by': initiative.created_by,
            'reviewed_at': initiative.reviewed_at,
            'created_at': initiative.created_at,
            'updated_at': initiative.updated_at,
            'creator_name': initiative.creator.name if initiative.creator else None,
            'team_head_name': initiative.team_head.name if initiative.team_head else None,
            'goal_title': initiative.goal.title if initiative.goal else None,
            'assignee_count': len(initiative.assignments),
            'submission_count': len(initiative.submissions) if hasattr(initiative, 'submissions') else 0,
            'document_count': len(initiative.documents) if hasattr(initiative, 'documents') else 0,
            'extension_count': len(initiative.extensions) if hasattr(initiative, 'extensions') else 0,
        }

        # Manually populate assignments with user data
        assignments = []
        for assignment in initiative.assignments:
            if assignment.user:  # Ensure user is loaded
                assignments.append(InitiativeAssignee(
                    user_id=assignment.user_id,
                    user_name=assignment.user.name,
                    user_email=assignment.user.email,
                    assigned_at=assignment.created_at
                ))

        initiative_dict['assignments'] = assignments
        initiative_data = InitiativeWithAssignees(**initiative_dict)
        initiative_list.append(initiative_data)

    return InitiativeList(
        initiatives=initiative_list,
        total=total,
        page=page,
        per_page=per_page
    )


@router.post("/upload-document", response_model=InitiativeDocument)
async def upload_initiative_document(
    file: UploadFile = File(...),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Upload a document that can be attached to initiatives
    Returns document ID that can be used when creating initiatives or submissions
    """
    from models import InitiativeDocument as InitiativeDocumentModel
    import os
    import uuid as uuid_module
    from datetime import datetime

    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate file type and size
    if file.size and file.size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    allowed_types = {
        "application/pdf", "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/jpeg", "image/png", "image/gif", "text/plain"
    }

    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="File type not allowed")

    # Create uploads directory if it doesn't exist
    upload_dir = "uploads/initiative_documents"
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
    unique_filename = f"{uuid_module.uuid4()}{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)

    # Save file
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to save file")

    # Create document record (without initiative_id initially)
    document = InitiativeDocumentModel(
        file_name=file.filename or unique_filename,
        file_path=file_path,
        uploaded_by=user.id
        # initiative_id will be None initially and set when attached to an initiative
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    record_activity(db, action=ActivityAction.INITIATIVE_DOCUMENT_UPLOAD, user=current_user,
                    entity_type="initiative_document", entity_id=document.id, request=request,
                    details={"file_name": document.file_name})

    return InitiativeDocument.from_orm(document)

@router.post("", response_model=InitiativeSchema)
async def create_initiative(
    initiative_data: InitiativeCreate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service),
    request: Request = None
):
    """
    Create new initiative with scope validation and assignment
    Scope-limited assignment: Can only assign users within creator's organizational scope
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # if not permission_service.user_has_permission(user, SystemPermissions.INITIATIVE_CREATE):
    #     raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        # Convert subtasks to dict format if provided
        subtasks_data = None
        if initiative_data.subtasks:
            subtasks_data = [subtask.dict() for subtask in initiative_data.subtasks]

        # Use initiative service to create with validation
        initiative = initiative_service.create_initiative(
            creator=user,
            initiative_data=initiative_data.dict(),
            assignee_ids=initiative_data.assignee_ids,
            team_head_id=initiative_data.team_head_id,
            document_ids=initiative_data.document_ids,
            subtasks=subtasks_data
        )

        record_activity(db, action=ActivityAction.INITIATIVE_CREATE, user=current_user,
                        entity_type="initiative", entity_id=initiative.id, request=request,
                        details={"title": initiative.title,
                                 "urgency": initiative.urgency.value if initiative.urgency else None})

        return InitiativeSchema.from_orm(initiative)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{initiative_id}/approve", response_model=InitiativeSchema)
async def approve_initiative(
    initiative_id: uuid.UUID,
    approval: InitiativeApproval,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service),
    request: Request = None
):
    """
    Approve or reject a pending initiative
    Only the initiative creator's supervisor can approve
    Approved initiatives go to PENDING status (ready to start)
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        success = initiative_service.approve_initiative(
            initiative_id,
            user.id,
            approval.approved,
            approval.rejection_reason
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to approve/reject initiative")

        initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()

        record_activity(db, action=ActivityAction.INITIATIVE_APPROVE, user=current_user,
                        entity_type="initiative", entity_id=initiative_id, request=request,
                        details={"approved": approval.approved,
                                 "rejection_reason": approval.rejection_reason,
                                 "status": initiative.status.value if initiative.status else None})

        return InitiativeSchema.from_orm(initiative)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{initiative_id}/accept", response_model=InitiativeSchema)
async def accept_initiative(
    initiative_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Accept an ASSIGNED initiative
    When supervisor creates and assigns to you, you must accept it
    ASSIGNED → PENDING
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # Verify user is assigned to this initiative
    from models import InitiativeAssignment
    is_assigned = db.query(InitiativeAssignment).filter(
        InitiativeAssignment.initiative_id == initiative_id,
        InitiativeAssignment.user_id == user.id
    ).first()

    if not is_assigned:
        raise HTTPException(status_code=403, detail="You are not assigned to this initiative")

    if initiative.status != InitiativeStatus.ASSIGNED:
        raise HTTPException(status_code=400, detail=f"Initiative must be ASSIGNED to accept (current: {initiative.status})")

    # Change status to PENDING
    initiative.status = InitiativeStatus.PENDING
    db.commit()
    db.refresh(initiative)

    return InitiativeSchema.from_orm(initiative)

@router.put("/{initiative_id}/start", response_model=InitiativeSchema)
async def start_initiative(
    initiative_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a PENDING initiative
    PENDING → ONGOING
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # Verify user is assigned to this initiative
    from models import InitiativeAssignment
    is_assigned = db.query(InitiativeAssignment).filter(
        InitiativeAssignment.initiative_id == initiative_id,
        InitiativeAssignment.user_id == user.id
    ).first()

    if not is_assigned:
        raise HTTPException(status_code=403, detail="You are not assigned to this initiative")

    if initiative.status != InitiativeStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Initiative must be PENDING to start (current: {initiative.status})")

    # Change status to ONGOING
    initiative.status = InitiativeStatus.ONGOING
    db.commit()
    db.refresh(initiative)

    return InitiativeSchema.from_orm(initiative)

@router.put("/{initiative_id}/complete", response_model=InitiativeSchema)
async def complete_initiative(
    initiative_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Mark ONGOING initiative as complete
    ONGOING → UNDER_REVIEW
    Note: Use /submit endpoint to add report and documents
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # Verify user is assigned to this initiative
    from models import InitiativeAssignment
    is_assigned = db.query(InitiativeAssignment).filter(
        InitiativeAssignment.initiative_id == initiative_id,
        InitiativeAssignment.user_id == user.id
    ).first()

    if not is_assigned:
        raise HTTPException(status_code=403, detail="You are not assigned to this initiative")

    if initiative.status != InitiativeStatus.ONGOING:
        raise HTTPException(status_code=400, detail=f"Initiative must be ONGOING to complete (current: {initiative.status})")

    # Change status to UNDER_REVIEW
    initiative.status = InitiativeStatus.UNDER_REVIEW
    db.commit()
    db.refresh(initiative)

    record_activity(db, action=ActivityAction.INITIATIVE_COMPLETE, user=current_user,
                    entity_type="initiative", entity_id=initiative_id, request=request,
                    details={"title": initiative.title})

    return InitiativeSchema.from_orm(initiative)

@router.get("/stats", response_model=InitiativeStats)
async def get_initiative_stats(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """
    Get initiative statistics and analytics
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user's visible initiatives
    initiatives = initiative_service.get_user_initiatives(user)

    # Calculate statistics
    total_initiatives = len(initiatives)

    by_status = {}
    for initiative_status in InitiativeStatus:
        by_status[initiative_status.value] = sum(1 for initiative in initiatives if initiative.status == initiative_status)

    by_type = {}
    for initiative_type in InitiativeType:
        by_type[initiative_type.value] = sum(1 for initiative in initiatives if initiative.type == initiative_type)

    # Calculate urgency statistics
    by_urgency = {}
    for initiative_urgency in InitiativeUrgency:
        by_urgency[initiative_urgency.value] = sum(1 for initiative in initiatives if initiative.urgency == initiative_urgency)

    # Count overdue and pending approval initiatives
    overdue_initiatives = sum(1 for initiative in initiatives if initiative.status == InitiativeStatus.OVERDUE)
    pending_approval = sum(1 for initiative in initiatives if initiative.status == InitiativeStatus.PENDING_APPROVAL)

    # Calculate average score and completion rate
    scored_initiatives = [initiative for initiative in initiatives if initiative.score is not None]
    average_score = sum(initiative.score for initiative in scored_initiatives) / len(scored_initiatives) if scored_initiatives else None

    completed_or_approved = sum(1 for initiative in initiatives
                              if initiative.status in [InitiativeStatus.UNDER_REVIEW, InitiativeStatus.COMPLETED])
    completion_rate = (completed_or_approved / total_initiatives * 100) if total_initiatives > 0 else 0

    return InitiativeStats(
        total_initiatives=total_initiatives,
        by_status=by_status,
        by_type=by_type,
        by_urgency=by_urgency,
        overdue_initiatives=overdue_initiatives,
        pending_approval=pending_approval,
        average_score=average_score,
        completion_rate=completion_rate
    )

@router.get("/assignable-users")
async def get_assignable_users(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of users that can be assigned to initiatives
    - Regular users: All active users in their department
    - Users with initiative_view_all: All active users in accessible organizations
    """
    from models import UserStatus
    from utils.permissions import UserPermissions

    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    permission_service = UserPermissions(db)

    # Check if user has global assignment permission
    if permission_service.user_has_permission(user, "initiative_view_all"):
        # Get all users in accessible organizations
        accessible_orgs = permission_service.get_accessible_organizations(user)
        users = db.query(User).filter(
            User.organization_id.in_(accessible_orgs),
            User.status == UserStatus.ACTIVE
        ).all()
    else:
        # Get users in same department only
        users = db.query(User).filter(
            User.organization_id == user.organization_id,
            User.status == UserStatus.ACTIVE
        ).all()

    return [
        {
            "id": str(u.id),
            "name": u.name,
            "email": u.email,
            "job_title": u.job_title
        }
        for u in users
    ]

@router.get("/has-supervisees")
async def check_has_supervisees(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if current user has supervisees (direct reports)
    Used by frontend to determine whether to show supervisee initiatives tab
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    supervisee_count = db.query(User).filter(User.supervisor_id == user.id).count()

    return {
        "has_supervisees": supervisee_count > 0,
        "supervisee_count": supervisee_count
    }

@router.get("/supervisees", response_model=List[InitiativeWithAssignees])
async def get_supervisee_initiatives(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all initiatives belonging to the current user's supervisees (direct reports)
    Returns initiatives created by or assigned to your direct reports
    This is where supervisors can see what their team members are working on

    NOTE: This endpoint always returns successfully (empty array if no supervisees)
    Use GET /has-supervisees to check if user has supervisees before calling this
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all supervisees (direct reports)
    supervisees = db.query(User).filter(User.supervisor_id == user.id).all()
    supervisee_ids = [s.id for s in supervisees]

    if not supervisee_ids:
        return []

    # Get initiatives created by or assigned to supervisees
    from models import InitiativeAssignment
    from sqlalchemy.orm import joinedload

    supervisee_initiative_ids_subquery = db.query(InitiativeAssignment.initiative_id).filter(
        InitiativeAssignment.user_id.in_(supervisee_ids)
    ).subquery()

    initiatives = db.query(Initiative).options(
        joinedload(Initiative.assignments).joinedload(InitiativeAssignment.user),
        joinedload(Initiative.creator),
        joinedload(Initiative.team_head),
        joinedload(Initiative.goal)
    ).filter(
        or_(
            Initiative.created_by.in_(supervisee_ids),  # Created by supervisees
            Initiative.id.in_(supervisee_initiative_ids_subquery)  # Assigned to supervisees
        )
    ).order_by(Initiative.created_at.desc()).all()

    # Convert to InitiativeWithAssignees with proper field population
    initiative_list = []
    for initiative in initiatives:
        initiative_dict = {
            'id': initiative.id,
            'title': initiative.title,
            'description': initiative.description,
            'type': initiative.type,
            'urgency': initiative.urgency,
            'due_date': initiative.due_date,
            'goal_id': initiative.goal_id,
            'status': initiative.status,
            'score': initiative.score,
            'feedback': initiative.feedback,
            'team_head_id': initiative.team_head_id,
            'created_by': initiative.created_by,
            'reviewed_at': initiative.reviewed_at,
            'created_at': initiative.created_at,
            'updated_at': initiative.updated_at,
            'creator_name': initiative.creator.name if initiative.creator else None,
            'team_head_name': initiative.team_head.name if initiative.team_head else None,
            'goal_title': initiative.goal.title if initiative.goal else None,
            'assignee_count': len(initiative.assignments),
            'submission_count': len(initiative.submissions) if hasattr(initiative, 'submissions') else 0,
            'document_count': len(initiative.documents) if hasattr(initiative, 'documents') else 0,
            'extension_count': len(initiative.extensions) if hasattr(initiative, 'extensions') else 0,
        }

        # Populate assignments with user data
        assignments = []
        for assignment in initiative.assignments:
            if assignment.user:
                assignments.append(InitiativeAssignee(
                    user_id=assignment.user_id,
                    user_name=assignment.user.name,
                    user_email=assignment.user.email,
                    assigned_at=assignment.created_at
                ))

        initiative_dict['assignments'] = assignments
        initiative_data = InitiativeWithAssignees(**initiative_dict)
        initiative_list.append(initiative_data)

    return initiative_list

@router.get("/assigned", response_model=InitiativeList)
async def get_assigned_initiatives(
    status_filter: Optional[List[InitiativeStatus]] = Query(None),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """
    Get user's assigned initiatives
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user's assigned initiatives
    from models import InitiativeAssignment
    user_initiative_ids = db.query(InitiativeAssignment.initiative_id).filter(InitiativeAssignment.user_id == user.id).all()
    user_initiative_ids = [iid[0] for iid in user_initiative_ids]

    query = db.query(Initiative).filter(Initiative.id.in_(user_initiative_ids))

    if status_filter:
        query = query.filter(Initiative.status.in_(status_filter))

    initiatives = query.all()

    return InitiativeList(
        initiatives=[InitiativeSchema.from_orm(initiative) for initiative in initiatives],
        total=len(initiatives),
        page=1,
        per_page=len(initiatives)
    )

@router.get("/created", response_model=InitiativeList)
async def get_created_initiatives(
    status_filter: Optional[List[InitiativeStatus]] = Query(None),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get initiatives user created
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = db.query(Initiative).filter(Initiative.created_by == user.id)

    if status_filter:
        query = query.filter(Initiative.status.in_(status_filter))

    initiatives = query.all()

    return InitiativeList(
        initiatives=[InitiativeSchema.from_orm(initiative) for initiative in initiatives],
        total=len(initiatives),
        page=1,
        per_page=len(initiatives)
    )

@router.get("/review-queue", response_model=InitiativeList)
async def get_review_queue(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get initiatives pending review by current user
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get initiatives created by user that are pending review
    initiatives = db.query(Initiative).filter(
        Initiative.created_by == user.id,
        Initiative.status == InitiativeStatus.UNDER_REVIEW
    ).all()

    return InitiativeList(
        initiatives=[InitiativeSchema.from_orm(initiative) for initiative in initiatives],
        total=len(initiatives),
        page=1,
        per_page=len(initiatives)
    )

@router.get("/{initiative_id}", response_model=InitiativeWithAssignees)
async def get_initiative(
    initiative_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """
    Get initiative details with assignees
    Visibility based on involvement and permissions
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user can see this initiative
    if not initiative_service.get_initiative_visibility(user, initiative_id):
        raise HTTPException(status_code=403, detail="Cannot access this initiative")

    initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # Get assignees
    assignees = []
    for assignment in initiative.assignments:
        assignees.append({
            "user_id": str(assignment.user.id),
            "user_name": assignment.user.name,  # Use display name field
            "user_email": assignment.user.email,
            "assigned_at": assignment.created_at
        })

    initiative_data = InitiativeWithAssignees.from_orm(initiative)
    initiative_data.assignees = assignees

    return initiative_data

@router.put("/{initiative_id}", response_model=InitiativeSchema)
async def update_initiative(
    initiative_id: uuid.UUID,
    initiative_data: InitiativeUpdate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service),
    request: Request = None
):
    """
    Update initiative details
    Only initiative creator can update
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not permission_service.user_has_permission(user, SystemPermissions.INITIATIVE_EDIT):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # Only creator can update initiative details
    if initiative.created_by != user.id:
        raise HTTPException(status_code=403, detail="Only initiative creator can update initiative details")

    # Update fields
    update_data = initiative_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(initiative, field, value)

    db.commit()
    db.refresh(initiative)

    record_activity(db, action=ActivityAction.INITIATIVE_UPDATE, user=current_user,
                    entity_type="initiative", entity_id=initiative_id, request=request,
                    details={"fields": list(update_data.keys())})

    return InitiativeSchema.from_orm(initiative)

@router.put("/{initiative_id}/status", response_model=InitiativeSchema)
async def update_initiative_status(
    initiative_id: uuid.UUID,
    status_data: InitiativeStatusUpdate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """
    Update initiative status (start/complete)
    Different rules for different status transitions
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        if status_data.status == InitiativeStatus.ONGOING:
            success = initiative_service.start_initiative(initiative_id, user.id)
        else:
            # Other status updates require different logic
            initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
            if not initiative:
                raise HTTPException(status_code=404, detail="Initiative not found")

            initiative.status = status_data.status
            db.commit()
            success = True

        if not success:
            raise HTTPException(status_code=400, detail="Failed to update initiative status")

        initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
        return InitiativeSchema.from_orm(initiative)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{initiative_id}/submit", response_model=InitiativeSubmissionDetail)
async def submit_initiative(
    initiative_id: uuid.UUID,
    submission_data: InitiativeSubmission,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service),
    request: Request = None
):
    """
    Submit initiative report and documents
    For group initiatives, only team head can submit
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        success = initiative_service.submit_initiative(
            initiative_id, user.id, submission_data.report, submission_data.document_ids
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to submit initiative")

        # Get submission details
        from models import InitiativeSubmission as SubmissionModel
        submission = db.query(SubmissionModel).filter(SubmissionModel.initiative_id == initiative_id).first()

        record_activity(db, action=ActivityAction.INITIATIVE_SUBMIT, user=current_user,
                        entity_type="initiative", entity_id=initiative_id, request=request,
                        details={"submission_id": str(submission.id) if submission else None})

        return InitiativeSubmissionDetail.from_orm(submission)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{initiative_id}/submission")
async def get_initiative_submission(
    initiative_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get initiative submission details including report and documents
    Only initiative creator can access submission for review
    """
    from models import InitiativeSubmission as SubmissionModel, InitiativeDocument
    from sqlalchemy.orm import joinedload

    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # Only creator can see submission
    if initiative.created_by != user.id:
        raise HTTPException(
            status_code=403,
            detail="Only initiative creator can access submission details"
        )

    # Get submission with documents
    submission = db.query(SubmissionModel).options(
        joinedload(SubmissionModel.submitted_by_user)
    ).filter(SubmissionModel.initiative_id == initiative_id).first()

    if not submission:
        raise HTTPException(status_code=404, detail="No submission found for this initiative")

    # Get documents
    documents = db.query(InitiativeDocument).filter(
        InitiativeDocument.initiative_id == initiative_id
    ).all()

    # Get submitter info
    submitter = db.query(User).filter(User.id == submission.submitted_by).first()

    return {
        "id": str(submission.id),
        "report": submission.report,
        "submitted_by": str(submission.submitted_by),
        "submitter_name": submitter.name if submitter else None,
        "submitted_at": submission.submitted_at,
        "documents": [
            {
                "id": str(doc.id),
                "file_name": doc.file_name,
                "file_path": doc.file_path,
                "uploaded_by": str(doc.uploaded_by),
                "uploaded_at": doc.uploaded_at
            }
            for doc in documents
        ]
    }

@router.get("/{initiative_id}/for-review", response_model=InitiativeForReview)
async def get_initiative_for_review(
    initiative_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """
    Get initiative with submission details for review
    Returns initiative details along with the submission report and documents
    Only accessible by initiative creator or supervisor
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user can see this initiative
    if not initiative_service.get_initiative_visibility(user, initiative_id):
        raise HTTPException(status_code=403, detail="Cannot access this initiative")

    initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # Verify user is authorized to review (creator or supervisor)
    creator = db.query(User).filter(User.id == initiative.created_by).first()
    is_supervisor = creator and creator.supervisor_id == user.id

    if initiative.created_by != user.id and not is_supervisor:
        raise HTTPException(status_code=403, detail="Only initiative creator or supervisor can review")

    # Get assignees
    assignees = []
    for assignment in initiative.assignments:
        assignees.append({
            "user_id": str(assignment.user.id),
            "user_name": assignment.user.name,
            "user_email": assignment.user.email,
            "assigned_at": assignment.created_at
        })

    # Get submission details
    from models import InitiativeSubmission as SubmissionModel, InitiativeDocument as DocumentModel
    submission = db.query(SubmissionModel).filter(
        SubmissionModel.initiative_id == initiative_id
    ).first()

    submission_data = None
    if submission:
        # Get submission documents
        documents = db.query(DocumentModel).filter(
            DocumentModel.initiative_id == initiative_id
        ).all()

        submitter = db.query(User).filter(User.id == submission.submitted_by).first()
        submission_data = InitiativeSubmissionDetail(
            id=submission.id,
            report=submission.report,
            submitted_by=submission.submitted_by,
            submitter_name=submitter.name if submitter else None,
            submitted_at=submission.submitted_at,
            documents=[{
                "id": str(doc.id),
                "file_name": doc.file_name,
                "file_path": doc.file_path,
                "uploaded_by": str(doc.uploaded_by),
                "uploaded_at": doc.uploaded_at
            } for doc in documents]
        )

    initiative_data = InitiativeForReview.from_orm(initiative)
    initiative_data.assignments = assignees
    initiative_data.submission = submission_data

    return initiative_data

@router.post("/{initiative_id}/review", response_model=InitiativeSchema)
async def review_initiative(
    initiative_id: uuid.UUID,
    review_data: InitiativeReview,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """
    Review and score completed initiative
    Only initiative creator can review
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        success = initiative_service.review_initiative(
            initiative_id, user.id, review_data.score, review_data.feedback, review_data.approved
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to review initiative")

        initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
        return InitiativeSchema.from_orm(initiative)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{initiative_id}/extension-request", response_model=InitiativeExtension)
async def request_extension(
    initiative_id: uuid.UUID,
    extension_data: InitiativeExtensionRequest,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """
    Request deadline extension
    Only assignees or team head can request
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        extension = initiative_service.request_extension(
            initiative_id, user.id, extension_data.new_due_date, extension_data.reason
        )

        return InitiativeExtension.from_orm(extension)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{initiative_id}/extension/{extension_id}", response_model=InitiativeExtension)
async def review_extension(
    initiative_id: uuid.UUID,
    extension_id: uuid.UUID,
    review_data: InitiativeExtensionReview,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """
    Approve/deny extension request
    Only initiative creator can review extensions
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        success = initiative_service.review_extension(
            extension_id, user.id, review_data.status == "approved", review_data.reason
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to review extension")

        from models import InitiativeExtension as ExtensionModel
        extension = db.query(ExtensionModel).filter(ExtensionModel.id == extension_id).first()

        return InitiativeExtension.from_orm(extension)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{initiative_id}/submissions", response_model=List[InitiativeSubmissionDetail])
async def get_initiative_submissions(
    initiative_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """
    View initiative submission details
    Only visible to initiative creator and assignees
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user can see this initiative
    if not initiative_service.get_initiative_visibility(user, initiative_id):
        raise HTTPException(status_code=403, detail="Cannot access this initiative")

    from models import InitiativeSubmission as SubmissionModel
    submissions = db.query(SubmissionModel).filter(SubmissionModel.initiative_id == initiative_id).all()

    return [InitiativeSubmissionDetail.from_orm(submission) for submission in submissions]

@router.post("/{initiative_id}/documents", response_model=InitiativeDocument)
async def upload_initiative_document(
    initiative_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """
    Upload document for initiative
    Only assignees can upload documents
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user can access this initiative
    if not initiative_service.get_initiative_visibility(user, initiative_id):
        raise HTTPException(status_code=403, detail="Cannot access this initiative")

    # Validate file type and size
    allowed_types = {
        "application/pdf", "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/jpeg", "image/png", "text/plain"
    }
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="File type not allowed")
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    # Create uploads directory if it doesn't exist
    upload_dir = "uploads/initiatives"
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename — use os.path.splitext, never split('.')
    from pathlib import Path as _Path
    file_extension = _Path(file.filename).suffix if file.filename else ""
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)

    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Create document record
    from models import InitiativeDocument as DocumentModel
    document = DocumentModel(
        initiative_id=initiative_id,
        file_name=file.filename,
        file_path=file_path,
        uploaded_by=user.id
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return InitiativeDocument.from_orm(document)

@router.get("/documents/{document_id}/download")
async def download_initiative_document(
    document_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    initiative_service: InitiativeWorkflowService = Depends(get_initiative_service)
):
    """Download an initiative document"""
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get document
    from models import InitiativeDocument as DocumentModel
    document = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if user can access the initiative this document belongs to
    if document.initiative_id:
        if not initiative_service.get_initiative_visibility(user, document.initiative_id):
            raise HTTPException(status_code=403, detail="Cannot access this document")

    # Check if file exists
    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    # Return file
    return FileResponse(
        path=document.file_path,
        filename=document.file_name,
        media_type='application/octet-stream'
    )

@router.get("/user/{user_id}")
async def get_user_initiatives(
    user_id: uuid.UUID,
    status: Optional[str] = None,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all initiatives for a specific user (assigned to them or created by them)
    Requires appropriate permissions if viewing another user's initiatives
    """
    # Check permissions
    if user_id != current_user.user_id:
        # Check if user has permission to view other users' initiatives
        if "initiative_view_all" not in current_user.permissions:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions to view other users' initiatives"
            )

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get initiatives assigned to the user
    from models import InitiativeAssignment

    assigned_initiative_ids = db.query(InitiativeAssignment.initiative_id).filter(
        InitiativeAssignment.user_id == user_id
    ).all()
    assigned_initiative_ids = [i[0] for i in assigned_initiative_ids]

    # Build query
    query = db.query(Initiative).filter(
        or_(
            Initiative.id.in_(assigned_initiative_ids),
            Initiative.created_by == user_id
        )
    )

    # Apply status filter if provided
    if status:
        query = query.filter(Initiative.status == status)

    # Order by due date
    initiatives = query.order_by(Initiative.due_date.desc()).all()

    # Convert to response format
    initiative_list = []
    for initiative in initiatives:
        initiative_dict = {
            "id": str(initiative.id),
            "title": initiative.title,
            "description": initiative.description,
            "type": initiative.type,
            "status": initiative.status.value if hasattr(initiative.status, 'value') else initiative.status,
            "score": initiative.score,
            "feedback": initiative.feedback,
            "due_date": initiative.due_date.isoformat() if initiative.due_date else None,
            "created_at": initiative.created_at.isoformat() if initiative.created_at else None,
            "created_by": initiative.created_by,
            "goal_id": str(initiative.goal_id) if initiative.goal_id else None,
        }
        initiative_list.append(initiative_dict)

    return initiative_list
# from models import InitiativeSubTask
# from schemas.initiatives import SubTask, SubTaskCreate, SubTaskUpdate, SubTaskReorder

@router.get("/{initiative_id}/subtasks", response_model=List[SubTask])
async def get_subtasks(
    initiative_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all sub-tasks for an initiative
    Only accessible by users who can see the initiative
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get initiative and check access
    initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # Check visibility
    from utils.initiative_workflows import InitiativeWorkflowService
    initiative_service = InitiativeWorkflowService(db)
    # if not initiative_service.get_initiative_visibility(user, initiative_id):
    #     raise HTTPException(status_code=403, detail="Cannot access this initiative")

    # Get sub-tasks
    subtasks = db.query(InitiativeSubTask).filter(
        InitiativeSubTask.initiative_id == initiative_id
    ).order_by(InitiativeSubTask.sequence_order).all()

    return [SubTask.from_orm(st) for st in subtasks]

@router.post("/{initiative_id}/subtasks", response_model=SubTask)
async def create_subtask(
    initiative_id: uuid.UUID,
    subtask_data: SubTaskCreate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new sub-task for an initiative
    Only assignees can create sub-tasks
    Initiative must be in ONGOING status
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get initiative
    initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # Verify user is assigned to initiative
    assignment = db.query(InitiativeAssignment).filter(
        InitiativeAssignment.initiative_id == initiative_id,
        InitiativeAssignment.user_id == user.id
    ).first()

    if not assignment:
        raise HTTPException(status_code=403, detail="Only assignees can create sub-tasks")

    # Verify initiative is in ONGOING status
    from models import InitiativeStatus
    if initiative.status != InitiativeStatus.ONGOING:
        raise HTTPException(status_code=400, detail="Can only create sub-tasks for ONGOING initiatives")

    # Get next sequence order
    max_order = db.query(func.max(InitiativeSubTask.sequence_order)).filter(
        InitiativeSubTask.initiative_id == initiative_id
    ).scalar() or -1

    # Create sub-task
    subtask = InitiativeSubTask(
        title=subtask_data.title,
        description=subtask_data.description,
        initiative_id=initiative_id,
        created_by=user.id,
        sequence_order=max_order + 1,
        status='pending'
    )

    db.add(subtask)
    db.commit()
    db.refresh(subtask)

    return SubTask.from_orm(subtask)

@router.put("/{initiative_id}/subtasks/{subtask_id}", response_model=SubTask)
async def update_subtask(
    initiative_id: uuid.UUID,
    subtask_id: uuid.UUID,
    subtask_data: SubTaskUpdate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a sub-task (title, description, or status)
    When status changes to 'completed', set completed_at timestamp
    """
    from datetime import datetime
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get sub-task
    subtask = db.query(InitiativeSubTask).filter(
        InitiativeSubTask.id == subtask_id,
        InitiativeSubTask.initiative_id == initiative_id
    ).first()

    if not subtask:
        raise HTTPException(status_code=404, detail="Sub-task not found")

    # Verify user is assigned to initiative
    assignment = db.query(InitiativeAssignment).filter(
        InitiativeAssignment.initiative_id == initiative_id,
        InitiativeAssignment.user_id == user.id
    ).first()

    if not assignment:
        raise HTTPException(status_code=403, detail="Only assignees can update sub-tasks")

    # Update fields
    if subtask_data.title is not None:
        subtask.title = subtask_data.title
    if subtask_data.description is not None:
        subtask.description = subtask_data.description
    if subtask_data.status is not None:
        old_status = subtask.status
        subtask.status = subtask_data.status
        # Set completed_at when status changes to completed
        if subtask_data.status == 'completed' and old_status != 'completed':
            subtask.completed_at = datetime.utcnow()
        elif subtask_data.status == 'pending' and old_status == 'completed':
            subtask.completed_at = None

    db.commit()
    db.refresh(subtask)

    return SubTask.from_orm(subtask)

@router.delete("/{initiative_id}/subtasks/{subtask_id}")
async def delete_subtask(
    initiative_id: uuid.UUID,
    subtask_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a sub-task
    Only assignees can delete sub-tasks
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get sub-task
    subtask = db.query(InitiativeSubTask).filter(
        InitiativeSubTask.id == subtask_id,
        InitiativeSubTask.initiative_id == initiative_id
    ).first()

    if not subtask:
        raise HTTPException(status_code=404, detail="Sub-task not found")

    # Verify user is assigned to initiative
    assignment = db.query(InitiativeAssignment).filter(
        InitiativeAssignment.initiative_id == initiative_id,
        InitiativeAssignment.user_id == user.id
    ).first()

    if not assignment:
        raise HTTPException(status_code=403, detail="Only assignees can delete sub-tasks")

    db.delete(subtask)
    db.commit()

    return {"message": "Sub-task deleted successfully"}

@router.post("/{initiative_id}/subtasks/reorder")
async def reorder_subtasks(
    initiative_id: uuid.UUID,
    reorder_data: SubTaskReorder,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reorder sub-tasks by providing ordered list of sub-task IDs
    Only assignees can reorder sub-tasks
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify user is assigned to initiative
    assignment = db.query(InitiativeAssignment).filter(
        InitiativeAssignment.initiative_id == initiative_id,
        InitiativeAssignment.user_id == user.id
    ).first()

    if not assignment:
        raise HTTPException(status_code=403, detail="Only assignees can reorder sub-tasks")

    # Update sequence_order for each sub-task
    for index, subtask_id in enumerate(reorder_data.subtask_ids):
        subtask = db.query(InitiativeSubTask).filter(
            InitiativeSubTask.id == subtask_id,
            InitiativeSubTask.initiative_id == initiative_id
        ).first()

        if subtask:
            subtask.sequence_order = index

    db.commit()

    return {"message": "Sub-tasks reordered successfully"}

@router.delete("/{initiative_id}")
async def delete_initiative(
    initiative_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service)
):
    """
    Delete an initiative
    Only the initiative creator or users with initiative_delete permission can delete initiatives
    Cannot delete initiatives that have been completed or are under review
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # Permission check: must be creator or have initiative_delete permission
    can_delete = (
        initiative.created_by == user.id or
        permission_service.user_has_permission(user, SystemPermissions.INITIATIVE_DELETE)
    )

    if not can_delete:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete this initiative"
        )

    # Prevent deletion of completed or under-review initiatives (optional business rule)
    if initiative.status in [InitiativeStatus.COMPLETED, InitiativeStatus.UNDER_REVIEW]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete initiative with status {initiative.status.value}. Only pending or ongoing initiatives can be deleted."
        )

    # Delete related records first (cascade delete)
    # Delete assignments
    from models import InitiativeAssignment, InitiativeSubmission, InitiativeDocument, InitiativeExtension
    db.query(InitiativeAssignment).filter(InitiativeAssignment.initiative_id == initiative_id).delete()

    # Delete sub-tasks
    db.query(InitiativeSubTask).filter(InitiativeSubTask.initiative_id == initiative_id).delete()

    # Delete submissions
    db.query(InitiativeSubmission).filter(InitiativeSubmission.initiative_id == initiative_id).delete()

    # Delete documents (note: you may want to also delete physical files)
    documents = db.query(InitiativeDocument).filter(InitiativeDocument.initiative_id == initiative_id).all()
    for doc in documents:
        # Optionally delete physical file
        if os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except Exception as e:
                print(f"Error deleting file {doc.file_path}: {e}")
        db.delete(doc)

    # Delete extensions
    db.query(InitiativeExtension).filter(InitiativeExtension.initiative_id == initiative_id).delete()

    # Finally, delete the initiative itself
    db.delete(initiative)
    db.commit()

    return {"message": "Initiative deleted successfully"}
