"""
Task Management API Router
Based on CLAUDE.md specification with comprehensive task workflows
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
import uuid
import os
from datetime import datetime
import json
 
from database import get_db
from models import Task, TaskStatus, TaskType, User
from schemas.tasks import (
    TaskCreate, TaskUpdate, TaskStatusUpdate, TaskSubmission, TaskReview,
    TaskExtensionRequest, TaskExtensionReview, Task as TaskSchema,
    TaskWithAssignees, TaskSubmissionDetail, TaskDocument, TaskExtension,
    TaskList, TaskStats, TaskUrgency, TaskAssignee
)
from schemas.auth import UserSession
from utils.auth import get_current_user
from utils.permissions import UserPermissions, SystemPermissions
from utils.task_workflows import TaskWorkflowService

router = APIRouter(tags=["tasks"])

@router.get("/debug")
async def debug_endpoint():
    """Simple debug endpoint to test basic router functionality"""
    return {"message": "Tasks router is working", "status": "ok"}

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
async def debug_create_endpoint(task_data: TaskCreate):
    """Debug task creation schema only"""
    return {
        "message": "Schema validation passed",
        "task_title": task_data.title,
        "team_head_id": str(task_data.team_head_id) if task_data.team_head_id else None,
        "urgency": task_data.urgency.value,
        "type": task_data.type.value
    }

def get_permission_service(db: Session = Depends(get_db)) -> UserPermissions:
    return UserPermissions(db)

def get_task_service(db: Session = Depends(get_db)) -> TaskWorkflowService:
    return TaskWorkflowService(db)


@router.get("", response_model=TaskList)
async def get_tasks(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status_filter: Optional[List[TaskStatus]] = Query(None),
    task_type: Optional[TaskType] = None,
    urgency_filter: Optional[TaskUrgency] = None,
    assigned_to_me: bool = False,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    List tasks with visibility rules based on permissions:
    - assigned_to_me=true: Only tasks assigned to user (My Tasks)
    - assigned_to_me=false: All tasks user can access based on permissions
        - With task_view_all permission: See all tasks in system
        - Without task_view_all: Only see tasks you created, are assigned to, or lead
    """
    from models import TaskAssignment
    from sqlalchemy.orm import joinedload

    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build base query with proper joins
    query = db.query(Task).options(
        joinedload(Task.assignments).joinedload(TaskAssignment.user),
        joinedload(Task.creator),
        joinedload(Task.team_head)
    )

    user_task_ids_subquery = db.query(TaskAssignment.task_id).filter(TaskAssignment.user_id == user.id).subquery()

    # Apply visibility filter
    if assigned_to_me:
        # My Tasks: Only tasks assigned to this user
        query = query.filter(Task.id.in_(user_task_ids_subquery))
    else:
        # All Tasks: Depends on permissions
        if "task_view_all" not in current_user.permissions:
            # Regular users: Only see tasks they're directly involved with
            visibility_filter = or_(
                Task.created_by == user.id,  # Created by user
                Task.id.in_(user_task_ids_subquery),  # Assigned to user
                Task.team_head_id == user.id  # User is team head
            )
            query = query.filter(visibility_filter)
        # If user has task_view_all, no filter applied - see everything

    # Apply status filter
    if status_filter:
        query = query.filter(Task.status.in_(status_filter))

    # Apply type filter
    if task_type:
        query = query.filter(Task.type == task_type)

    # Apply urgency filter
    if urgency_filter:
        query = query.filter(Task.urgency == urgency_filter)

    # Order by creation date (newest first)
    query = query.order_by(Task.created_at.desc())

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * per_page
    tasks = query.offset(offset).limit(per_page).all()

    print(f"\n=== DEBUG: Found {total} total tasks, returning {len(tasks)} ===")

    # Convert to TaskWithAssignees with proper assignment data
    task_list = []
    for task in tasks:
        # Convert task to dict, excluding assignments to avoid validation error
        task_dict = {
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'type': task.type,
            'urgency': task.urgency,
            'due_date': task.due_date,
            'goal_id': task.goal_id,
            'status': task.status,
            'score': task.score,
            'feedback': task.feedback,
            'team_head_id': task.team_head_id,
            'created_by': task.created_by,
            'reviewed_at': task.reviewed_at,
            'created_at': task.created_at,
            'updated_at': task.updated_at,
            'creator_name': task.creator.name if task.creator else None,
            'team_head_name': task.team_head.name if task.team_head else None,
            'goal_title': task.goal.title if task.goal else None,
            'assignee_count': len(task.assignments),
            'submission_count': len(task.submissions) if hasattr(task, 'submissions') else 0,
            'document_count': len(task.documents) if hasattr(task, 'documents') else 0,
            'extension_count': len(task.extensions) if hasattr(task, 'extensions') else 0,
        }

        # Manually populate assignments with user data
        assignments = []
        for assignment in task.assignments:
            if assignment.user:  # Ensure user is loaded
                assignments.append(TaskAssignee(
                    user_id=assignment.user_id,
                    user_name=assignment.user.name,
                    user_email=assignment.user.email,
                    assigned_at=assignment.created_at
                ))

        task_dict['assignments'] = assignments
        task_data = TaskWithAssignees(**task_dict)
        task_list.append(task_data)

    return TaskList(
        tasks=task_list,
        total=total,
        page=page,
        per_page=per_page
    )


@router.post("/upload-document", response_model=TaskDocument)
async def upload_task_document(
    file: UploadFile = File(...),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a document that can be attached to tasks
    Returns document ID that can be used when creating tasks or submissions
    """
    from models import TaskDocument as TaskDocumentModel
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
    upload_dir = "uploads/task_documents"
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

    # Create document record (without task_id initially)
    document = TaskDocumentModel(
        file_name=file.filename or unique_filename,
        file_path=file_path,
        uploaded_by=user.id
        # task_id will be None initially and set when attached to a task
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return TaskDocument.from_orm(document)

@router.post("", response_model=TaskSchema)
async def create_task(
    task_data: TaskCreate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    Create new task with scope validation and assignment
    Scope-limited assignment: Can only assign users within creator's organizational scope
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not permission_service.user_has_permission(user, SystemPermissions.TASK_CREATE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        # Use task service to create with validation
        task = task_service.create_task(
            creator=user,
            task_data=task_data.dict(),
            assignee_ids=task_data.assignee_ids,
            team_head_id=task_data.team_head_id,
            document_ids=task_data.document_ids
        )

        return TaskSchema.from_orm(task)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/stats", response_model=TaskStats)
async def get_task_stats(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    Get task statistics and analytics
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user's visible tasks
    tasks = task_service.get_user_tasks(user)

    # Calculate statistics
    total_tasks = len(tasks)

    by_status = {}
    for task_status in TaskStatus:
        by_status[task_status.value] = sum(1 for task in tasks if task.status == task_status)

    by_type = {}
    for task_type in TaskType:
        by_type[task_type.value] = sum(1 for task in tasks if task.type == task_type)

    # Calculate urgency statistics
    by_urgency = {}
    for task_urgency in TaskUrgency:
        by_urgency[task_urgency.value] = sum(1 for task in tasks if task.urgency == task_urgency)

    # Count overdue tasks
    overdue_tasks = sum(1 for task in tasks if task.status == TaskStatus.OVERDUE)

    # Calculate average score and completion rate
    scored_tasks = [task for task in tasks if task.score is not None]
    average_score = sum(task.score for task in scored_tasks) / len(scored_tasks) if scored_tasks else None

    completed_or_approved = sum(1 for task in tasks
                              if task.status in [TaskStatus.PENDING_REVIEW, TaskStatus.APPROVED])
    completion_rate = (completed_or_approved / total_tasks * 100) if total_tasks > 0 else 0

    return TaskStats(
        total_tasks=total_tasks,
        by_status=by_status,
        by_type=by_type,
        by_urgency=by_urgency,
        overdue_tasks=overdue_tasks,
        average_score=average_score,
        completion_rate=completion_rate
    )

@router.get("/{task_id}", response_model=TaskWithAssignees)
async def get_task(
    task_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    Get task details with assignees
    Visibility based on involvement and permissions
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user can see this task
    if not task_service.get_task_visibility(user, task_id):
        raise HTTPException(status_code=403, detail="Cannot access this task")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get assignees
    assignees = []
    for assignment in task.assignments:
        # Compute full name from separate fields
        name_parts = [assignment.user.first_name]
        if assignment.user.middle_name:
            name_parts.append(assignment.user.middle_name)
        name_parts.append(assignment.user.last_name)
        full_name = " ".join(name_parts)

        assignees.append({
            "user_id": str(assignment.user.id),
            "user_name": full_name,
            "user_email": assignment.user.email,
            "assigned_at": assignment.created_at
        })

    task_data = TaskWithAssignees.from_orm(task)
    task_data.assignees = assignees

    return task_data

@router.put("/{task_id}", response_model=TaskSchema)
async def update_task(
    task_id: uuid.UUID,
    task_data: TaskUpdate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: UserPermissions = Depends(get_permission_service),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    Update task details
    Only task creator can update
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not permission_service.user_has_permission(user, SystemPermissions.TASK_EDIT):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Only creator can update task details
    if task.created_by != user.id:
        raise HTTPException(status_code=403, detail="Only task creator can update task details")

    # Update fields
    update_data = task_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)

    return TaskSchema.from_orm(task)

@router.put("/{task_id}/status", response_model=TaskSchema)
async def update_task_status(
    task_id: uuid.UUID,
    status_data: TaskStatusUpdate,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    Update task status (start/complete)
    Different rules for different status transitions
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        if status_data.status == TaskStatus.ONGOING:
            success = task_service.start_task(task_id, user.id)
        else:
            # Other status updates require different logic
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            task.status = status_data.status
            db.commit()
            success = True

        if not success:
            raise HTTPException(status_code=400, detail="Failed to update task status")

        task = db.query(Task).filter(Task.id == task_id).first()
        return TaskSchema.from_orm(task)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{task_id}/submit", response_model=TaskSubmissionDetail)
async def submit_task(
    task_id: uuid.UUID,
    submission_data: TaskSubmission,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    Submit task report and documents
    For group tasks, only team head can submit
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        success = task_service.submit_task(
            task_id, user.id, submission_data.report, submission_data.document_ids
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to submit task")

        # Get submission details
        from models import TaskSubmission as SubmissionModel
        submission = db.query(SubmissionModel).filter(SubmissionModel.task_id == task_id).first()

        return TaskSubmissionDetail.from_orm(submission)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{task_id}/submission")
async def get_task_submission(
    task_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get task submission details including report and documents
    Only task creator can access submission for review
    """
    from models import TaskSubmission as SubmissionModel, TaskDocument
    from sqlalchemy.orm import joinedload

    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Only creator can see submission
    if task.created_by != user.id:
        raise HTTPException(
            status_code=403,
            detail="Only task creator can access submission details"
        )

    # Get submission with documents
    submission = db.query(SubmissionModel).options(
        joinedload(SubmissionModel.submitted_by_user)
    ).filter(SubmissionModel.task_id == task_id).first()

    if not submission:
        raise HTTPException(status_code=404, detail="No submission found for this task")

    # Get documents
    documents = db.query(TaskDocument).filter(
        TaskDocument.task_id == task_id
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

@router.post("/{task_id}/review", response_model=TaskSchema)
async def review_task(
    task_id: uuid.UUID,
    review_data: TaskReview,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    Review and score completed task
    Only task creator can review
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        success = task_service.review_task(
            task_id, user.id, review_data.score, review_data.feedback, review_data.approved
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to review task")

        task = db.query(Task).filter(Task.id == task_id).first()
        return TaskSchema.from_orm(task)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{task_id}/extension-request", response_model=TaskExtension)
async def request_extension(
    task_id: uuid.UUID,
    extension_data: TaskExtensionRequest,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    Request deadline extension
    Only assignees or team head can request
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        extension = task_service.request_extension(
            task_id, user.id, extension_data.new_due_date, extension_data.reason
        )

        return TaskExtension.from_orm(extension)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{task_id}/extension/{extension_id}", response_model=TaskExtension)
async def review_extension(
    task_id: uuid.UUID,
    extension_id: uuid.UUID,
    review_data: TaskExtensionReview,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    Approve/deny extension request
    Only task creator can review extensions
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        success = task_service.review_extension(
            extension_id, user.id, review_data.status == "approved", review_data.reason
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to review extension")

        from models import TaskExtension as ExtensionModel
        extension = db.query(ExtensionModel).filter(ExtensionModel.id == extension_id).first()

        return TaskExtension.from_orm(extension)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{task_id}/submissions", response_model=List[TaskSubmissionDetail])
async def get_task_submissions(
    task_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    View task submission details
    Only visible to task creator and assignees
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user can see this task
    if not task_service.get_task_visibility(user, task_id):
        raise HTTPException(status_code=403, detail="Cannot access this task")

    from models import TaskSubmission as SubmissionModel
    submissions = db.query(SubmissionModel).filter(SubmissionModel.task_id == task_id).all()

    return [TaskSubmissionDetail.from_orm(submission) for submission in submissions]

@router.post("/{task_id}/documents", response_model=TaskDocument)
async def upload_task_document(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    Upload document for task
    Only assignees can upload documents
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user can access this task
    if not task_service.get_task_visibility(user, task_id):
        raise HTTPException(status_code=403, detail="Cannot access this task")

    # Create uploads directory if it doesn't exist
    upload_dir = "uploads/tasks"
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)

    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Create document record
    from models import TaskDocument as DocumentModel
    document = DocumentModel(
        task_id=task_id,
        file_name=file.filename,
        file_path=file_path,
        uploaded_by=user.id
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return TaskDocument.from_orm(document)

@router.get("/documents/{document_id}/download")
async def download_task_document(
    document_id: uuid.UUID,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """Download a task document"""
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get document
    from models import TaskDocument as DocumentModel
    document = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if user can access the task this document belongs to
    if document.task_id:
        if not task_service.get_task_visibility(user, document.task_id):
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

@router.get("/assigned", response_model=TaskList)
async def get_assigned_tasks(
    status_filter: Optional[List[TaskStatus]] = Query(None),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db),
    task_service: TaskWorkflowService = Depends(get_task_service)
):
    """
    Get user's assigned tasks
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user's assigned tasks
    from models import TaskAssignment
    user_task_ids = db.query(TaskAssignment.task_id).filter(TaskAssignment.user_id == user.id).all()
    user_task_ids = [tid[0] for tid in user_task_ids]

    query = db.query(Task).filter(Task.id.in_(user_task_ids))

    if status_filter:
        query = query.filter(Task.status.in_(status_filter))

    tasks = query.all()

    return TaskList(
        tasks=[TaskSchema.from_orm(task) for task in tasks],
        total=len(tasks),
        page=1,
        per_page=len(tasks)
    )

@router.get("/created", response_model=TaskList)
async def get_created_tasks(
    status_filter: Optional[List[TaskStatus]] = Query(None),
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get tasks user created
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = db.query(Task).filter(Task.created_by == user.id)

    if status_filter:
        query = query.filter(Task.status.in_(status_filter))

    tasks = query.all()

    return TaskList(
        tasks=[TaskSchema.from_orm(task) for task in tasks],
        total=len(tasks),
        page=1,
        per_page=len(tasks)
    )

@router.get("/review-queue", response_model=TaskList)
async def get_review_queue(
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get tasks pending review by current user
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get tasks created by user that are pending review
    tasks = db.query(Task).filter(
        Task.created_by == user.id,
        Task.status == TaskStatus.PENDING_REVIEW
    ).all()

    return TaskList(
        tasks=[TaskSchema.from_orm(task) for task in tasks],
        total=len(tasks),
        page=1,
        per_page=len(tasks)
    )

@router.get("/user/{user_id}")
async def get_user_tasks(
    user_id: uuid.UUID,
    status: Optional[str] = None,
    current_user: UserSession = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all tasks for a specific user (assigned to them or created by them)
    Requires appropriate permissions if viewing another user's tasks
    """
    # Check permissions
    if user_id != current_user.user_id:
        # Check if user has permission to view other users' tasks
        if "task_view_all" not in current_user.permissions:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions to view other users' tasks"
            )

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get tasks assigned to the user
    from models import TaskAssignment

    assigned_task_ids = db.query(TaskAssignment.task_id).filter(
        TaskAssignment.user_id == user_id
    ).all()
    assigned_task_ids = [t[0] for t in assigned_task_ids]

    # Build query
    query = db.query(Task).filter(
        or_(
            Task.id.in_(assigned_task_ids),
            Task.created_by == user_id
        )
    )

    # Apply status filter if provided
    if status:
        query = query.filter(Task.status == status)

    # Order by due date
    tasks = query.order_by(Task.due_date.desc()).all()

    # Convert to response format
    task_list = []
    for task in tasks:
        task_dict = {
            "id": str(task.id),
            "title": task.title,
            "description": task.description,
            "type": task.type,
            "status": task.status.value if hasattr(task.status, 'value') else task.status,
            "score": task.score,
            "feedback": task.feedback,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "created_by": task.created_by
        }
        task_list.append(task_dict)

    return task_list

