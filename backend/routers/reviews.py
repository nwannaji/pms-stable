"""
Performance Review API Router
Handles review cycles, reviews, and evaluation workflows
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc, asc
from typing import List, Optional, Dict, Any
from database import get_db
from models import User, ReviewCycle, Review, Initiative, InitiativeAssignment, Goal, Organization, ReviewTrait, ReviewQuestion, ReviewCycleTrait, ReviewAssignment, ReviewResponse as ReviewResponseModel, ReviewScore, PerformanceScore, ReviewCycleStatus
from routers.auth import get_current_user
from utils.permissions import UserPermissions
from pydantic import BaseModel
from datetime import datetime, timedelta
import json

router = APIRouter(tags=["reviews"])

# Pydantic models
class ReviewCycleCreate(BaseModel):
    name: str
    type: str  # quarterly, annual, probationary, project
    period: str  # Q1-2024, FY-2024, etc.
    start_date: datetime
    end_date: datetime
    phase_schedule: Optional[dict] = None
    buffer_time: str = '1_week'
    target_population: Optional[dict] = None
    inclusion_criteria: Optional[dict] = None
    exclusion_criteria: Optional[dict] = None
    mandatory_participants: Optional[List[int]] = None
    components: Optional[dict] = None
    ai_assistance: Optional[dict] = None
    calibration_sessions: Optional[dict] = None
    approval_workflow: Optional[dict] = None

class ReviewCycleUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    period: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    phase_schedule: Optional[dict] = None
    buffer_time: Optional[str] = None
    target_population: Optional[dict] = None
    components: Optional[dict] = None
    status: Optional[str] = None

class ReviewCycleResponse(BaseModel):
    id: str
    name: str
    type: str
    period: str
    start_date: datetime
    end_date: datetime
    phase_schedule: dict
    buffer_time: str
    target_population: Optional[dict] = None
    components: dict
    status: str
    created_by: str
    participants_count: int = 0
    completion_rate: float = 0.0
    quality_score: float = 0.0
    selected_traits: List[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

    @classmethod
    def model_validate(cls, obj):
        if hasattr(obj, 'id'):
            obj.id = str(obj.id)
        if hasattr(obj, 'created_by'):
            obj.created_by = str(obj.created_by)
        return super().model_validate(obj)

class ReviewCreate(BaseModel):
    cycle_id: int
    reviewee_id: int
    type: str  # self, peer, supervisor, 360

class ReviewUpdate(BaseModel):
    responses: Optional[dict] = None
    completion_percentage: Optional[float] = None
    status: Optional[str] = None

class ReviewResponse(BaseModel):
    id: int
    cycle_id: int
    reviewee_id: int
    type: str
    responses: Optional[dict]
    completion_percentage: float
    time_spent: int
    ai_insights: Optional[dict]
    status: str
    deadline: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]

    class Config:
        from_attributes = True

# Review Cycle endpoints
@router.get("/cycles", response_model=List[ReviewCycleResponse])
async def get_review_cycles(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all review cycles visible to the current user"""
    # Admins can see all cycles regardless of status
    if ("review_view_all" in current_user.permissions or
        "review_manage_cycle" in current_user.permissions or
        "system_admin" in current_user.permissions):
        cycles = db.query(ReviewCycle).order_by(desc(ReviewCycle.created_at)).all()
    else:
        # Cycles where user is creator OR has review assignments
        cycles = db.query(ReviewCycle).filter(
            or_(
                ReviewCycle.created_by == current_user.user_id,
                ReviewCycle.id.in_(
                    db.query(ReviewAssignment.cycle_id).filter(
                        ReviewAssignment.reviewer_id == current_user.user_id
                    )
                )
            )
        ).order_by(desc(ReviewCycle.created_at)).all()

    # Compute completion_rate dynamically and convert UUIDs to strings
    for cycle in cycles:
        total = db.query(ReviewAssignment).filter(
            ReviewAssignment.cycle_id == cycle.id
        ).count()
        if total > 0:
            completed = db.query(ReviewAssignment).filter(
                ReviewAssignment.cycle_id == cycle.id,
                ReviewAssignment.status == 'completed'
            ).count()
            cycle.completion_rate = round(completed / total * 100, 1)
        else:
            cycle.completion_rate = 0.0
        cycle.id = str(cycle.id)
        cycle.created_by = str(cycle.created_by)

    return cycles

@router.post("/cycles", response_model=ReviewCycleResponse)
async def create_review_cycle(
    cycle_data: ReviewCycleCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new review cycle in DRAFT status"""
    if "review_create_cycle" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create review cycles"
        )

    cycle = ReviewCycle(
        name=cycle_data.name,
        type=cycle_data.type,
        period=cycle_data.period,
        start_date=cycle_data.start_date,
        end_date=cycle_data.end_date,
        status=ReviewCycleStatus.DRAFT,
        phase_schedule=cycle_data.phase_schedule or {
            "setup": {"start": cycle_data.start_date.isoformat(), "duration": "1_week"},
            "reviews": {"start": (cycle_data.start_date + timedelta(weeks=1)).isoformat(), "duration": "3_weeks"},
            "analysis": {"start": (cycle_data.end_date - timedelta(weeks=1)).isoformat(), "duration": "1_week"}
        },
        buffer_time=cycle_data.buffer_time,
        target_population=cycle_data.target_population,
        inclusion_criteria=cycle_data.inclusion_criteria,
        exclusion_criteria=cycle_data.exclusion_criteria,
        mandatory_participants=cycle_data.mandatory_participants,
        components=cycle_data.components or {
            "self_review": True,
            "supervisor_review": True,
            "auto_assign": True
        },
        ai_assistance=cycle_data.ai_assistance or {},
        calibration_sessions=cycle_data.calibration_sessions,
        approval_workflow=cycle_data.approval_workflow,
        created_by=current_user.user_id
    )

    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    # Link ALL traits to the cycle
    all_traits = db.query(ReviewTrait).filter(ReviewTrait.is_active == True).all()
    for trait in all_traits:
        cycle_trait = ReviewCycleTrait(
            cycle_id=cycle.id,
            trait_id=trait.id
        )
        db.add(cycle_trait)

    db.commit()
    db.refresh(cycle)

    # Convert UUIDs to strings for response
    cycle.id = str(cycle.id)
    cycle.created_by = str(cycle.created_by)

    return cycle

@router.get("/cycles/{cycle_id}", response_model=ReviewCycleResponse)
async def get_review_cycle(
    cycle_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific review cycle"""
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review cycle not found"
        )
    
    # Get selected traits for this cycle
    cycle_traits = db.query(ReviewCycleTrait).filter(ReviewCycleTrait.cycle_id == cycle_id).all()
    selected_trait_ids = [str(ct.trait_id) for ct in cycle_traits]

    # Create response with selected traits
    cycle_dict = {
        "id": str(cycle.id),
        "name": cycle.name,
        "type": cycle.type,
        "period": cycle.period,
        "start_date": cycle.start_date,
        "end_date": cycle.end_date,
        "phase_schedule": cycle.phase_schedule or {},
        "buffer_time": cycle.buffer_time or "1_week",
        "target_population": cycle.target_population,
        "components": cycle.components or {},
        "status": cycle.status,
        "created_by": str(cycle.created_by),
        "participants_count": cycle.participants_count or 0,
        "completion_rate": _compute_cycle_completion_rate(cycle_id, db),
        "quality_score": cycle.quality_score or 0.0,
        "selected_traits": selected_trait_ids,
        "created_at": cycle.created_at,
        "updated_at": cycle.updated_at
    }

    return cycle_dict

@router.put("/cycles/{cycle_id}", response_model=ReviewCycleResponse)
async def update_review_cycle(
    cycle_id: str,
    cycle_data: ReviewCycleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a review cycle"""
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review cycle not found"
        )
    
    # Check permissions
    permission_engine = get_permission_engine(db)
    if not (cycle.created_by == current_user.user_id or 
            permission_engine.check_permission(current_user, "reviews:update:all")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update this review cycle"
        )
    
    # Update fields
    update_data = cycle_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cycle, field, value)
    
    db.commit()
    db.refresh(cycle)

    return cycle

@router.post("/cycles/{cycle_id}/sync-traits")
async def sync_cycle_traits(
    cycle_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync all active traits to this cycle
    This is useful when traits are created after the cycle was created
    """
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review cycle not found"
        )

    # Check permissions
    if not ("review_manage_cycle" in current_user.permissions or
            "system_admin" in current_user.permissions or
            cycle.created_by == current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to sync traits for this cycle"
        )

    # Get all currently active traits
    all_traits = db.query(ReviewTrait).filter(ReviewTrait.is_active == True).all()

    # Get currently linked traits
    existing_links = db.query(ReviewCycleTrait).filter(
        ReviewCycleTrait.cycle_id == cycle_id
    ).all()
    existing_trait_ids = {link.trait_id for link in existing_links}

    # Link any new traits that aren't already linked
    new_links_count = 0
    for trait in all_traits:
        if trait.id not in existing_trait_ids:
            cycle_trait = ReviewCycleTrait(
                cycle_id=cycle.id,
                trait_id=trait.id,
                is_active=True
            )
            db.add(cycle_trait)
            new_links_count += 1

    db.commit()

    return {
        "message": f"Successfully synced traits to cycle",
        "cycle_id": str(cycle_id),
        "new_traits_linked": new_links_count,
        "total_traits": len(all_traits)
    }

@router.post("/cycles/{cycle_id}/start")
async def start_review_cycle(
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start a review cycle and initialize participants"""
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review cycle not found"
        )
    
    # Check permissions
    permission_engine = get_permission_engine(db)
    if not (cycle.created_by == current_user.user_id or 
            permission_engine.check_permission(current_user, "reviews:manage:cycle")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to start this review cycle"
        )
    
    if cycle.status != 'draft':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review cycle is not in draft status"
        )
    
    # Initialize participants based on target population
    participants = _initialize_cycle_participants(cycle, db)
    
    # Create initial reviews for participants
    for participant in participants:
        # Self review
        if cycle.components.get('self_review', {}).get('enabled', True):
            self_review = Review(
                cycle_id=cycle.id,
                reviewee_id=participant.id,
                type='self',
                deadline=cycle.start_date + timedelta(days=cycle.components['self_review'].get('deadline_days', 7))
            )
            db.add(self_review)
    
    # Update cycle status
    cycle.status = 'active'
    cycle.participants_count = len(participants)
    
    db.commit()
    
    return {"message": f"Review cycle started with {len(participants)} participants"}

# Review endpoints
@router.get("", response_model=List[ReviewResponse])
async def get_reviews(
    cycle_id: Optional[int] = None,
    reviewee_id: Optional[int] = None,
    type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get reviews based on filters"""
    query = db.query(Review)
    
    # Apply filters
    if cycle_id:
        query = query.filter(Review.cycle_id == cycle_id)
    if reviewee_id:
        query = query.filter(Review.reviewee_id == reviewee_id)
    if type:
        query = query.filter(Review.type == type)
    
    # Apply permission-based filtering
    permission_engine = get_permission_engine(db)
    if not permission_engine.check_permission(current_user, "reviews:read:all"):
        # Users can only see their own reviews (as reviewee)
        query = query.filter(Review.reviewee_id == current_user.user_id)
    
    reviews = query.all()
    return reviews

@router.post("", response_model=ReviewResponse)
async def create_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new review"""
    permission_engine = get_permission_engine(db)
    
    if not permission_engine.check_permission(current_user, "reviews:create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create reviews"
        )
    
    # Verify cycle exists
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == review_data.cycle_id).first()
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review cycle not found"
        )
    
    review = Review(
        cycle_id=review_data.cycle_id,
        reviewee_id=review_data.reviewee_id,
        type=review_data.type,
        deadline=cycle.end_date
    )
    
    db.add(review)
    db.commit()
    db.refresh(review)
    
    return review

@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: int,
    review_data: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a review"""
    review = db.query(Review).filter(Review.id == review_id).first()
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    
    # Check permissions - reviewee can update their own reviews
    if review.reviewee_id != current_user.user_id:
        permission_engine = get_permission_engine(db)
        if not permission_engine.check_permission(current_user, "reviews:update:all"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update this review"
            )
    
    # Update fields
    update_data = review_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(review, field, value)
    
    # Update completion percentage based on responses
    if 'responses' in update_data and review.responses:
        total_questions = len([q for q in review.responses.keys() if q.startswith('q_')])
        answered_questions = len([q for q, a in review.responses.items() if q.startswith('q_') and a])
        review.completion_percentage = (answered_questions / total_questions * 100) if total_questions > 0 else 0
    
    db.commit()
    db.refresh(review)
    
    return review

@router.post("/{review_id}/submit")
async def submit_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a review for approval"""
    review = db.query(Review).filter(Review.id == review_id).first()
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    
    # Check permissions
    if review.reviewee_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the reviewee can submit their review"
        )
    
    if review.status != 'draft':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review is not in draft status"
        )
    
    review.status = 'submitted'
    review.submitted_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "Review submitted successfully"}

def _initialize_cycle_participants(cycle: ReviewCycle, db: Session) -> List[User]:
    """Initialize participants for a review cycle based on target population"""
    query = db.query(User).filter(User.is_active == True)
    
    # Apply inclusion criteria
    if cycle.inclusion_criteria:
        # This would contain logic for filtering users based on criteria
        # For now, just get all active users
        pass
    
    # Apply exclusion criteria
    if cycle.exclusion_criteria:
        # Apply exclusion logic
        pass
    
    participants = query.all()
    
    # Add mandatory participants
    if cycle.mandatory_participants:
        mandatory_users = db.query(User).filter(User.id.in_(cycle.mandatory_participants)).all()
        participant_ids = {p.id for p in participants}
        for user in mandatory_users:
            if user.id not in participant_ids:
                participants.append(user)
    
    return participants

# Advanced Review System Features

@router.post("/cycles/{cycle_id}/analytics")
async def generate_cycle_analytics(
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate comprehensive analytics for a review cycle"""
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    
    if not cycle:
        raise HTTPException(status_code=404, detail="Review cycle not found")
    
    permission_engine = get_permission_engine(db)
    if not permission_engine.check_permission(current_user, "reviews:analytics:view"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get all reviews for this cycle
    reviews = db.query(Review).filter(Review.cycle_id == cycle_id).all()
    peer_reviews = []

    analytics = {
        "cycle_overview": _generate_cycle_overview(cycle, reviews, peer_reviews),
        "participation_analysis": _analyze_participation(reviews, peer_reviews),
        "performance_insights": _analyze_performance_patterns(reviews),
        "bias_analysis": _detect_and_analyze_bias(reviews, peer_reviews),
        "consistency_metrics": _analyze_rating_consistency(reviews, peer_reviews),
        "quality_assessment": _assess_review_quality(reviews, peer_reviews),
        "recommendations": _generate_cycle_recommendations(cycle, reviews, peer_reviews)
    }
    
    return analytics

@router.post("/cycles/{cycle_id}/calibration")
async def schedule_calibration_session(
    cycle_id: int,
    session_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Schedule calibration session for review consistency"""
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    
    if not cycle:
        raise HTTPException(status_code=404, detail="Review cycle not found")
    
    permission_engine = get_permission_engine(db)
    if not permission_engine.check_permission(current_user, "reviews:manage:cycle"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Update calibration settings
    calibration_config = cycle.calibration_sessions or {}
    calibration_config.update({
        "sessions": calibration_config.get("sessions", []) + [{
            "scheduled_by": current_user.user_id,
            "scheduled_at": datetime.utcnow().isoformat(),
            "session_date": session_data.get("session_date"),
            "participants": session_data.get("participants", []),
            "agenda": session_data.get("agenda", []),
            "focus_areas": session_data.get("focus_areas", [])
        }]
    })
    
    cycle.calibration_sessions = calibration_config
    db.commit()
    
    return {"message": "Calibration session scheduled successfully"}

@router.get("/bias-detection/{cycle_id}")
async def get_bias_detection_report(
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive bias detection report for a cycle"""
    permission_engine = get_permission_engine(db)
    if not permission_engine.check_permission(current_user, "reviews:analytics:view"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    reviews = db.query(Review).filter(Review.cycle_id == cycle_id).all()
    peer_reviews = []

    bias_report = {
        "overall_bias_score": _calculate_overall_bias_score(reviews, peer_reviews),
        "bias_types": {
            "recency_bias": _detect_recency_bias(reviews),
            "halo_effect": _detect_halo_effect(reviews),
            "similarity_bias": _detect_similarity_bias(peer_reviews),
            "leniency_bias": _detect_leniency_bias(reviews),
            "central_tendency": _detect_central_tendency_bias(reviews)
        },
        "affected_groups": _analyze_demographic_bias(reviews, db),
        "reviewer_patterns": _analyze_reviewer_bias_patterns(peer_reviews),
        "mitigation_recommendations": _generate_bias_mitigation_recommendations(reviews, peer_reviews)
    }
    
    return bias_report

@router.post("/ai-insights/{review_id}")
async def generate_ai_insights(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate AI-powered insights for a specific review"""
    review = db.query(Review).filter(Review.id == review_id).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    # Check permissions
    if review.reviewee_id != current_user.user_id:
        permission_engine = get_permission_engine(db)
        if not permission_engine.check_permission(current_user, "reviews:read:all"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    if not review.responses:
        raise HTTPException(status_code=400, detail="No review responses to analyze")
    
    # Generate AI insights
    insights = {
        "performance_highlights": _extract_performance_highlights(review.responses),
        "development_areas": _identify_development_areas(review.responses),
        "sentiment_analysis": _analyze_review_sentiment(review.responses),
        "topic_extraction": _extract_review_topics(review.responses),
        "strengths_summary": _summarize_strengths(review.responses),
        "improvement_suggestions": _generate_improvement_suggestions(review.responses),
        "career_development_recommendations": _recommend_career_development(review.responses)
    }
    
    # Store insights
    review.ai_insights = insights
    review.sentiment_analysis = insights["sentiment_analysis"]
    review.topic_analysis = insights["topic_extraction"]
    
    db.commit()
    
    return insights

@router.get("/performance-dashboard/{user_id}")
async def get_performance_dashboard(
    user_id: int,
    time_period: str = Query("current_year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive performance dashboard for a user"""
    
    # Check permissions
    if user_id != current_user.user_id:
        permission_engine = get_permission_engine(db)
        if not (current_user.is_superuser or permission_engine.check_permission(current_user, "performance:view:all")):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get reviews for the user
    reviews_query = db.query(Review).filter(Review.reviewee_id == user_id)

    # Apply time filter
    if time_period == "current_year":
        start_date = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        reviews_query = reviews_query.filter(Review.created_at >= start_date)
    elif time_period == "last_6_months":
        start_date = datetime.now() - timedelta(days=180)
        reviews_query = reviews_query.filter(Review.created_at >= start_date)

    reviews = reviews_query.all()
    peer_reviews = []

    dashboard = {
        "user_profile": {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email,
            "job_title": user.job_title,
            "department": user.department.name if user.department else None
        },
        "performance_summary": _generate_performance_summary(reviews, peer_reviews),
        "goal_achievement": _analyze_goal_achievement(user_id, db),
        "competency_analysis": _analyze_competency_development(reviews),
        "peer_feedback_trends": _analyze_peer_feedback_trends(peer_reviews),
        "development_progress": _track_development_progress(reviews),
        "recognition_highlights": _extract_recognition_highlights(reviews, peer_reviews),
        "growth_recommendations": _generate_growth_recommendations(user_id, reviews, peer_reviews, db)
    }
    
    return dashboard

@router.get("/organization-performance")
async def get_organization_performance(
    cycle_id: Optional[str] = Query(None, description="Review cycle ID"),
    department: Optional[str] = Query(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get organization-wide performance analytics based on review cycle
    Returns task performance, values/traits scores, and competency framework data
    """

    # Check permissions
    if "performance_view_all" not in current_user.permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions to view organization performance")

    # Get review cycle (use most recent active/completed if not specified)
    from models import UserStatus, ReviewCycleStatus, InitiativeStatus
    cycle = None
    if cycle_id:
        cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
        if not cycle:
            raise HTTPException(status_code=404, detail="Review cycle not found")
    else:
        # Prefer the most recent active or completed cycle
        cycle = db.query(ReviewCycle).filter(
            ReviewCycle.status.in_([ReviewCycleStatus.ACTIVE, ReviewCycleStatus.COMPLETED])
        ).order_by(desc(ReviewCycle.start_date)).first()
        # Fall back to any cycle (e.g. draft) so employees are always visible
        if not cycle:
            cycle = db.query(ReviewCycle).order_by(desc(ReviewCycle.start_date)).first()

    # Build base query for employees
    employees_query = db.query(User).filter(User.status == UserStatus.ACTIVE)

    # Apply department filter
    if department and department != "all":
        try:
            dept_id = int(department)
            employees_query = employees_query.filter(User.organization_id == dept_id)
        except ValueError:
            dept = db.query(Organization).filter(Organization.name == department).first()
            if dept:
                employees_query = employees_query.filter(User.organization_id == dept.id)

    employees = employees_query.all()

    # Get all traits for this cycle
    cycle_traits = db.query(ReviewTrait).join(
        ReviewCycleTrait, ReviewCycleTrait.trait_id == ReviewTrait.id
    ).filter(
        ReviewCycleTrait.cycle_id == cycle.id,
        ReviewTrait.is_active == True
    ).order_by(ReviewTrait.display_order).all()

    # Prepare employee performance data
    employee_performance = []

    for employee in employees:
        # Get tasks within cycle date range
        tasks = db.query(Initiative).join(
            InitiativeAssignment, InitiativeAssignment.initiative_id == Initiative.id
        ).filter(
            InitiativeAssignment.user_id == employee.id,
            Initiative.created_at >= cycle.start_date,
            Initiative.created_at <= cycle.end_date
        ).all()

        # Calculate task metrics
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.status == InitiativeStatus.COMPLETED])
        task_scores = [t.score for t in tasks if t.score is not None]
        avg_task_score = sum(task_scores) / len(task_scores) if task_scores else None

        # Get task details with ratings
        task_details = []
        for task in tasks:
            task_details.append({
                "id": str(task.id),
                "title": task.title,
                "status": task.status.value,
                "score": task.score,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "completed_at": task.reviewed_at.isoformat() if task.reviewed_at else None
            })

        # Get trait scores for this employee in this cycle
        trait_scores = db.query(ReviewScore).filter(
            ReviewScore.cycle_id == cycle.id,
            ReviewScore.user_id == employee.id
        ).all()

        trait_score_map = {str(score.trait_id): score for score in trait_scores}

        # Separate values (global) from competency (department/unit-specific)
        values_data = []
        competency_data = []

        from models import TraitScopeType

        for trait in cycle_traits:
            score_obj = trait_score_map.get(str(trait.id))

            # Values are global (organization-wide)
            if trait.scope_type == TraitScopeType.GLOBAL:
                trait_data = {
                    "trait_id": str(trait.id),
                    "trait_name": trait.name,
                    "trait_description": trait.description,
                    "weighted_score": float(score_obj.weighted_score) if score_obj and score_obj.weighted_score else None
                }
                values_data.append(trait_data)
            # Competency are tied to directorate/department/unit
            # Only include if the trait's organization matches the employee's organization
            elif trait.organization_id and str(trait.organization_id) == str(employee.organization_id):
                trait_data = {
                    "trait_id": str(trait.id),
                    "trait_name": trait.name,
                    "trait_description": trait.description,
                    "weighted_score": float(score_obj.weighted_score) if score_obj and score_obj.weighted_score else None
                }
                competency_data.append(trait_data)

        # Get overall review score for this cycle
        reviews = db.query(Review).filter(
            Review.cycle_id == cycle.id,
            Review.reviewee_id == employee.id
        ).all()

        # Calculate separate scores for values and competency
        values_scores = [v["weighted_score"] for v in values_data if v["weighted_score"] is not None]
        competency_scores = [c["weighted_score"] for c in competency_data if c["weighted_score"] is not None]

        avg_values_score = sum(values_scores) / len(values_scores) if values_scores else None
        avg_competency_score = sum(competency_scores) / len(competency_scores) if competency_scores else None

        # Get department info
        department_name = None
        if employee.organization:
            department_name = employee.organization.name

        employee_performance.append({
            "id": str(employee.id),
            "name": f"{employee.first_name} {employee.last_name}",
            "email": employee.email,
            "department_name": department_name,
            "role_name": employee.job_title,

            # Task Performance
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "task_completion_rate": round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1),
            "avg_task_score": round(avg_task_score, 2) if avg_task_score else None,
            "tasks": task_details,

            # Values (organization-wide) and Competency (unit-specific)
            "values": values_data,
            "values_score": round(avg_values_score, 2) if avg_values_score else None,
            "competency": competency_data,
            "competency_score": round(avg_competency_score, 2) if avg_competency_score else None,

            "total_reviews": len(reviews)
        })

    return {
        "cycle": {
            "id": str(cycle.id),
            "name": cycle.name,
            "type": cycle.type,
            "period": cycle.period,
            "start_date": cycle.start_date.isoformat(),
            "end_date": cycle.end_date.isoformat(),
            "status": cycle.status.value
        },
        "traits": [{"id": str(t.id), "name": t.name, "description": t.description} for t in cycle_traits],
        "employees": employee_performance
    }

@router.get("/my-assignments")
async def get_my_review_assignments(
    status: Optional[str] = Query(None),
    cycle_id: Optional[str] = Query(None),
    limit: int = Query(20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's review assignments using ReviewAssignment model"""

    # Query all assignments where the current user is the reviewer
    query = db.query(ReviewAssignment).filter(
        ReviewAssignment.reviewer_id == current_user.user_id
    )

    # Apply status filter if provided
    if status:
        query = query.filter(ReviewAssignment.status == status)

    # Apply cycle filter if provided
    if cycle_id:
        query = query.filter(ReviewAssignment.cycle_id == cycle_id)

    # Get assignments with related data
    assignments_data = query.limit(limit).all()

    # Format response
    assignments = []
    for assignment in assignments_data:
        # Get cycle details
        cycle = db.query(ReviewCycle).filter(ReviewCycle.id == assignment.cycle_id).first()

        # Get reviewee details (only for peer and supervisor reviews)
        reviewee_name = None
        if assignment.review_type != 'self':
            reviewee = db.query(User).filter(User.id == assignment.reviewee_id).first()
            reviewee_name = reviewee.name if reviewee else "Unknown"

        # Calculate progress based on responses
        # Get trait IDs for this cycle
        cycle_trait_ids = [ct.trait_id for ct in db.query(ReviewCycleTrait).filter(
            ReviewCycleTrait.cycle_id == assignment.cycle_id
        ).all()]

        # Count total questions for this review type
        questions_query = db.query(ReviewQuestion).filter(
            ReviewQuestion.trait_id.in_(cycle_trait_ids)
        )

        # Filter by review type
        if assignment.review_type == 'self':
            questions_query = questions_query.filter(ReviewQuestion.applies_to_self == True)
        elif assignment.review_type == 'peer':
            questions_query = questions_query.filter(ReviewQuestion.applies_to_peer == True)
        elif assignment.review_type == 'supervisor':
            questions_query = questions_query.filter(ReviewQuestion.applies_to_supervisor == True)

        total_questions = questions_query.count()

        completed_responses = db.query(ReviewResponseModel).filter(
            ReviewResponseModel.assignment_id == assignment.id,
            ReviewResponseModel.rating.isnot(None)
        ).count()

        progress = (completed_responses / total_questions * 100) if total_questions > 0 else 0

        assignments.append({
            "id": str(assignment.id),
            "review_type": assignment.review_type,
            "cycle_id": str(assignment.cycle_id),
            "cycle_title": cycle.name if cycle else "Unknown Cycle",
            "reviewee_name": reviewee_name,
            "due_date": cycle.end_date if cycle else None,
            "status": assignment.status,
            "progress": round(progress, 1),
            "total_questions": total_questions,
            "completed_questions": completed_responses,
            "completed_at": assignment.completed_at
        })

    return assignments

@router.get("/assignments/{assignment_id}")
async def get_review_assignment(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific review assignment details using ReviewAssignment model"""

    # Get the assignment
    assignment = db.query(ReviewAssignment).filter(ReviewAssignment.id == assignment_id).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Check if user has access (must be the reviewer)
    if assignment.reviewer_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get cycle details
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == assignment.cycle_id).first()

    # Get reviewee details (only for peer and supervisor reviews)
    reviewee_name = None
    if assignment.review_type != 'self':
        reviewee = db.query(User).filter(User.id == assignment.reviewee_id).first()
        reviewee_name = reviewee.name if reviewee else "Unknown"

    # Determine the reviewee for org/level filtering
    # For self reviews the reviewee is the reviewer themselves
    reviewee_id = assignment.reviewee_id if assignment.reviewee_id else current_user.user_id
    reviewee = db.query(User).filter(User.id == reviewee_id).first()

    # Get traits applicable to the reviewee (respects org hierarchy + grade level)
    from utils.trait_inheritance import TraitInheritanceService
    trait_service = TraitInheritanceService(db)
    applicable_traits = trait_service.get_applicable_traits_for_user(reviewee_id)
    applicable_trait_ids = {t.id for t in applicable_traits}

    # Intersect with traits actually assigned to this cycle
    cycle_traits = db.query(ReviewCycleTrait).filter(
        ReviewCycleTrait.cycle_id == assignment.cycle_id
    ).all()
    trait_ids = [ct.trait_id for ct in cycle_traits if ct.trait_id in applicable_trait_ids]

    questions_query = db.query(ReviewQuestion).filter(
        ReviewQuestion.trait_id.in_(trait_ids)
    )

    # Filter by review type
    if assignment.review_type == 'self':
        questions_query = questions_query.filter(ReviewQuestion.applies_to_self == True)
    elif assignment.review_type == 'peer':
        questions_query = questions_query.filter(ReviewQuestion.applies_to_peer == True)
    elif assignment.review_type == 'supervisor':
        questions_query = questions_query.filter(ReviewQuestion.applies_to_supervisor == True)

    questions = questions_query.all()

    # Format questions with trait information
    formatted_questions = []
    for question in questions:
        trait = db.query(ReviewTrait).filter(ReviewTrait.id == question.trait_id).first()
        formatted_questions.append({
            "id": str(question.id),
            "question_text": question.question_text,
            "trait_id": str(question.trait_id),
            "trait_name": trait.name if trait else "Unknown"
        })

    # Get all responses for this assignment
    responses = db.query(ReviewResponseModel).filter(
        ReviewResponseModel.assignment_id == assignment_id
    ).all()

    responses_list = [{
        "question_id": str(r.question_id),
        "rating": r.rating
    } for r in responses]

    return {
        "id": str(assignment.id),
        "review_type": assignment.review_type,
        "cycle_id": str(assignment.cycle_id),
        "cycle_title": cycle.name if cycle else "Unknown Cycle",
        "reviewee_name": reviewee_name,
        "due_date": cycle.end_date if cycle else None,
        "status": assignment.status,
        "questions": formatted_questions,
        "responses": responses_list
    }

@router.get("/assignments/{assignment_id}/questions")
async def get_review_questions(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get questions for a review assignment"""

    # Get the assignment
    assignment = db.query(ReviewAssignment).filter(ReviewAssignment.id == assignment_id).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Check if user has access
    if assignment.reviewer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get questions based on review type and cycle
    review_type = assignment.review_type
    cycle_id = assignment.cycle_id

    # Get all traits associated with this cycle
    cycle_traits = db.query(ReviewCycleTrait).filter(
        ReviewCycleTrait.cycle_id == cycle_id
    ).all()

    trait_ids = [ct.trait_id for ct in cycle_traits]

    # Get questions for these traits filtered by review type
    questions_query = db.query(ReviewQuestion).filter(
        ReviewQuestion.trait_id.in_(trait_ids)
    )

    # Filter by review type
    if review_type == 'self':
        questions_query = questions_query.filter(ReviewQuestion.applies_to_self == True)
    elif review_type == 'peer':
        questions_query = questions_query.filter(ReviewQuestion.applies_to_peer == True)
    elif review_type == 'supervisor':
        questions_query = questions_query.filter(ReviewQuestion.applies_to_supervisor == True)

    questions = questions_query.all()

    # Format questions with trait information
    formatted_questions = []
    for question in questions:
        trait = db.query(ReviewTrait).filter(ReviewTrait.id == question.trait_id).first()
        formatted_questions.append({
            "id": str(question.id),
            "question_text": question.question_text,
            "trait_id": str(question.trait_id),
            "trait_name": trait.name if trait else "Unknown",
            "created_at": question.created_at
        })

    return formatted_questions

@router.post("/responses")
async def save_review_responses(
    response_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save review responses (draft mode)"""
    
    assignment_id = response_data.get("assignment_id")
    responses = response_data.get("responses", {})
    
    if not assignment_id:
        raise HTTPException(status_code=400, detail="Assignment ID is required")
    
    # Try regular review first
    review = db.query(Review).filter(Review.id == assignment_id).first()
    if review:
        if review.reviewee_id != current_user.user_id:
            # Check supervisor permissions
            permission_engine = get_permission_engine(db)
            if not permission_engine.check_permission(current_user, "reviews:supervise"):
                raise HTTPException(status_code=403, detail="Access denied")
        
        review.responses = responses
        review.completion_percentage = _calculate_completion_percentage(responses)
        db.commit()
        
        return {"message": "Responses saved successfully"}

    raise HTTPException(status_code=404, detail="Assignment not found")

# Removed duplicate submit endpoint - using the one at line 3906 instead

@router.get("/cycles/{cycle_id}/analytics")
async def get_cycle_analytics(
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed analytics for a review cycle"""
    
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Review cycle not found")
    
    permission_engine = get_permission_engine(db)
    if not (current_user.is_superuser or permission_engine.check_permission(current_user, "reviews:analytics:view")):
        # Check if user created this cycle
        if cycle.created_by != current_user.user_id:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get all reviews for this cycle
    reviews = db.query(Review).filter(Review.cycle_id == cycle_id).all()
    peer_reviews = []

    analytics = _generate_comprehensive_cycle_analytics(cycle, reviews, peer_reviews, db)
    
    return analytics

@router.get("/cycles/{cycle_id}/progress")
async def get_cycle_progress(
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get progress tracking for a review cycle"""
    
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Review cycle not found")
    
    permission_engine = get_permission_engine(db)
    if not (current_user.is_superuser or permission_engine.check_permission(current_user, "reviews:read:all")):
        if cycle.created_by != current_user.user_id:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    reviews = db.query(Review).filter(Review.cycle_id == cycle_id).all()

    total_reviews = len(reviews)
    completed_reviews = len([r for r in reviews if r.status in ['completed', 'submitted']])

    progress = {
        "cycle_id": cycle_id,
        "total_participants": len(set([r.reviewee_id for r in reviews])),
        "total_reviews": total_reviews,
        "completed_reviews": completed_reviews,
        "pending_reviews": total_reviews - completed_reviews,
        "completion_rate": round((completed_reviews / total_reviews * 100) if total_reviews > 0 else 0, 1),
        "review_types": {
            "self_reviews": {
                "total": len([r for r in reviews if r.type == 'self']),
                "completed": len([r for r in reviews if r.type == 'self' and r.status in ['completed', 'submitted']])
            },
            "supervisor_reviews": {
                "total": len([r for r in reviews if r.type == 'supervisor']),
                "completed": len([r for r in reviews if r.type == 'supervisor' and r.status in ['completed', 'submitted']])
            }
        },
        "timeline": {
            "start_date": cycle.start_date.isoformat(),
            "end_date": cycle.end_date.isoformat(),
            "days_remaining": max(0, (cycle.end_date - datetime.utcnow()).days)
        }
    }
    
    return progress

@router.get("/cycles/{cycle_id}/user-scores")
async def get_cycle_user_scores(
    cycle_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get review progress and scores for all participants in a cycle.
    Shows every participant (based on assignments), not just those with final scores.
    """

    # Verify cycle exists
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Review cycle not found")

    # Get all unique reviewees (participants) who have assignments in this cycle
    reviewee_rows = db.query(ReviewAssignment.reviewee_id).filter(
        ReviewAssignment.cycle_id == cycle_id
    ).distinct().all()
    reviewee_ids = [row[0] for row in reviewee_rows]

    if not reviewee_ids:
        return []

    # Load any existing final scores (may be empty until all assignments done)
    review_scores = db.query(ReviewScore).filter(
        ReviewScore.cycle_id == cycle_id
    ).all()

    # Group scores by user
    score_map = {}
    for score in review_scores:
        uid = str(score.user_id)
        if uid not in score_map:
            score_map[uid] = {'trait_scores': {}, 'total_score': 0, 'trait_count': 0}
        trait_score = score.weighted_score or score.self_score or 0
        score_map[uid]['trait_scores'][str(score.trait_id)] = trait_score
        score_map[uid]['total_score'] += trait_score
        score_map[uid]['trait_count'] += 1

    result = []
    for reviewee_id in reviewee_ids:
        user = db.query(User).filter(User.id == reviewee_id).first()
        if not user:
            continue

        uid_str = str(reviewee_id)

        # Build display name
        name_parts = [user.first_name]
        if user.middle_name:
            name_parts.append(user.middle_name)
        name_parts.append(user.last_name)
        user_name = " ".join(filter(None, name_parts))

        # Get department name
        department_name = None
        if user.organization_id:
            org = db.query(Organization).filter(Organization.id == user.organization_id).first()
            if org:
                department_name = org.name

        # Count assignments to determine completion status
        total_assignments = db.query(ReviewAssignment).filter(
            ReviewAssignment.cycle_id == cycle_id,
            ReviewAssignment.reviewee_id == reviewee_id
        ).count()

        completed_assignments = db.query(ReviewAssignment).filter(
            ReviewAssignment.cycle_id == cycle_id,
            ReviewAssignment.reviewee_id == reviewee_id,
            ReviewAssignment.status == 'completed'
        ).count()

        if completed_assignments == 0:
            completion_status = 'pending'
        elif completed_assignments < total_assignments:
            completion_status = 'in_progress'
        else:
            completion_status = 'completed'

        # Scores (may be None/empty until all assignments finished and scored)
        scores = score_map.get(uid_str, {})
        trait_scores = scores.get('trait_scores', {})
        trait_count = scores.get('trait_count', 0)
        total_score = scores.get('total_score', 0)
        overall_score = round(total_score / trait_count, 2) if trait_count > 0 else None

        result.append({
            'user_id': uid_str,
            'user_name': user_name,
            'department_name': department_name,
            'trait_scores': trait_scores,
            'overall_score': overall_score,
            'completion_status': completion_status,
            'completed_assignments': completed_assignments,
            'total_assignments': total_assignments,
        })

    return result

def _compute_cycle_completion_rate(cycle_id: str, db: Session) -> float:
    """Compute the percentage of completed assignments for a cycle."""
    total = db.query(ReviewAssignment).filter(
        ReviewAssignment.cycle_id == cycle_id
    ).count()
    if total == 0:
        return 0.0
    completed = db.query(ReviewAssignment).filter(
        ReviewAssignment.cycle_id == cycle_id,
        ReviewAssignment.status == 'completed'
    ).count()
    return round(completed / total * 100, 1)


# Helper functions for advanced features

def _generate_cycle_overview(cycle: ReviewCycle, reviews: List[Review], peer_reviews: List) -> dict:
    """Generate comprehensive cycle overview"""
    return {
        "total_participants": len(set([r.reviewee_id for r in reviews])),
        "total_reviews": len(reviews),
        "total_peer_reviews": len(peer_reviews),
        "completion_rate": len([r for r in reviews if r.status == "submitted"]) / len(reviews) if reviews else 0,
        "average_completion_time": sum([r.time_spent for r in reviews if r.time_spent]) / len(reviews) if reviews else 0,
        "quality_indicators": {
            "avg_response_length": _calculate_avg_response_length(reviews),
            "thoughtfulness_score": _calculate_thoughtfulness_score(reviews),
            "consistency_score": _calculate_consistency_score(reviews)
        }
    }

def _analyze_participation(reviews: List[Review], peer_reviews: List) -> dict:
    """Analyze participation patterns"""
    return {
        "participation_by_type": {
            "self_reviews": len([r for r in reviews if r.type == "self"]),
            "supervisor_reviews": len([r for r in reviews if r.type == "supervisor"]),
            "peer_reviews": len(peer_reviews)
        },
        "engagement_metrics": {
            "high_engagement": len([r for r in reviews if r.time_spent and r.time_spent > 60]),
            "medium_engagement": len([r for r in reviews if r.time_spent and 30 <= r.time_spent <= 60]),
            "low_engagement": len([r for r in reviews if r.time_spent and r.time_spent < 30])
        },
        "completion_timeline": _analyze_completion_timeline(reviews, peer_reviews)
    }

def _analyze_performance_patterns(reviews: List[Review]) -> dict:
    """Analyze performance patterns across reviews"""
    return {
        "performance_distribution": _calculate_performance_distribution(reviews),
        "improvement_trends": _identify_improvement_trends(reviews),
        "consistency_patterns": _analyze_consistency_patterns(reviews),
        "outlier_analysis": _identify_performance_outliers(reviews)
    }

def _detect_and_analyze_bias(reviews: List[Review], peer_reviews: List) -> dict:
    """Comprehensive bias detection and analysis"""
    return {
        "overall_bias_risk": _calculate_overall_bias_risk(reviews, peer_reviews),
        "specific_biases": {
            "recency_bias": _detect_recency_bias(reviews),
            "halo_effect": _detect_halo_effect(reviews),
            "similarity_bias": _detect_similarity_bias(peer_reviews),
            "leniency_bias": _detect_leniency_bias(reviews)
        },
        "demographic_analysis": _analyze_demographic_bias(reviews, None),  # db not available here
        "mitigation_priority": _prioritize_bias_mitigation(reviews, peer_reviews)
    }

# Bias detection functions - TODO: Implement proper algorithms
def _calculate_overall_bias_score(reviews, peer_reviews):
    """Calculate overall bias risk score based on review patterns"""
    if not reviews and not peer_reviews:
        return 0.0
    
    # Basic implementation - analyze rating patterns
    all_ratings = []
    for review in reviews:
        if review.responses:
            for key, response in review.responses.items():
                if isinstance(response, (int, float)) and 1 <= response <= 5:
                    all_ratings.append(response)
    
    if not all_ratings:
        return 0.0
    
    # Simple bias indicators
    avg_rating = sum(all_ratings) / len(all_ratings)
    rating_variance = sum((r - avg_rating) ** 2 for r in all_ratings) / len(all_ratings)
    
    # Higher variance indicates less bias, score between 0-1
    bias_score = max(0.0, min(1.0, (5.0 - rating_variance) / 5.0))
    return bias_score

def _detect_recency_bias(reviews):
    """Detect if recent events disproportionately influence ratings"""
    if len(reviews) < 2:
        return {"detected": False, "severity": "low", "details": "Insufficient data"}
    
    # Sort by creation date and compare recent vs older ratings
    recent_reviews = sorted(reviews, key=lambda r: r.created_at, reverse=True)[:len(reviews)//2]
    older_reviews = sorted(reviews, key=lambda r: r.created_at, reverse=True)[len(reviews)//2:]
    
    recent_avg = _get_average_rating(recent_reviews)
    older_avg = _get_average_rating(older_reviews)
    
    if recent_avg is None or older_avg is None:
        return {"detected": False, "severity": "low", "details": "No rating data"}
    
    difference = abs(recent_avg - older_avg)
    severity = "high" if difference > 1.0 else ("medium" if difference > 0.5 else "low")
    
    return {
        "detected": difference > 0.5,
        "severity": severity,
        "details": f"Recent avg: {recent_avg:.2f}, Older avg: {older_avg:.2f}"
    }

def _detect_halo_effect(reviews):
    """Detect if one strong trait influences all ratings"""
    if not reviews:
        return {"detected": False, "severity": "low", "details": "No review data"}
    
    correlations = []
    for review in reviews:
        if not review.responses:
            continue
        
        ratings = [v for v in review.responses.values() if isinstance(v, (int, float)) and 1 <= v <= 5]
        if len(ratings) < 2:
            continue
        
        # Simple correlation check - if all ratings are very similar, possible halo effect
        rating_range = max(ratings) - min(ratings)
        correlations.append(rating_range)
    
    if not correlations:
        return {"detected": False, "severity": "low", "details": "No rating patterns found"}
    
    avg_range = sum(correlations) / len(correlations)
    severity = "high" if avg_range < 0.5 else ("medium" if avg_range < 1.0 else "low")
    
    return {
        "detected": avg_range < 1.0,
        "severity": severity,
        "details": f"Average rating range: {avg_range:.2f}"
    }

def _detect_similarity_bias(peer_reviews):
    """Detect if similar peers rate each other more favorably"""
    # TODO: Implement based on peer demographic/role similarity
    return {"detected": False, "severity": "low", "details": "Not implemented"}

def _detect_leniency_bias(reviews):
    """Detect if reviewers are consistently too lenient"""
    if not reviews:
        return {"detected": False, "severity": "low", "details": "No review data"}
    
    all_ratings = []
    for review in reviews:
        if review.responses:
            ratings = [v for v in review.responses.values() if isinstance(v, (int, float)) and 1 <= v <= 5]
            all_ratings.extend(ratings)
    
    if not all_ratings:
        return {"detected": False, "severity": "low", "details": "No ratings found"}
    
    avg_rating = sum(all_ratings) / len(all_ratings)
    high_ratings_percent = len([r for r in all_ratings if r >= 4]) / len(all_ratings)
    
    severity = "high" if avg_rating > 4.2 and high_ratings_percent > 0.8 else \
              ("medium" if avg_rating > 3.8 and high_ratings_percent > 0.6 else "low")
    
    return {
        "detected": avg_rating > 3.8 and high_ratings_percent > 0.6,
        "severity": severity,
        "details": f"Avg rating: {avg_rating:.2f}, High ratings: {high_ratings_percent:.1%}"
    }

def _detect_central_tendency_bias(reviews):
    """Detect if reviewers avoid extreme ratings"""
    if not reviews:
        return {"detected": False, "severity": "low", "details": "No review data"}
    
    all_ratings = []
    for review in reviews:
        if review.responses:
            ratings = [v for v in review.responses.values() if isinstance(v, (int, float)) and 1 <= v <= 5]
            all_ratings.extend(ratings)
    
    if not all_ratings:
        return {"detected": False, "severity": "low", "details": "No ratings found"}
    
    extreme_ratings = len([r for r in all_ratings if r <= 2 or r >= 4]) / len(all_ratings)
    middle_ratings = len([r for r in all_ratings if r == 3]) / len(all_ratings)
    
    severity = "high" if middle_ratings > 0.6 else ("medium" if middle_ratings > 0.4 else "low")
    
    return {
        "detected": middle_ratings > 0.4 and extreme_ratings < 0.3,
        "severity": severity,
        "details": f"Middle ratings: {middle_ratings:.1%}, Extreme ratings: {extreme_ratings:.1%}"
    }

def _analyze_demographic_bias(reviews, db):
    """Analyze potential demographic bias patterns"""
    # TODO: Implement demographic analysis when user demographic data is available
    return {"message": "Demographic bias analysis requires additional user demographic data"}

def _analyze_reviewer_bias_patterns(peer_reviews):
    """Analyze individual reviewer bias patterns"""
    # TODO: Implement reviewer-specific bias pattern analysis
    return {"message": "Reviewer bias pattern analysis not yet implemented"}

def _generate_bias_mitigation_recommendations(reviews, peer_reviews):
    """Generate recommendations to reduce identified bias"""
    recommendations = []
    
    if _detect_leniency_bias(reviews)["detected"]:
        recommendations.append({
            "type": "leniency_bias",
            "recommendation": "Provide calibration training to ensure rating standards",
            "priority": "high"
        })
    
    if _detect_halo_effect(reviews)["detected"]:
        recommendations.append({
            "type": "halo_effect",
            "recommendation": "Use structured rating forms with specific criteria for each competency",
            "priority": "medium"
        })
    
    return recommendations

def _calculate_overall_bias_risk(reviews, peer_reviews):
    """Calculate overall bias risk level"""
    risk_factors = 0
    
    if _detect_leniency_bias(reviews)["detected"]:
        risk_factors += 1
    if _detect_halo_effect(reviews)["detected"]:
        risk_factors += 1
    if _detect_recency_bias(reviews)["detected"]:
        risk_factors += 1
    
    if risk_factors >= 2:
        return "high"
    elif risk_factors == 1:
        return "medium"
    else:
        return "low"

def _prioritize_bias_mitigation(reviews, peer_reviews):
    """Prioritize bias mitigation actions"""
    priorities = []
    
    leniency = _detect_leniency_bias(reviews)
    if leniency["detected"] and leniency["severity"] == "high":
        priorities.append({"type": "leniency_bias", "priority": 1})
    
    halo = _detect_halo_effect(reviews)
    if halo["detected"] and halo["severity"] == "high":
        priorities.append({"type": "halo_effect", "priority": 2})
    
    return priorities

def _get_average_rating(reviews):
    """Helper function to get average rating from reviews"""
    all_ratings = []
    for review in reviews:
        if review.responses:
            ratings = [v for v in review.responses.values() if isinstance(v, (int, float)) and 1 <= v <= 5]
            all_ratings.extend(ratings)
    
    return sum(all_ratings) / len(all_ratings) if all_ratings else None

# AI insights functions - Basic implementations
def _extract_performance_highlights(responses):
    """Extract key performance highlights from review responses"""
    highlights = []
    if not responses:
        return highlights
    
    # Look for high ratings or positive keywords in text responses
    for key, value in responses.items():
        if isinstance(value, (int, float)) and value >= 4:
            highlights.append(f"High rating in {key.replace('_', ' ')}: {value}/5")
        elif isinstance(value, str) and any(word in value.lower() for word in ['excellent', 'outstanding', 'exceptional', 'exceeded']):
            highlights.append(f"Positive feedback in {key.replace('_', ' ')}")
    
    return highlights

def _identify_development_areas(responses):
    """Identify areas needing development from review responses"""
    development_areas = []
    if not responses:
        return development_areas
    
    # Look for low ratings or improvement keywords in text responses
    for key, value in responses.items():
        if isinstance(value, (int, float)) and value <= 2:
            development_areas.append(f"Improvement needed in {key.replace('_', ' ')}: {value}/5")
        elif isinstance(value, str) and any(word in value.lower() for word in ['improve', 'develop', 'needs work', 'lacking']):
            development_areas.append(f"Development opportunity in {key.replace('_', ' ')}")
    
    return development_areas

def _analyze_review_sentiment(responses):
    """Analyze sentiment of review responses"""
    if not responses:
        return {"overall": "neutral", "details": {}}
    
    positive_indicators = ['excellent', 'outstanding', 'great', 'strong', 'exceeded', 'exceptional']
    negative_indicators = ['poor', 'lacking', 'needs improvement', 'below expectations', 'weak']
    
    sentiment_scores = []
    details = {}
    
    for key, value in responses.items():
        if isinstance(value, str):
            positive_count = sum(1 for word in positive_indicators if word in value.lower())
            negative_count = sum(1 for word in negative_indicators if word in value.lower())
            
            if positive_count > negative_count:
                sentiment = "positive"
                score = min(1.0, positive_count * 0.3)
            elif negative_count > positive_count:
                sentiment = "negative"
                score = -min(1.0, negative_count * 0.3)
            else:
                sentiment = "neutral"
                score = 0.0
            
            sentiment_scores.append(score)
            details[key] = {"sentiment": sentiment, "score": score}
        elif isinstance(value, (int, float)) and 1 <= value <= 5:
            # Convert rating to sentiment
            if value >= 4:
                sentiment_scores.append(0.5)
                details[key] = {"sentiment": "positive", "score": 0.5}
            elif value <= 2:
                sentiment_scores.append(-0.5)
                details[key] = {"sentiment": "negative", "score": -0.5}
            else:
                sentiment_scores.append(0.0)
                details[key] = {"sentiment": "neutral", "score": 0.0}
    
    if sentiment_scores:
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        overall = "positive" if avg_sentiment > 0.2 else ("negative" if avg_sentiment < -0.2 else "neutral")
    else:
        overall = "neutral"
    
    return {"overall": overall, "details": details, "score": sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0}

def _extract_review_topics(responses):
    """Extract main topics from review responses"""
    topics = []
    if not responses:
        return topics
    
    # Basic keyword-based topic extraction
    topic_keywords = {
        "Leadership": ["lead", "leadership", "manage", "team", "direct", "guide"],
        "Communication": ["communicate", "presentation", "meeting", "discuss", "explain"],
        "Technical Skills": ["technical", "coding", "programming", "analysis", "problem solving"],
        "Collaboration": ["collaborate", "teamwork", "cooperation", "work with", "partner"],
        "Innovation": ["innovative", "creative", "new ideas", "improve", "solution"],
        "Quality": ["quality", "accuracy", "detail", "thorough", "careful"]
    }
    
    text_content = " ".join([str(v) for v in responses.values() if isinstance(v, str)]).lower()
    
    for topic, keywords in topic_keywords.items():
        if any(keyword in text_content for keyword in keywords):
            topics.append(topic)
    
    return topics

def _summarize_strengths(responses):
    """Summarize key strengths from review responses"""
    strengths = []
    if not responses:
        return strengths
    
    # Extract from high ratings and positive text
    for key, value in responses.items():
        if isinstance(value, (int, float)) and value >= 4:
            strengths.append(key.replace('_', ' ').title())
        elif isinstance(value, str):
            # Look for strength-related keywords
            strength_words = ['strength', 'strong', 'excellent', 'outstanding', 'skilled', 'proficient']
            if any(word in value.lower() for word in strength_words):
                strengths.append(f"Noted strength in {key.replace('_', ' ')}")
    
    return list(set(strengths))  # Remove duplicates

def _generate_improvement_suggestions(responses):
    """Generate specific improvement suggestions based on responses"""
    suggestions = []
    if not responses:
        return suggestions
    
    # Basic suggestions based on low ratings or improvement keywords
    for key, value in responses.items():
        if isinstance(value, (int, float)) and value <= 2:
            area = key.replace('_', ' ').title()
            suggestions.append(f"Focus on developing {area} through targeted training and practice")
        elif isinstance(value, str) and 'improve' in value.lower():
            suggestions.append(f"Address feedback in {key.replace('_', ' ')} area")
    
    # Add generic suggestions if specific ones not found
    if not suggestions:
        suggestions = [
            "Continue building on current strengths",
            "Seek feedback regularly from peers and supervisors",
            "Consider professional development opportunities"
        ]
    
    return suggestions

def _recommend_career_development(responses):
    """Recommend career development opportunities based on review data"""
    recommendations = []
    if not responses:
        return recommendations
    
    # Basic recommendations based on strengths and development areas
    topics = _extract_review_topics(responses)
    strengths = _summarize_strengths(responses)
    
    if "Leadership" in topics:
        recommendations.append({
            "area": "Leadership Development",
            "suggestion": "Consider leadership training programs or mentoring opportunities",
            "priority": "medium"
        })
    
    if "Technical Skills" in topics:
        recommendations.append({
            "area": "Technical Advancement",
            "suggestion": "Pursue advanced technical certifications or specialized training",
            "priority": "high"
        })
    
    if len(strengths) > 3:
        recommendations.append({
            "area": "Career Advancement",
            "suggestion": "Strong performance indicates readiness for increased responsibilities",
            "priority": "high"
        })
    
    return recommendations

# Performance dashboard functions - Basic implementations
def _generate_performance_summary(reviews, peer_reviews):
    """Generate performance summary from reviews"""
    if not reviews and not peer_reviews:
        return {
            "overall_score": 0,
            "trend": "no_data",
            "key_strengths": [],
            "development_areas": [],
            "peer_rating": 0,
            "supervisor_rating": 0,
            "self_assessment": 0
        }
    
    # Calculate ratings by type
    self_ratings = []
    supervisor_ratings = []
    peer_ratings = []
    
    for review in reviews:
        if review.responses:
            ratings = [v for v in review.responses.values() if isinstance(v, (int, float)) and 1 <= v <= 5]
            if ratings:
                avg_rating = sum(ratings) / len(ratings)
                if review.type == 'self':
                    self_ratings.append(avg_rating)
                elif review.type == 'supervisor':
                    supervisor_ratings.append(avg_rating)
    
    for peer_review in peer_reviews:
        if peer_review.responses:
            ratings = [v for v in peer_review.responses.values() if isinstance(v, (int, float)) and 1 <= v <= 5]
            if ratings:
                peer_ratings.append(sum(ratings) / len(ratings))
    
    # Compile summary
    return {
        "overall_score": round(sum(self_ratings + supervisor_ratings + peer_ratings) / 
                             len(self_ratings + supervisor_ratings + peer_ratings) * 20) if (self_ratings + supervisor_ratings + peer_ratings) else 0,
        "trend": "improving",  # Would need historical data to determine
        "key_strengths": _extract_common_strengths(reviews + peer_reviews),
        "development_areas": _extract_common_development_areas(reviews + peer_reviews),
        "peer_rating": sum(peer_ratings) / len(peer_ratings) if peer_ratings else 0,
        "supervisor_rating": sum(supervisor_ratings) / len(supervisor_ratings) if supervisor_ratings else 0,
        "self_assessment": sum(self_ratings) / len(self_ratings) if self_ratings else 0
    }

def _analyze_goal_achievement(user_id, db):
    """Analyze goal achievement for user - placeholder for now"""
    # TODO: Implement once goal models are integrated
    return {
        "total_goals": 0,
        "completed_goals": 0,
        "in_progress_goals": 0,
        "achievement_rate": 0,
        "top_achievements": []
    }

def _analyze_competency_development(reviews):
    """Analyze competency development from reviews"""
    if not reviews:
        return {}
    
    competencies = {}
    for review in reviews:
        if review.responses:
            topics = _extract_review_topics(review.responses)
            for topic in topics:
                if topic not in competencies:
                    competencies[topic] = {"mentions": 0, "avg_score": 0, "ratings": []}
                competencies[topic]["mentions"] += 1
                
                # Extract ratings for this topic area
                ratings = [v for k, v in review.responses.items() if isinstance(v, (int, float)) and topic.lower() in k.lower()]
                if ratings:
                    competencies[topic]["ratings"].extend(ratings)
    
    # Calculate averages
    for comp in competencies.values():
        if comp["ratings"]:
            comp["avg_score"] = sum(comp["ratings"]) / len(comp["ratings"])
        else:
            comp["avg_score"] = 3.0  # Default neutral
        del comp["ratings"]  # Remove raw ratings
    
    return competencies

def _analyze_peer_feedback_trends(peer_reviews):
    """Analyze trends in peer feedback"""
    if not peer_reviews:
        return {"total_reviews": 0, "avg_rating": 0, "themes": []}
    
    all_ratings = []
    all_themes = []
    
    for review in peer_reviews:
        if review.responses:
            ratings = [v for v in review.responses.values() if isinstance(v, (int, float)) and 1 <= v <= 5]
            all_ratings.extend(ratings)
            all_themes.extend(_extract_review_topics(review.responses))
    
    from collections import Counter
    theme_counts = Counter(all_themes)
    
    return {
        "total_reviews": len(peer_reviews),
        "avg_rating": sum(all_ratings) / len(all_ratings) if all_ratings else 0,
        "themes": [{"theme": theme, "count": count} for theme, count in theme_counts.most_common(5)],
        "trend": "stable"  # Would need historical data
    }

def _track_development_progress(reviews):
    """Track development progress over time"""
    if not reviews:
        return {"progress_indicators": [], "improvement_areas": []}
    
    # Sort reviews by date
    sorted_reviews = sorted(reviews, key=lambda r: r.created_at)
    
    progress_indicators = []
    if len(sorted_reviews) >= 2:
        first_review = sorted_reviews[0]
        latest_review = sorted_reviews[-1]
        
        first_avg = _get_review_average(first_review)
        latest_avg = _get_review_average(latest_review)
        
        if first_avg and latest_avg:
            improvement = latest_avg - first_avg
            progress_indicators.append({
                "metric": "Overall Performance",
                "change": improvement,
                "direction": "improving" if improvement > 0 else ("declining" if improvement < 0 else "stable")
            })
    
    return {
        "progress_indicators": progress_indicators,
        "improvement_areas": _identify_development_areas(latest_review.responses if sorted_reviews else {})
    }

def _extract_recognition_highlights(reviews, peer_reviews):
    """Extract recognition and achievements from reviews"""
    highlights = []
    
    all_reviews = reviews + peer_reviews
    for review in all_reviews:
        if hasattr(review, 'responses') and review.responses:
            # Look for recognition keywords
            for key, value in review.responses.items():
                if isinstance(value, str):
                    recognition_words = ['recognition', 'award', 'achievement', 'outstanding', 'exceptional', 'exceeded expectations']
                    if any(word in value.lower() for word in recognition_words):
                        highlights.append({
                            "type": "peer_recognition" if hasattr(review, 'reviewer_id') else "performance_recognition",
                            "description": f"Recognition noted in {key.replace('_', ' ')}",
                            "date": review.created_at.isoformat() if review.created_at else None
                        })
                elif isinstance(value, (int, float)) and value == 5:
                    highlights.append({
                        "type": "top_rating",
                        "description": f"Excellent rating in {key.replace('_', ' ')}: {value}/5",
                        "date": review.created_at.isoformat() if review.created_at else None
                    })
    
    return highlights

def _generate_growth_recommendations(user_id, reviews, peer_reviews, db):
    """Generate growth recommendations based on review data"""
    recommendations = []
    
    if not reviews and not peer_reviews:
        return recommendations
    
    # Analyze strengths and development areas
    all_responses = []
    for review in reviews + peer_reviews:
        if hasattr(review, 'responses') and review.responses:
            all_responses.append(review.responses)
    
    if all_responses:
        # Combine all responses
        combined_responses = {}
        for responses in all_responses:
            combined_responses.update(responses)
        
        development_areas = _identify_development_areas(combined_responses)
        career_recs = _recommend_career_development(combined_responses)
        
        # Convert to growth recommendations format
        for area in development_areas:
            recommendations.append({
                "area": "Skill Development",
                "recommendation": area,
                "priority": "medium"
            })
        
        recommendations.extend(career_recs)
    
    return recommendations

def _extract_common_strengths(reviews):
    """Extract commonly mentioned strengths across reviews"""
    all_strengths = []
    for review in reviews:
        if hasattr(review, 'responses') and review.responses:
            all_strengths.extend(_summarize_strengths(review.responses))
    
    from collections import Counter
    strength_counts = Counter(all_strengths)
    return [strength for strength, count in strength_counts.most_common(5) if count > 1]

def _extract_common_development_areas(reviews):
    """Extract commonly mentioned development areas across reviews"""
    all_areas = []
    for review in reviews:
        if hasattr(review, 'responses') and review.responses:
            all_areas.extend(_identify_development_areas(review.responses))
    
    from collections import Counter
    area_counts = Counter(all_areas)
    return [area for area, count in area_counts.most_common(3) if count > 1]

def _get_review_average(review):
    """Get average rating from a review"""
    if not hasattr(review, 'responses') or not review.responses:
        return None
    
    ratings = [v for v in review.responses.values() if isinstance(v, (int, float)) and 1 <= v <= 5]
    return sum(ratings) / len(ratings) if ratings else None

# Analytics functions - Basic implementations
def _calculate_avg_response_length(reviews):
    """Calculate average response length for text responses"""
    text_lengths = []
    for review in reviews:
        if review.responses:
            for value in review.responses.values():
                if isinstance(value, str) and len(value.strip()) > 0:
                    text_lengths.append(len(value.strip()))
    
    return sum(text_lengths) / len(text_lengths) if text_lengths else 0

def _calculate_thoughtfulness_score(reviews):
    """Calculate thoughtfulness score based on response quality"""
    if not reviews:
        return 0.0
    
    total_score = 0
    review_count = 0
    
    for review in reviews:
        if not review.responses:
            continue
        
        review_score = 0
        response_count = 0
        
        for value in review.responses.values():
            if isinstance(value, str):
                # Basic thoughtfulness indicators
                word_count = len(value.split())
                has_examples = any(word in value.lower() for word in ['example', 'instance', 'specifically', 'such as'])
                has_detail = word_count > 20
                
                score = 0.3  # Base score
                if has_examples:
                    score += 0.3
                if has_detail:
                    score += 0.4
                
                review_score += min(1.0, score)
                response_count += 1
        
        if response_count > 0:
            total_score += review_score / response_count
            review_count += 1
    
    return total_score / review_count if review_count > 0 else 0.0

def _calculate_consistency_score(reviews):
    """Calculate consistency score across reviews"""
    if len(reviews) < 2:
        return 1.0
    
    all_ratings = []
    for review in reviews:
        if review.responses:
            ratings = [v for v in review.responses.values() if isinstance(v, (int, float)) and 1 <= v <= 5]
            if ratings:
                all_ratings.append(sum(ratings) / len(ratings))
    
    if len(all_ratings) < 2:
        return 1.0
    
    # Calculate variance - lower variance means higher consistency
    mean_rating = sum(all_ratings) / len(all_ratings)
    variance = sum((r - mean_rating) ** 2 for r in all_ratings) / len(all_ratings)
    
    # Convert variance to consistency score (0-1, where 1 is most consistent)
    consistency = max(0.0, 1.0 - (variance / 4.0))  # Normalize by max possible variance
    return consistency

def _analyze_completion_timeline(reviews, peer_reviews):
    """Analyze review completion patterns over time"""
    all_reviews = reviews + peer_reviews
    if not all_reviews:
        return {"completion_pattern": "no_data", "avg_time_to_complete": 0}
    
    completion_times = []
    for review in all_reviews:
        if hasattr(review, 'submitted_at') and review.submitted_at and hasattr(review, 'created_at'):
            time_diff = (review.submitted_at - review.created_at).total_seconds() / 3600  # hours
            completion_times.append(time_diff)
    
    return {
        "completion_pattern": "consistent" if completion_times else "no_data",
        "avg_time_to_complete": sum(completion_times) / len(completion_times) if completion_times else 0,
        "total_completed": len([r for r in all_reviews if getattr(r, 'status', '') == 'submitted'])
    }

def _calculate_performance_distribution(reviews):
    """Calculate distribution of performance ratings"""
    all_ratings = []
    for review in reviews:
        if review.responses:
            ratings = [v for v in review.responses.values() if isinstance(v, (int, float)) and 1 <= v <= 5]
            all_ratings.extend(ratings)
    
    if not all_ratings:
        return {"distribution": {}, "mean": 0, "median": 0}
    
    from collections import Counter
    distribution = Counter(all_ratings)
    all_ratings.sort()
    
    return {
        "distribution": dict(distribution),
        "mean": sum(all_ratings) / len(all_ratings),
        "median": all_ratings[len(all_ratings) // 2] if all_ratings else 0
    }

def _identify_improvement_trends(reviews):
    """Identify improvement trends over time"""
    if len(reviews) < 2:
        return []
    
    sorted_reviews = sorted(reviews, key=lambda r: r.created_at)
    trends = []
    
    # Compare first and last review averages
    first_avg = _get_review_average(sorted_reviews[0])
    last_avg = _get_review_average(sorted_reviews[-1])
    
    if first_avg and last_avg:
        improvement = last_avg - first_avg
        if improvement > 0.5:
            trends.append({"type": "improvement", "magnitude": improvement, "area": "overall"})
        elif improvement < -0.5:
            trends.append({"type": "decline", "magnitude": abs(improvement), "area": "overall"})
    
    return trends

def _analyze_consistency_patterns(reviews):
    """Analyze patterns in review consistency"""
    if not reviews:
        return {"pattern": "no_data", "consistency_score": 0}
    
    consistency_score = _calculate_consistency_score(reviews)
    
    pattern = "highly_consistent" if consistency_score > 0.8 else (
        "moderately_consistent" if consistency_score > 0.6 else "inconsistent"
    )
    
    return {
        "pattern": pattern,
        "consistency_score": consistency_score,
        "review_count": len(reviews)
    }

def _identify_performance_outliers(reviews):
    """Identify performance outliers in reviews"""
    all_ratings = []
    for review in reviews:
        if review.responses:
            ratings = [v for v in review.responses.values() if isinstance(v, (int, float)) and 1 <= v <= 5]
            if ratings:
                all_ratings.append((review.id, sum(ratings) / len(ratings)))
    
    if len(all_ratings) < 3:
        return []
    
    ratings_values = [rating for _, rating in all_ratings]
    mean_rating = sum(ratings_values) / len(ratings_values)
    
    # Simple outlier detection: more than 1.5 standard deviations from mean
    outliers = []
    for review_id, rating in all_ratings:
        if abs(rating - mean_rating) > 1.5:
            outliers.append({
                "review_id": review_id,
                "rating": rating,
                "deviation": abs(rating - mean_rating),
                "type": "high_performer" if rating > mean_rating else "low_performer"
            })
    
    return outliers

def _generate_cycle_recommendations(cycle, reviews, peer_reviews):
    """Generate recommendations for improving review cycles"""
    recommendations = []
    
    if not reviews and not peer_reviews:
        recommendations.append({
            "type": "participation",
            "recommendation": "Increase participation by sending reminder notifications",
            "priority": "high"
        })
        return recommendations
    
    # Analyze completion rates
    total_reviews = len(reviews) + len(peer_reviews)
    completed_reviews = len([r for r in reviews + peer_reviews if getattr(r, 'status', '') == 'submitted'])
    completion_rate = completed_reviews / total_reviews if total_reviews > 0 else 0
    
    if completion_rate < 0.8:
        recommendations.append({
            "type": "completion",
            "recommendation": "Implement automated reminders and extend deadlines to improve completion rates",
            "priority": "high"
        })
    
    # Check for bias issues
    bias_risk = _calculate_overall_bias_risk(reviews, peer_reviews)
    if bias_risk == "high":
        recommendations.append({
            "type": "bias_mitigation",
            "recommendation": "Conduct calibration sessions to address rating bias",
            "priority": "high"
        })
    
    # Check thoughtfulness
    thoughtfulness = _calculate_thoughtfulness_score(reviews)
    if thoughtfulness < 0.5:
        recommendations.append({
            "type": "quality",
            "recommendation": "Provide training on giving constructive feedback to improve review quality",
            "priority": "medium"
        })
    
    return recommendations

# Additional Advanced Review Features

@router.post("/multi-source-feedback/{user_id}")
async def initiate_multi_source_feedback(
    user_id: int,
    feedback_config: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate 360-degree multi-source feedback collection"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    permission_engine = get_permission_engine(db)
    if not permission_engine.check_permission(current_user, "reviews:create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Create 360 review cycle
    cycle_data = {
        "name": f"360 Feedback - {user.first_name} {user.last_name}",
        "type": "360_feedback",
        "period": f"{datetime.now().year}",
        "start_date": datetime.utcnow(),
        "end_date": datetime.utcnow() + timedelta(days=feedback_config.get("duration_days", 14)),
        "phase_schedule": {
            "feedback_collection": {"duration": "10_days"},
            "analysis": {"duration": "3_days"},
            "report_generation": {"duration": "1_day"}
        },
        "components": {
            "supervisor_feedback": {"enabled": True, "weight": 30},
            "peer_feedback": {"enabled": True, "weight": 40},
            "subordinate_feedback": {"enabled": True, "weight": 20},
            "self_assessment": {"enabled": True, "weight": 10}
        },
        "target_population": {"specific_user": user_id},
        "ai_assistance": {"enabled": True}
    }
    
    cycle = ReviewCycle(
        **cycle_data,
        created_by=current_user.user_id
    )
    
    db.add(cycle)
    db.flush()
    
    # Create feedback requests
    feedback_sources = feedback_config.get("feedback_sources", {})
    
    # Self-assessment
    self_review = Review(
        cycle_id=cycle.id,
        reviewee_id=user_id,
        type="self",
        deadline=cycle.end_date
    )
    db.add(self_review)
    
    # Supervisor feedback
    if feedback_sources.get("supervisor_ids"):
        for supervisor_id in feedback_sources["supervisor_ids"]:
            supervisor_review = Review(
                cycle_id=cycle.id,
                reviewee_id=user_id,
                type="supervisor",
                deadline=cycle.end_date
            )
            db.add(supervisor_review)
    
    db.commit()

    return {
        "message": "360-degree feedback initiated successfully",
        "cycle_id": cycle.id,
        "feedback_requests": {
            "self_assessment": 1,
            "supervisor_feedback": len(feedback_sources.get("supervisor_ids", []))
        }
    }

@router.get("/competency-assessment/{user_id}")
async def get_competency_assessment(
    user_id: int,
    competency_framework: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive competency assessment for a user"""
    
    if user_id != current_user.user_id:
        permission_engine = get_permission_engine(db)
        if not permission_engine.check_permission(current_user, "performance:view:all"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get recent reviews for competency analysis
    reviews = db.query(Review).filter(
        Review.reviewee_id == user_id,
        Review.status == "submitted",
        Review.created_at >= datetime.utcnow() - timedelta(days=365)
    ).all()
    
    competency_assessment = {
        "user_profile": {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "role": user.job_title,
            "department": user.department.name if user.department else None
        },
        "competency_framework": competency_framework or "default",
        "core_competencies": _assess_core_competencies(reviews),
        "technical_skills": _assess_technical_skills(reviews, user),
        "leadership_competencies": _assess_leadership_competencies(reviews),
        "behavioral_indicators": _assess_behavioral_indicators(reviews),
        "development_needs": _identify_competency_gaps(reviews),
        "strengths_profile": _build_strengths_profile(reviews),
        "development_roadmap": _create_development_roadmap(reviews, user),
        "benchmark_comparison": _compare_to_benchmarks(reviews, user)
    }
    
    return competency_assessment

@router.post("/development-planning/{user_id}")
async def create_development_plan(
    user_id: int,
    development_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create comprehensive development plan based on review insights"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    permission_engine = get_permission_engine(db)
    if not permission_engine.check_permission(current_user, "performance:evaluate"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Analyze recent reviews for development insights
    reviews = db.query(Review).filter(
        Review.reviewee_id == user_id,
        Review.status == "submitted"
    ).order_by(Review.created_at.desc()).limit(5).all()
    
    development_plan = {
        "user_id": user_id,
        "created_by": current_user.user_id,
        "created_at": datetime.utcnow().isoformat(),
        "planning_period": development_data.get("planning_period", "12_months"),
        
        "assessment_summary": {
            "strengths": _extract_strengths_from_reviews(reviews),
            "development_areas": _extract_development_areas_from_reviews(reviews),
            "potential_rating": development_data.get("potential_rating"),
            "performance_rating": development_data.get("performance_rating")
        },
        
        "development_objectives": [
            {
                "area": area,
                "specific_goals": _generate_development_goals(area, reviews),
                "timeline": "6_months",
                "success_metrics": _define_success_metrics(area),
                "resources_needed": _identify_resources_needed(area)
            }
            for area in development_data.get("focus_areas", [])
        ],
        
        "learning_and_development": {
            "formal_training": _recommend_formal_training(reviews, user),
            "on_the_job_learning": _recommend_otj_learning(reviews, user),
            "mentoring_coaching": _recommend_mentoring(reviews, user),
            "stretch_assignments": _recommend_stretch_assignments(reviews, user)
        },
        
        "career_progression": {
            "next_role_readiness": _assess_next_role_readiness(reviews, user),
            "skill_gaps_for_advancement": _identify_advancement_gaps(reviews, user),
            "recommended_experiences": _recommend_career_experiences(reviews, user)
        },
        
        "support_structure": {
            "manager_support": development_data.get("manager_support", []),
            "hr_support": development_data.get("hr_support", []),
            "peer_support": development_data.get("peer_support", [])
        },
        
        "milestones_and_checkpoints": _create_development_milestones(development_data),
        "success_indicators": _define_development_success_indicators(development_data)
    }
    
    return {
        "message": "Development plan created successfully",
        "plan": development_plan
    }

@router.get("/performance-trends/{user_id}")
async def get_performance_trends(
    user_id: int,
    time_range: str = Query("2_years"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed performance trends analysis"""
    
    if user_id != current_user.user_id:
        permission_engine = get_permission_engine(db)
        if not permission_engine.check_permission(current_user, "performance:view:all"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Calculate time range
    if time_range == "1_year":
        start_date = datetime.utcnow() - timedelta(days=365)
    elif time_range == "2_years":
        start_date = datetime.utcnow() - timedelta(days=730)
    else:
        start_date = datetime.utcnow() - timedelta(days=1095)  # 3 years
    
    # Get historical reviews
    reviews = db.query(Review).filter(
        Review.reviewee_id == user_id,
        Review.created_at >= start_date,
        Review.status == "submitted"
    ).order_by(Review.created_at.asc()).all()
    
    trends_analysis = {
        "performance_trajectory": _calculate_performance_trajectory(reviews),
        "competency_progression": _track_competency_progression(reviews),
        "goal_achievement_trends": _analyze_goal_achievement_trends(user_id, start_date, db),
        "feedback_themes_evolution": _track_feedback_themes_evolution(reviews),
        "development_progress": _measure_development_progress(reviews),
        "consistency_patterns": _identify_consistency_patterns(reviews),
        "seasonal_performance": _analyze_seasonal_patterns(reviews),
        "predictive_insights": _generate_predictive_insights(reviews)
    }
    
    return trends_analysis

@router.get("/user-trait-scores/{user_id}")
async def get_user_trait_scores(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get trait scores for a specific user from their review scores"""
    from utils.trait_inheritance import TraitInheritanceService

    # Check permissions
    if user_id != current_user.user_id:
        if "performance_view_all" not in current_user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view other users' trait scores"
            )

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get applicable traits for this user
    trait_service = TraitInheritanceService(db)
    applicable_traits = trait_service.get_applicable_traits_for_user(user_id)

    # Get review scores for the user grouped by trait
    trait_scores = []

    for trait in applicable_traits:
        # Get all scores for this trait from review_scores table
        scores = db.query(ReviewScore).join(
            Review, ReviewScore.review_id == Review.id
        ).filter(
            Review.reviewee_id == user_id,
            ReviewScore.trait_id == trait.id,
            Review.status.in_(['submitted', 'approved'])
        ).all()

        if scores:
            # Calculate average score for this trait
            total_score = sum(score.score for score in scores)
            average_score = total_score / len(scores)

            # Get organization name if scoped trait
            organization_name = None
            if trait.organization_id:
                org = db.query(Organization).filter(Organization.id == trait.organization_id).first()
                organization_name = org.name if org else None

            trait_scores.append({
                "trait_id": str(trait.id),
                "name": trait.name,
                "description": trait.description,
                "scope_type": trait.scope_type.value if hasattr(trait.scope_type, 'value') else trait.scope_type,
                "organization_name": organization_name,
                "average_score": round(average_score, 2),
                "total_reviews": len(scores),
                "latest_score": scores[-1].score if scores else None
            })

    return trait_scores

# TODO: Advanced helper functions - These require more complex implementation
# These functions are stubs that return empty data and need proper implementation
# when the advanced features are fully developed

def _assess_core_competencies(reviews): 
    """TODO: Implement core competency assessment based on review data"""
    return {"message": "Core competency assessment not yet implemented"}

def _assess_technical_skills(reviews, user): 
    """TODO: Implement technical skills assessment"""
    return {"message": "Technical skills assessment not yet implemented"}

def _assess_leadership_competencies(reviews): 
    """TODO: Implement leadership competency assessment"""
    return {"message": "Leadership competency assessment not yet implemented"}

def _assess_behavioral_indicators(reviews): 
    """TODO: Implement behavioral indicators assessment"""
    return {"message": "Behavioral indicators assessment not yet implemented"}

def _identify_competency_gaps(reviews): 
    """TODO: Implement competency gap analysis"""
    return []

def _build_strengths_profile(reviews): 
    """TODO: Implement comprehensive strengths profile building"""
    return {"message": "Strengths profile building not yet implemented"}

def _create_development_roadmap(reviews, user): 
    """TODO: Implement personalized development roadmap creation"""
    return {"message": "Development roadmap creation not yet implemented"}

def _compare_to_benchmarks(reviews, user): 
    """TODO: Implement benchmark comparison"""
    return {"message": "Benchmark comparison not yet implemented"}

def _extract_strengths_from_reviews(reviews): 
    """TODO: Implement advanced strength extraction"""
    return []

def _extract_development_areas_from_reviews(reviews): 
    """TODO: Implement advanced development area extraction"""
    return []

def _generate_development_goals(area, reviews): 
    """TODO: Implement development goal generation"""
    return []

def _define_success_metrics(area): 
    """TODO: Implement success metrics definition"""
    return []

def _identify_resources_needed(area): 
    """TODO: Implement resource identification"""
    return []

def _recommend_formal_training(reviews, user): 
    """TODO: Implement formal training recommendations"""
    return []

def _recommend_otj_learning(reviews, user): 
    """TODO: Implement on-the-job learning recommendations"""
    return []

def _recommend_mentoring(reviews, user): 
    """TODO: Implement mentoring recommendations"""
    return []

def _recommend_stretch_assignments(reviews, user): 
    """TODO: Implement stretch assignment recommendations"""
    return []

def _assess_next_role_readiness(reviews, user): 
    """TODO: Implement next role readiness assessment"""
    return {"message": "Next role readiness assessment not yet implemented"}

def _identify_advancement_gaps(reviews, user): 
    """TODO: Implement advancement gap identification"""
    return []

def _recommend_career_experiences(reviews, user): 
    """TODO: Implement career experience recommendations"""
    return []

def _create_development_milestones(development_data): 
    """TODO: Implement development milestone creation"""
    return []

def _define_development_success_indicators(development_data): 
    """TODO: Implement development success indicator definition"""
    return []

def _calculate_performance_trajectory(reviews): 
    """TODO: Implement performance trajectory calculation"""
    return {"message": "Performance trajectory calculation not yet implemented"}

def _track_competency_progression(reviews): 
    """TODO: Implement competency progression tracking"""
    return {"message": "Competency progression tracking not yet implemented"}

def _analyze_goal_achievement_trends(user_id, start_date, db): 
    """TODO: Implement goal achievement trend analysis"""
    return {"message": "Goal achievement trend analysis not yet implemented"}

def _track_feedback_themes_evolution(reviews): 
    """TODO: Implement feedback theme evolution tracking"""
    return {"message": "Feedback theme evolution tracking not yet implemented"}

def _measure_development_progress(reviews): 
    """TODO: Implement development progress measurement"""
    return {"message": "Development progress measurement not yet implemented"}

def _identify_consistency_patterns(reviews): 
    """TODO: Implement consistency pattern identification"""
    return {"message": "Consistency pattern identification not yet implemented"}

def _analyze_seasonal_patterns(reviews): 
    """TODO: Implement seasonal pattern analysis"""
    return {"message": "Seasonal pattern analysis not yet implemented"}

def _generate_predictive_insights(reviews): 
    """TODO: Implement predictive insights generation"""
    return {"message": "Predictive insights generation not yet implemented"}

# Additional helper functions for new API endpoints

def _get_date_range_filter(date_range: str) -> datetime:
    """Get start date for filtering based on date range"""
    now = datetime.utcnow()

    if date_range == "current_year":
        # Use 2024 as the reference year for demo data
        return datetime(2024, 1, 1)
    elif date_range == "last_year":
        return datetime(2023, 1, 1)
    elif date_range == "last_6_months":
        return now - timedelta(days=180)
    elif date_range == "last_3_months":
        return now - timedelta(days=90)
    else:  # all_time
        return datetime(2000, 1, 1)  # Far in the past

def _get_employee_review_performance(user_id: int, date_filter: datetime, db: Session) -> dict:
    """Get review performance metrics for an employee"""

    # Get review scores directly from ReviewScore table
    review_scores = db.query(ReviewScore).join(
        ReviewCycle, ReviewScore.cycle_id == ReviewCycle.id
    ).filter(
        ReviewScore.user_id == user_id,
        ReviewCycle.start_date >= date_filter
    ).all()

    if not review_scores:
        return {
            'latest_review_score': None,
            'avg_review_score': None,
            'total_reviews': 0
        }

    # Calculate average score from all review scores
    all_scores = []
    for score in review_scores:
        # Use weighted_score if available, otherwise use self_score
        score_value = score.weighted_score or score.self_score
        if score_value:
            all_scores.append(score_value)

    if not all_scores:
        return {
            'latest_review_score': None,
            'avg_review_score': None,
            'total_reviews': 0
        }

    # Get the most recent cycle to determine latest score
    cycles_with_scores = {}
    for score in review_scores:
        cycle = db.query(ReviewCycle).filter(ReviewCycle.id == score.cycle_id).first()
        if cycle:
            if cycle.id not in cycles_with_scores:
                cycles_with_scores[cycle.id] = {
                    'start_date': cycle.start_date,
                    'scores': []
                }
            score_value = score.weighted_score or score.self_score
            if score_value:
                cycles_with_scores[cycle.id]['scores'].append(score_value)

    # Get latest cycle
    latest_cycle_id = None
    latest_date = None
    for cycle_id, data in cycles_with_scores.items():
        if latest_date is None or data['start_date'] > latest_date:
            latest_date = data['start_date']
            latest_cycle_id = cycle_id

    # Calculate latest score as average of all trait scores in the latest cycle
    latest_score = None
    if latest_cycle_id and cycles_with_scores[latest_cycle_id]['scores']:
        latest_score = sum(cycles_with_scores[latest_cycle_id]['scores']) / len(cycles_with_scores[latest_cycle_id]['scores'])

    # Count unique review cycles
    total_reviews = len(cycles_with_scores)

    return {
        'latest_review_score': round(latest_score, 2) if latest_score else None,
        'avg_review_score': round(sum(all_scores) / len(all_scores), 2),
        'total_reviews': total_reviews
    }

def _get_employee_task_performance(user_id: int, date_filter: datetime, db: Session) -> dict:
    """Get task performance metrics for an employee"""

    # Get tasks assigned to the employee via TaskAssignment
    from models import InitiativeAssignment
    task_assignments = db.query(InitiativeAssignment).filter(
        InitiativeAssignment.user_id == user_id
    ).all()

    if not task_assignments:
        return {
            'completion_rate': 0,
            'efficiency_score': 0,
            'leadership_count': 0,
            'active_tasks': 0,
            'extension_ratio': 0
        }

    # Get the actual tasks
    task_ids = [assignment.task_id for assignment in task_assignments]
    tasks = db.query(Initiative).filter(
        Initiative.id.in_(task_ids),
        Initiative.created_at >= date_filter
    ).all()

    if not tasks:
        return {
            'completion_rate': 0,
            'efficiency_score': 0,
            'leadership_count': 0,
            'active_tasks': 0,
            'extension_ratio': 0
        }

    # Calculate completion rate based on TaskStatus
    from models import InitiativeStatus
    approved_tasks = [t for t in tasks if t.status == InitiativeStatus.COMPLETED]
    completion_rate = (len(approved_tasks) / len(tasks)) * 100 if tasks else 0

    # Calculate efficiency based on task scores (if available)
    efficiency_scores = []
    for task in approved_tasks:
        if task.score:
            # Convert 1-10 score to percentage
            efficiency_scores.append((task.score / 10) * 100)

    avg_efficiency = sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 0

    # Count leadership roles (tasks where user is team head)
    leadership_count = len([t for t in tasks if t.team_head_id == user_id])

    # Count active tasks (pending, ongoing, or under review but not approved)
    active_tasks = len([t for t in tasks if t.status in [InitiativeStatus.PENDING, InitiativeStatus.ONGOING, InitiativeStatus.UNDER_REVIEW]])

    # Calculate extension requests ratio
    from models import InitiativeExtension
    extension_requests = db.query(InitiativeExtension).filter(
        InitiativeExtension.task_id.in_(task_ids),
        InitiativeExtension.requested_by == user_id
    ).count()
    extension_ratio = (extension_requests / len(tasks)) * 100 if tasks else 0

    return {
        'completion_rate': round(completion_rate, 1),
        'efficiency_score': round(avg_efficiency, 1),
        'leadership_count': leadership_count,
        'active_tasks': active_tasks,
        'extension_ratio': round(extension_ratio, 1)
    }

def _calculate_completion_percentage(responses: dict) -> float:
    """Calculate completion percentage based on responses"""
    if not responses:
        return 0.0
    
    total_questions = len(responses)
    answered_questions = len([v for v in responses.values() 
                             if v is not None and str(v).strip() != ''])
    
    return (answered_questions / total_questions) * 100 if total_questions > 0 else 0.0

def _get_questions_for_review_type(cycle: ReviewCycle, review_type: str) -> list:
    """Get questions for a specific review type from cycle configuration"""
    
    # Default question templates
    default_questions = {
        "self": [
            {
                "id": 1,
                "text": "What were your key achievements this period?",
                "type": "text",
                "required": True,
                "max_length": 1000
            },
            {
                "id": 2,
                "text": "Rate your overall performance this period",
                "type": "rating",
                "required": True,
                "scale_labels": ["Poor", "Below Average", "Average", "Good", "Excellent"]
            },
            {
                "id": 3,
                "text": "What areas would you like to develop?",
                "type": "text",
                "required": True,
                "max_length": 1000
            },
            {
                "id": 4,
                "text": "How well did you collaborate with your team?",
                "type": "rating",
                "required": True,
                "scale_labels": ["Poor", "Below Average", "Average", "Good", "Excellent"]
            },
            {
                "id": 5,
                "text": "Did you meet your goals this period?",
                "type": "yes_no",
                "required": True
            }
        ],
        "peer": [
            {
                "id": 1,
                "text": "How would you rate this colleague's collaboration?",
                "type": "rating",
                "required": True,
                "scale_labels": ["Poor", "Below Average", "Average", "Good", "Excellent"]
            },
            {
                "id": 2,
                "text": "What are this colleague's key strengths?",
                "type": "text",
                "required": True,
                "max_length": 500
            },
            {
                "id": 3,
                "text": "How effectively does this colleague communicate?",
                "type": "rating",
                "required": True,
                "scale_labels": ["Poor", "Below Average", "Average", "Good", "Excellent"]
            },
            {
                "id": 4,
                "text": "What could this colleague improve on?",
                "type": "text",
                "required": False,
                "max_length": 500
            },
            {
                "id": 5,
                "text": "Would you recommend this colleague for increased responsibilities?",
                "type": "yes_no",
                "required": True
            }
        ],
        "supervisor": [
            {
                "id": 1,
                "text": "Rate this employee's overall performance",
                "type": "rating",
                "required": True,
                "scale_labels": ["Poor", "Below Average", "Average", "Good", "Excellent"]
            },
            {
                "id": 2,
                "text": "How well did this employee meet their objectives?",
                "type": "rating",
                "required": True,
                "scale_labels": ["Poor", "Below Average", "Average", "Good", "Excellent"]
            },
            {
                "id": 3,
                "text": "What are this employee's key accomplishments?",
                "type": "text",
                "required": True,
                "max_length": 1000
            },
            {
                "id": 4,
                "text": "What development areas should this employee focus on?",
                "type": "text",
                "required": True,
                "max_length": 1000
            },
            {
                "id": 5,
                "text": "How would you rate this employee's leadership potential?",
                "type": "rating",
                "required": True,
                "scale_labels": ["Poor", "Below Average", "Average", "Good", "Excellent"]
            },
            {
                "id": 6,
                "text": "Is this employee ready for promotion?",
                "type": "yes_no",
                "required": True
            }
        ]
    }
    
    # Check if cycle has custom questions configured
    if cycle.components and cycle.components.get(f"{review_type}_review", {}).get("questions"):
        return cycle.components[f"{review_type}_review"]["questions"]
    
    # Return default questions for the review type
    return default_questions.get(review_type, default_questions["self"])

def _generate_comprehensive_cycle_analytics(cycle: ReviewCycle, reviews: List[Review], peer_reviews: List, db: Session) -> dict:
    """Generate comprehensive analytics for a review cycle"""
    
    # Basic cycle overview
    total_participants = len(set([r.reviewee_id for r in reviews]))
    total_reviews = len(reviews) + len(peer_reviews)
    completed_reviews = len([r for r in reviews if r.status in ['completed', 'submitted']]) + \
                       len([r for r in peer_reviews if r.status in ['completed', 'submitted']])
    
    completion_rate = (completed_reviews / total_reviews * 100) if total_reviews > 0 else 0
    
    # Participation analysis
    participation_by_type = {
        "self_reviews": len([r for r in reviews if r.type == 'self']),
        "supervisor_reviews": len([r for r in reviews if r.type == 'supervisor']),
        "peer_reviews": len(peer_reviews)
    }
    
    # Performance insights
    all_ratings = []
    for review in reviews:
        if review.responses:
            ratings = [v for v in review.responses.values() 
                      if isinstance(v, (int, float)) and 1 <= v <= 5]
            all_ratings.extend(ratings)
    
    for peer_review in peer_reviews:
        if peer_review.responses:
            ratings = [v for v in peer_review.responses.values() 
                      if isinstance(v, (int, float)) and 1 <= v <= 5]
            all_ratings.extend(ratings)
    
    avg_rating = sum(all_ratings) / len(all_ratings) if all_ratings else 0
    
    # Quality metrics
    avg_response_length = _calculate_avg_response_length(reviews + peer_reviews)
    thoughtfulness_score = _calculate_thoughtfulness_score(reviews)
    
    # Bias analysis
    bias_analysis = {
        "overall_bias_score": _calculate_overall_bias_score(reviews, peer_reviews),
        "leniency_bias": _detect_leniency_bias(reviews),
        "halo_effect": _detect_halo_effect(reviews),
        "recency_bias": _detect_recency_bias(reviews)
    }
    
    return {
        "cycle_overview": {
            "cycle_id": cycle.id,
            "cycle_name": cycle.name,
            "total_participants": total_participants,
            "total_reviews": total_reviews,
            "completed_reviews": completed_reviews,
            "completion_rate": round(completion_rate, 1),
            "average_rating": round(avg_rating, 2)
        },
        "participation_analysis": {
            "participation_by_type": participation_by_type,
            "engagement_level": "high" if completion_rate > 80 else ("medium" if completion_rate > 60 else "low")
        },
        "performance_insights": {
            "average_score": round(avg_rating, 2),
            "high_performers": len([r for r in all_ratings if r >= 4]),
            "needs_improvement": len([r for r in all_ratings if r <= 2]),
            "rating_distribution": _calculate_rating_distribution(all_ratings)
        },
        "quality_metrics": {
            "avg_response_length": avg_response_length,
            "thoughtfulness_score": thoughtfulness_score,
            "completion_timeline": _analyze_completion_timeline(reviews, peer_reviews)
        },
        "bias_analysis": bias_analysis,
        "recommendations": _generate_cycle_recommendations(cycle, reviews, peer_reviews)
    }

def _calculate_rating_distribution(ratings: List[float]) -> dict:
    """Calculate distribution of ratings"""
    if not ratings:
        return {}
    
    from collections import Counter
    distribution = Counter(ratings)
    
    return {
        "1_star": distribution.get(1, 0),
        "2_star": distribution.get(2, 0),
        "3_star": distribution.get(3, 0),
        "4_star": distribution.get(4, 0),
        "5_star": distribution.get(5, 0)
    }

# Trait Management Endpoints

class TraitCreate(BaseModel):
    name: str
    description: Optional[str] = None
    display_order: Optional[int] = None
    scope_type: str = "global"  # global, directorate, department, unit
    organization_id: Optional[str] = None  # Required for scoped traits
    applicable_levels: Optional[List[int]] = None  # None = all levels; e.g. [12, 13]

class TraitResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_active: bool
    display_order: Optional[int]
    scope_type: str
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    applicable_levels: Optional[List[int]] = None
    created_at: datetime
    question_count: int = 0

    class Config:
        from_attributes = True

class QuestionCreate(BaseModel):
    question_text: str
    applies_to_self: bool = True
    applies_to_peer: bool = True
    applies_to_supervisor: bool = True

class QuestionResponse(BaseModel):
    id: str
    question_text: str
    applies_to_self: bool
    applies_to_peer: bool
    applies_to_supervisor: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Enhanced Review Cycle Create with Traits
class EnhancedReviewCycleCreate(BaseModel):
    name: str
    type: str
    period: str
    start_date: datetime
    end_date: datetime
    buffer_time: str = '1_week'
    peer_review_count: int = 5
    auto_assign_peers: bool = True
    components: dict = {}

class ReviewAssignmentResponse(BaseModel):
    id: str
    cycle_id: str
    cycle_name: str
    reviewee_name: str
    reviewee_id: str
    review_type: str
    status: str
    completed_at: Optional[datetime]
    questions: List[QuestionResponse] = []

    class Config:
        from_attributes = True

# Trait Management Routes

@router.get("/traits", response_model=List[TraitResponse])
async def get_traits(
    all_traits: bool = None,  # Admin can see all traits
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get review traits with question counts
    By default, admins see all traits, regular users see only applicable traits
    Set all_traits=true/false to override default behavior
    """
    from sqlalchemy.orm import joinedload
    from utils.trait_inheritance import TraitInheritanceService

    trait_service = TraitInheritanceService(db)

    # Check if user has admin permission to view all traits
    has_admin_permission = ("review_trait_manage" in current_user.permissions or
                           "review_manage_cycle" in current_user.permissions or
                           "system_admin" in current_user.permissions)

    if all_traits is None:
         
        show_all = has_admin_permission
    else:
        # Explicit override
        show_all = all_traits
        if show_all and not has_admin_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view all traits"
            )

    if show_all:
        # Admin view - all traits
        traits = db.query(ReviewTrait).options(
            joinedload(ReviewTrait.organization)
        ).filter(ReviewTrait.is_active == True).order_by(ReviewTrait.display_order).all()
    else:
        # User view - only applicable traits
        traits = trait_service.get_applicable_traits_for_user(current_user.user_id)

    result = []
    for trait in traits:
        question_count = db.query(ReviewQuestion).filter(
            ReviewQuestion.trait_id == trait.id,
            ReviewQuestion.is_active == True
        ).count()

        # Load organization if not already loaded
        organization_name = None
        if trait.organization_id:
            if hasattr(trait, 'organization') and trait.organization:
                organization_name = trait.organization.name
            else:
                org = db.query(Organization).filter(Organization.id == trait.organization_id).first()
                organization_name = org.name if org else None

        trait_dict = {
            "id": str(trait.id),
            "name": trait.name,
            "description": trait.description,
            "is_active": trait.is_active,
            "display_order": trait.display_order,
            "scope_type": trait.scope_type.value if trait.scope_type else "global",
            "organization_id": str(trait.organization_id) if trait.organization_id else None,
            "organization_name": organization_name,
            "applicable_levels": trait.applicable_levels,
            "created_at": trait.created_at,
            "question_count": question_count
        }
        result.append(TraitResponse(**trait_dict))

    return result

@router.post("/traits", response_model=TraitResponse)
async def create_trait(
    trait_data: TraitCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new performance trait with organizational scope
    Global traits apply to everyone, scoped traits apply to specific organizational units and their children
    """
    from models import TraitScopeType
    user_permissions = UserPermissions(db)

    if "review_trait_manage" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create traits"
        )

    # Normalize scope_type to lowercase
    trait_data.scope_type = trait_data.scope_type.lower()

    # Validate scope and organization_id relationship
    if trait_data.scope_type != "global" and not trait_data.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="organization_id is required for scoped traits"
        )

    if trait_data.scope_type == "global" and trait_data.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Global traits cannot have an organization_id"
        )

    # Validate organization exists if provided
    if trait_data.organization_id:
        organization = db.query(Organization).filter(Organization.id == trait_data.organization_id).first()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )

    # Check if trait name already exists within the same scope
    existing_query = db.query(ReviewTrait).filter(
        ReviewTrait.name == trait_data.name,
        ReviewTrait.scope_type == trait_data.scope_type
    )
    if trait_data.organization_id:
        existing_query = existing_query.filter(ReviewTrait.organization_id == trait_data.organization_id)
    else:
        existing_query = existing_query.filter(ReviewTrait.organization_id.is_(None))

    existing_trait = existing_query.first()
    if existing_trait:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trait with this name already exists in this scope"
        )

    # Set display order if not provided
    if trait_data.display_order is None:
        max_order = db.query(func.max(ReviewTrait.display_order)).scalar() or 0
        trait_data.display_order = max_order + 1

    trait = ReviewTrait(
        name=trait_data.name,
        description=trait_data.description,
        display_order=trait_data.display_order,
        scope_type=trait_data.scope_type,
        organization_id=trait_data.organization_id if trait_data.organization_id else None,
        applicable_levels=trait_data.applicable_levels if trait_data.applicable_levels else None,
        created_by=current_user.user_id
    )

    db.add(trait)
    db.commit()
    db.refresh(trait)

    # Load organization if present
    organization_name = None
    if trait.organization_id:
        org = db.query(Organization).filter(Organization.id == trait.organization_id).first()
        organization_name = org.name if org else None

    return TraitResponse(
        id=str(trait.id),
        name=trait.name,
        description=trait.description,
        is_active=trait.is_active,
        display_order=trait.display_order,
        scope_type=trait.scope_type.value,
        organization_id=str(trait.organization_id) if trait.organization_id else None,
        organization_name=organization_name,
        applicable_levels=trait.applicable_levels,
        created_at=trait.created_at,
        question_count=0
    )

class TraitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    applicable_levels: Optional[List[int]] = None  # None keeps existing; pass [] to clear (= all levels)
    clear_levels: bool = False  # Explicit flag to reset applicable_levels to null (all levels)

@router.put("/traits/{trait_id}", response_model=TraitResponse)
async def update_trait(
    trait_id: str,
    trait_data: TraitUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a performance trait's name, description, and/or applicable grade levels.
    Scope type and organization cannot be changed after creation.
    """
    if "review_trait_manage" not in current_user.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to edit traits")

    trait = db.query(ReviewTrait).filter(ReviewTrait.id == trait_id).first()
    if not trait:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trait not found")

    if trait_data.name is not None:
        # Check uniqueness within same scope
        existing = db.query(ReviewTrait).filter(
            ReviewTrait.name == trait_data.name,
            ReviewTrait.scope_type == trait.scope_type,
            ReviewTrait.organization_id == trait.organization_id,
            ReviewTrait.id != trait.id
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trait with this name already exists in this scope")
        trait.name = trait_data.name

    if trait_data.description is not None:
        trait.description = trait_data.description

    if trait_data.clear_levels:
        trait.applicable_levels = None
    elif trait_data.applicable_levels is not None:
        trait.applicable_levels = sorted(trait_data.applicable_levels) if trait_data.applicable_levels else None

    db.commit()
    db.refresh(trait)

    organization_name = None
    if trait.organization_id:
        org = db.query(Organization).filter(Organization.id == trait.organization_id).first()
        organization_name = org.name if org else None

    question_count = db.query(ReviewQuestion).filter(ReviewQuestion.trait_id == trait.id, ReviewQuestion.is_active == True).count()

    return TraitResponse(
        id=str(trait.id),
        name=trait.name,
        description=trait.description,
        is_active=trait.is_active,
        display_order=trait.display_order,
        scope_type=trait.scope_type.value,
        organization_id=str(trait.organization_id) if trait.organization_id else None,
        organization_name=organization_name,
        applicable_levels=trait.applicable_levels,
        created_at=trait.created_at,
        question_count=question_count
    )

@router.delete("/traits/{trait_id}")
async def delete_trait(
    trait_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a performance trait
    Only allows deletion if the trait is not used in any active review cycles
    """
    user_permissions = UserPermissions(db)

    if "review_trait_manage" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete traits"
        )

    # Get the trait
    trait = db.query(ReviewTrait).filter(ReviewTrait.id == trait_id).first()
    if not trait:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trait not found"
        )

    # Check if trait is used in any active review cycles
    active_cycle_count = db.query(ReviewCycleTrait).join(ReviewCycle).filter(
        ReviewCycleTrait.trait_id == trait_id,
        ReviewCycle.status.in_(['draft', 'active'])
    ).count()

    if active_cycle_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete trait. It is currently used in {active_cycle_count} active review cycle(s). Please complete or cancel those cycles first."
        )

    # Delete associated questions first
    db.query(ReviewQuestion).filter(ReviewQuestion.trait_id == trait_id).delete()

    # Delete the trait
    db.delete(trait)
    db.commit()

    return {"message": "Trait deleted successfully"}

@router.get("/traits/{trait_id}/questions", response_model=List[QuestionResponse])
async def get_trait_questions(
    trait_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all questions for a specific trait"""
    questions = db.query(ReviewQuestion).filter(
        ReviewQuestion.trait_id == trait_id,
        ReviewQuestion.is_active == True
    ).all()

    return [QuestionResponse(
        id=str(q.id),
        question_text=q.question_text,
        applies_to_self=q.applies_to_self,
        applies_to_peer=q.applies_to_peer,
        applies_to_supervisor=q.applies_to_supervisor,
        is_active=q.is_active,
        created_at=q.created_at
    ) for q in questions]

@router.post("/traits/{trait_id}/questions", response_model=QuestionResponse)
async def create_question(
    trait_id: str,
    question_data: QuestionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a question to a trait"""
    user_permissions = UserPermissions(db)

    if "review_trait_manage" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create questions"
        )

    # Verify trait exists
    trait = db.query(ReviewTrait).filter(ReviewTrait.id == trait_id).first()
    if not trait:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trait not found"
        )

    question = ReviewQuestion(
        trait_id=trait_id,
        question_text=question_data.question_text,
        applies_to_self=question_data.applies_to_self,
        applies_to_peer=question_data.applies_to_peer,
        applies_to_supervisor=question_data.applies_to_supervisor,
        created_by=current_user.user_id
    )

    db.add(question)
    db.commit()
    db.refresh(question)

    return QuestionResponse(
        id=str(question.id),
        question_text=question.question_text,
        applies_to_self=question.applies_to_self,
        applies_to_peer=question.applies_to_peer,
        applies_to_supervisor=question.applies_to_supervisor,
        is_active=question.is_active,
        created_at=question.created_at
    )

@router.delete("/questions/{question_id}")
async def delete_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a question"""
    user_permissions = UserPermissions(db)

    if "review_trait_manage" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete questions"
        )

    question = db.query(ReviewQuestion).filter(ReviewQuestion.id == question_id).first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    # Check if question is used in any active reviews
    active_responses = db.query(ReviewResponseModel).filter(ReviewResponseModel.question_id == question_id).first()
    if active_responses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete question that has been used in reviews"
        )

    db.delete(question)
    db.commit()

    return {"message": "Question deleted successfully"}


@router.get("/cycles/{cycle_id}/questions")
async def get_cycle_questions(
    cycle_id: str,
    review_type: Optional[str] = Query(None, description="Filter by review type: self, peer, supervisor"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all questions configured for a cycle, grouped by trait"""
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Review cycle not found")

    # Get all traits linked to this cycle
    cycle_traits = db.query(ReviewCycleTrait).filter(
        ReviewCycleTrait.cycle_id == cycle_id,
        ReviewCycleTrait.is_active == True
    ).join(ReviewTrait).all()

    result = []
    for ct in cycle_traits:
        trait = ct.trait

        # Get all questions for this trait
        questions_query = db.query(ReviewQuestion).filter(
            ReviewQuestion.trait_id == trait.id,
            ReviewQuestion.is_active == True
        )

        # Filter by review type if specified
        if review_type:
            if review_type == 'self':
                questions_query = questions_query.filter(ReviewQuestion.applies_to_self == True)
            elif review_type == 'peer':
                questions_query = questions_query.filter(ReviewQuestion.applies_to_peer == True)
            elif review_type == 'supervisor':
                questions_query = questions_query.filter(ReviewQuestion.applies_to_supervisor == True)

        questions = questions_query.all()

        result.append({
            "trait_id": str(trait.id),
            "trait_name": trait.name,
            "trait_description": trait.description,
            "questions": [{
                "id": str(q.id),
                "question_text": q.question_text,
                "applies_to_self": q.applies_to_self,
                "applies_to_peer": q.applies_to_peer,
                "applies_to_supervisor": q.applies_to_supervisor
            } for q in questions]
        })

    return result

@router.post("/cycles/{cycle_id}/questions")
async def add_question_to_cycle(
    cycle_id: str,
    question_data: dict,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a new question to a draft cycle"""
    if "review_create_cycle" not in current_user.permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Review cycle not found")

    if cycle.status != "DRAFT":
        raise HTTPException(status_code=400, detail="Can only modify questions in draft cycles")

    # Create the question (with or without trait)
    question = ReviewQuestion(
        trait_id=question_data.get("trait_id"),  # Optional
        question_text=question_data["question_text"],
        applies_to_self=question_data.get("applies_to_self", True),
        applies_to_peer=question_data.get("applies_to_peer", True),
        applies_to_supervisor=question_data.get("applies_to_supervisor", True),
        is_active=True
    )

    db.add(question)
    db.commit()
    db.refresh(question)

    return {"id": str(question.id), "message": "Question added successfully"}

@router.delete("/cycles/{cycle_id}/questions/{question_id}")
async def remove_question_from_cycle(
    cycle_id: str,
    question_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a question from a draft cycle"""
    if "review_create_cycle" not in current_user.permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Review cycle not found")

    if cycle.status != "DRAFT":
        raise HTTPException(status_code=400, detail="Can only modify questions in draft cycles")

    question = db.query(ReviewQuestion).filter(ReviewQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Soft delete
    question.is_active = False
    db.commit()

    return {"message": "Question removed successfully"}

@router.post("/cycles/{cycle_id}/activate")
async def activate_review_cycle(
    cycle_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Schedule a review cycle from draft status and generate assignments.
    The cycle will become active on the start_date and close on the end_date.
    """
    if "review_create_cycle" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to activate review cycles"
        )

    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review cycle not found"
        )

    if cycle.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review cycle is not in draft status"
        )

    # Generate all review assignments
    _generate_review_assignments(cycle_id, db)

    # Update cycle status to scheduled
    # The cycle will automatically become active on the start_date
    cycle.status = "SCHEDULED"

    # Update participant count
    participant_count = db.query(func.count(func.distinct(ReviewAssignment.reviewee_id))).filter(
        ReviewAssignment.cycle_id == cycle_id
    ).scalar()
    cycle.participants_count = participant_count

    db.commit()
    db.refresh(cycle)

    return {
        "message": f"Review cycle scheduled successfully. It will become active on {cycle.start_date.strftime('%Y-%m-%d')} and close on {cycle.end_date.strftime('%Y-%m-%d')}",
        "cycle_id": cycle_id,
        "status": cycle.status,
        "start_date": cycle.start_date.isoformat(),
        "end_date": cycle.end_date.isoformat(),
        "participants_count": cycle.participants_count,
        "assignments_generated": True
    }

def _generate_review_assignments(cycle_id: str, db: Session):
    """Generate review assignments for a cycle"""
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not cycle:
        return

    # Delete any existing assignments for this cycle (to handle re-activation scenarios)
    db.query(ReviewAssignment).filter(ReviewAssignment.cycle_id == cycle_id).delete()
    db.flush()  # Ensure deletions are processed before creating new assignments

    # Get all active users
    active_users = db.query(User).filter(User.status == 'ACTIVE').all()

    for user in active_users:
        # Create self-review assignment
        self_assignment = ReviewAssignment(
            cycle_id=cycle_id,
            reviewer_id=user.id,
            reviewee_id=user.id,
            review_type='self'
        )
        db.add(self_assignment)

        # Create supervisor review assignment
        # Use the actual supervisor_id field from the user model
        if user.supervisor_id:
            supervisor = db.query(User).filter(
                User.id == user.supervisor_id,
                User.status == 'ACTIVE'
            ).first()

            if supervisor:
                supervisor_assignment = ReviewAssignment(
                    cycle_id=cycle_id,
                    reviewer_id=supervisor.id,
                    reviewee_id=user.id,
                    review_type='supervisor'
                )
                db.add(supervisor_assignment)

        # Create peer reviews (always included in new system)
        peer_count = cycle.components.get('peer_count', 5)

        # Get users from same department, excluding:
        # 1. The user themselves
        # 2. Their supervisor (already reviewing in supervisor section)
        # 3. Anyone they supervise (avoid dual review burden)
        excluded_ids = [user.id]
        if user.supervisor_id:
            excluded_ids.append(user.supervisor_id)

        # Get all subordinates
        subordinate_ids = db.query(User.id).filter(
            User.supervisor_id == user.id,
            User.status == 'ACTIVE'
        ).all()
        excluded_ids.extend([sub_id[0] for sub_id in subordinate_ids])

        # Get eligible peers from same department
        dept_users = db.query(User).filter(
            User.organization_id == user.organization_id,
            User.status == 'ACTIVE',
            User.id.notin_(excluded_ids)
        ).order_by(func.random()).limit(peer_count).all()

        for peer in dept_users:
            peer_assignment = ReviewAssignment(
                cycle_id=cycle_id,
                reviewer_id=peer.id,
                reviewee_id=user.id,
                review_type='peer'
            )
            db.add(peer_assignment)

    db.commit()

# User Review Assignment Endpoints

@router.get("/assignments/me")
async def get_my_review_assignments(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all review assignments for the current user"""
    # Get assignments for current user
    assignments = db.query(ReviewAssignment).filter(
        ReviewAssignment.reviewer_id == current_user.user_id
    ).all()

    if not assignments:
        return []

    result = []
    for assignment in assignments:
        try:
            # Get cycle
            cycle = db.query(ReviewCycle).filter(
                ReviewCycle.id == assignment.cycle_id
            ).first()

            if not cycle:
                continue

            # Get reviewee
            reviewee = db.query(User).filter(
                User.id == assignment.reviewee_id
            ).first()

            if not reviewee:
                continue

            # Build reviewee name
            name_parts = [reviewee.first_name]
            if reviewee.middle_name:
                name_parts.append(reviewee.middle_name)
            name_parts.append(reviewee.last_name)
            reviewee_name = " ".join(name_parts)

            # Simple response with empty questions array for now
            result.append({
                "id": str(assignment.id),
                "cycle_id": str(cycle.id),
                "cycle_name": cycle.name,
                "reviewee_id": str(reviewee.id),
                "reviewee_name": reviewee_name,
                "review_type": assignment.review_type,
                "status": assignment.status,
                "completed_at": assignment.completed_at.isoformat() if assignment.completed_at else None,
                "questions": []  # Empty for now to prevent frontend errors
            })
        except Exception as e:
            print(f"Error processing assignment: {e}")
            continue

    return result

@router.get("/assignments/{assignment_id}/form")
async def get_review_assignment_form(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get review assignment form with questions and current responses"""

    # Get the assignment
    assignment = db.query(ReviewAssignment).filter(ReviewAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Check access permissions
    if assignment.reviewer_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get reviewee details
    reviewee = db.query(User).filter(User.id == assignment.reviewee_id).first()
    if not reviewee:
        raise HTTPException(status_code=404, detail="Reviewee not found")

    # Get cycle details
    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == assignment.cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Review cycle not found")

    # Get traits applicable to the reviewee (org hierarchy + grade level filtering)
    from utils.trait_inheritance import TraitInheritanceService
    trait_service = TraitInheritanceService(db)
    reviewee_applicable = trait_service.get_applicable_traits_for_user(assignment.reviewee_id or assignment.reviewer_id)
    reviewee_applicable_ids = {t.id for t in reviewee_applicable}

    # Get traits assigned to this cycle, intersected with reviewee-applicable traits
    cycle_traits = db.query(ReviewCycleTrait).filter(
        ReviewCycleTrait.cycle_id == assignment.cycle_id,
        ReviewCycleTrait.is_active == True,
        ReviewCycleTrait.trait_id.in_(reviewee_applicable_ids)
    ).all()

    form_data = {
        "assignment_id": assignment_id,
        "review_type": assignment.review_type,
        "reviewee": {
            "id": str(reviewee.id),
            "name": f"{reviewee.first_name} {reviewee.last_name}",
            "job_title": reviewee.job_title,
            "department": reviewee.organization.name if reviewee.organization else None
        },
        "cycle": {
            "id": str(cycle.id),
            "name": cycle.name,
            "period": cycle.period
        },
        "status": assignment.status,
        "completed_at": assignment.completed_at,
        "traits": []
    }

    # Get existing responses
    existing_responses = db.query(ReviewResponseModel).filter(
        ReviewResponse.assignment_id == assignment_id
    ).all()

    response_map = {str(resp.question_id): resp for resp in existing_responses}

    # Build trait questions structure
    for cycle_trait in cycle_traits:
        trait = db.query(ReviewTrait).filter(ReviewTrait.id == cycle_trait.trait_id).first()
        if not trait:
            continue

        # Get questions for this trait that apply to the review type
        questions_query = db.query(ReviewQuestion).filter(
            ReviewQuestion.trait_id == trait.id,
            ReviewQuestion.is_active == True
        )

        # Filter based on review type
        if assignment.review_type == 'self':
            questions_query = questions_query.filter(ReviewQuestion.applies_to_self == True)
        elif assignment.review_type == 'peer':
            questions_query = questions_query.filter(ReviewQuestion.applies_to_peer == True)
        elif assignment.review_type == 'supervisor':
            questions_query = questions_query.filter(ReviewQuestion.applies_to_supervisor == True)

        questions = questions_query.all()

        trait_data = {
            "id": str(trait.id),
            "name": trait.name,
            "description": trait.description,
            "questions": []
        }

        for question in questions:
            question_id = str(question.id)
            existing_response = response_map.get(question_id)

            question_data = {
                "id": question_id,
                "text": question.question_text,
                "rating": existing_response.rating if existing_response else None,
                "comment": existing_response.comment if existing_response else None
            }
            trait_data["questions"].append(question_data)

        if trait_data["questions"]:  # Only include traits that have questions
            form_data["traits"].append(trait_data)

    return form_data

@router.post("/assignments/{assignment_id}/submit")
async def submit_review_assignment(
    assignment_id: str,
    responses: dict,  # {"responses": [{"question_id": "uuid", "rating": 8, "comment": "text"}]}
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit responses for a review assignment"""

    # Get the assignment
    assignment = db.query(ReviewAssignment).filter(ReviewAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Check access permissions
    if assignment.reviewer_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if assignment.status == 'completed':
        raise HTTPException(status_code=400, detail="Assignment already completed")

    # Validate and save responses
    response_list = responses.get('responses', [])

    for response_data in response_list:
        question_id = response_data.get('question_id')
        rating = response_data.get('rating')
        comment = response_data.get('comment', '')

        if not question_id or rating is None:
            continue

        # Validate rating is in range 1-10
        if not (1 <= rating <= 10):
            raise HTTPException(status_code=400, detail=f"Rating must be between 1 and 10, got {rating}")

        # Check if response already exists
        existing_response = db.query(ReviewResponseModel).filter(
            ReviewResponseModel.assignment_id == assignment_id,
            ReviewResponseModel.question_id == question_id
        ).first()

        if existing_response:
            # Update existing response
            existing_response.rating = rating
            existing_response.comment = comment
            existing_response.updated_at = func.now()
        else:
            # Create new response
            new_response = ReviewResponseModel(
                assignment_id=assignment_id,
                question_id=question_id,
                rating=rating,
                comment=comment
            )
            db.add(new_response)

    # Check if this is final submission or just saving progress
    is_draft = responses.get('is_draft', False)

    if not is_draft:
        # Mark assignment as completed
        assignment.status = 'completed'
        assignment.completed_at = func.now()

    db.commit()

    # After marking as completed, check if all reviews for this reviewee in this cycle are done
    # If so, calculate scores
    if not is_draft:
        _calculate_scores_if_ready(assignment.cycle_id, assignment.reviewee_id, db)

        # Update cycle completion_rate
        try:
            total = db.query(ReviewAssignment).filter(
                ReviewAssignment.cycle_id == assignment.cycle_id
            ).count()
            completed = db.query(ReviewAssignment).filter(
                ReviewAssignment.cycle_id == assignment.cycle_id,
                ReviewAssignment.status == 'completed'
            ).count()
            cycle = db.query(ReviewCycle).filter(ReviewCycle.id == assignment.cycle_id).first()
            if cycle and total > 0:
                cycle.completion_rate = round(completed / total * 100, 1)
                db.commit()
        except Exception as e:
            print(f"Error updating completion rate: {e}")

    return {
        "message": "Progress saved successfully" if is_draft else "Review submitted successfully",
        "assignment_id": assignment_id,
        "status": assignment.status,
        "completed_at": assignment.completed_at
    }

def _calculate_scores_if_ready(cycle_id: str, user_id: str, db: Session):
    """Check if all reviews are completed for a user and calculate scores if ready"""

    # Check if all assignments for this user in this cycle are completed
    total_assignments = db.query(ReviewAssignment).filter(
        ReviewAssignment.cycle_id == cycle_id,
        ReviewAssignment.reviewee_id == user_id
    ).count()

    completed_assignments = db.query(ReviewAssignment).filter(
        ReviewAssignment.cycle_id == cycle_id,
        ReviewAssignment.reviewee_id == user_id,
        ReviewAssignment.status == 'completed'
    ).count()

    if total_assignments == completed_assignments and total_assignments > 0:
        # All reviews completed, calculate scores
        _calculate_user_review_scores(cycle_id, user_id, db)

def _calculate_user_review_scores(cycle_id: str, user_id: str, db: Session):
    """Calculate weighted scores for a user based on all their reviews in a cycle"""

    # Get all traits for this cycle
    cycle_traits = db.query(ReviewCycleTrait).filter(
        ReviewCycleTrait.cycle_id == cycle_id,
        ReviewCycleTrait.is_active == True
    ).all()

    for cycle_trait in cycle_traits:
        trait_id = cycle_trait.trait_id

        # Calculate scores for each review type
        self_score = _calculate_trait_score_by_type(cycle_id, user_id, trait_id, 'self', db)
        peer_score = None
        supervisor_score = _calculate_trait_score_by_type(cycle_id, user_id, trait_id, 'supervisor', db)

        # Calculate weighted score: self (28.6%) + supervisor (71.4%) — normalised from 0.2 + 0.5
        weighted_score = None
        if self_score is not None or supervisor_score is not None:
            total_weight = 0
            weighted_total = 0

            if self_score is not None:
                weighted_total += self_score * 0.2
                total_weight += 0.2

            if supervisor_score is not None:
                weighted_total += supervisor_score * 0.5
                total_weight += 0.5

            if total_weight > 0:
                weighted_score = weighted_total / total_weight * 10  # Normalize to 10-point scale

        # Save or update the score
        existing_score = db.query(ReviewScore).filter(
            ReviewScore.cycle_id == cycle_id,
            ReviewScore.user_id == user_id,
            ReviewScore.trait_id == trait_id
        ).first()

        if existing_score:
            existing_score.self_score = self_score
            existing_score.peer_score = peer_score
            existing_score.supervisor_score = supervisor_score
            existing_score.weighted_score = weighted_score
            existing_score.calculated_at = func.now()
        else:
            new_score = ReviewScore(
                cycle_id=cycle_id,
                user_id=user_id,
                trait_id=trait_id,
                self_score=self_score,
                peer_score=peer_score,
                supervisor_score=supervisor_score,
                weighted_score=weighted_score
            )
            db.add(new_score)

    db.commit()

def _calculate_trait_score_by_type(cycle_id: str, user_id: str, trait_id: str, review_type: str, db: Session) -> float:
    """Calculate average score for a trait from specific review type"""

    # Get all assignments of this type for this user
    assignments = db.query(ReviewAssignment).filter(
        ReviewAssignment.cycle_id == cycle_id,
        ReviewAssignment.reviewee_id == user_id,
        ReviewAssignment.review_type == review_type,
        ReviewAssignment.status == 'completed'
    ).all()

    if not assignments:
        return None

    # Get all questions for this trait
    trait_questions = db.query(ReviewQuestion).filter(
        ReviewQuestion.trait_id == trait_id,
        ReviewQuestion.is_active == True
    )

    # Filter based on review type
    if review_type == 'self':
        trait_questions = trait_questions.filter(ReviewQuestion.applies_to_self == True)
    elif review_type == 'peer':
        trait_questions = trait_questions.filter(ReviewQuestion.applies_to_peer == True)
    elif review_type == 'supervisor':
        trait_questions = trait_questions.filter(ReviewQuestion.applies_to_supervisor == True)

    question_ids = [str(q.id) for q in trait_questions.all()]

    if not question_ids:
        return None

    # Get all responses for these questions from these assignments
    all_ratings = []
    for assignment in assignments:
        responses = db.query(ReviewResponseModel).filter(
            ReviewResponse.assignment_id == assignment.id,
            ReviewResponse.question_id.in_(question_ids)
        ).all()

        for response in responses:
            all_ratings.append(response.rating)

    if not all_ratings:
        return None

    # Return average score
    return sum(all_ratings) / len(all_ratings)

@router.post("/cycles/{cycle_id}/calculate-scores")
async def calculate_cycle_scores(
    cycle_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually trigger score calculation for all users in a cycle"""
    user_permissions = UserPermissions(db)

    if "review_create_cycle" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to calculate scores"
        )

    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review cycle not found"
        )

    # Get all users who have assignments in this cycle
    user_ids = db.query(func.distinct(ReviewAssignment.reviewee_id)).filter(
        ReviewAssignment.cycle_id == cycle_id
    ).all()

    calculated_count = 0
    for (user_id,) in user_ids:
        _calculate_user_review_scores(cycle_id, user_id, db)
        calculated_count += 1

    return {
        "message": f"Scores calculated for {calculated_count} users",
        "cycle_id": cycle_id,
        "users_processed": calculated_count
    }

# Dashboard and Analytics Endpoints

@router.get("/cycles/{cycle_id}/dashboard")
async def get_cycle_dashboard(
    cycle_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive dashboard data for a review cycle"""
    user_permissions = UserPermissions(db)

    if "review_view_all" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view cycle dashboard"
        )

    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review cycle not found"
        )

    # Get participation statistics
    total_participants = db.query(func.count(func.distinct(ReviewAssignment.reviewee_id))).filter(
        ReviewAssignment.cycle_id == cycle_id
    ).scalar() or 0

    completed_participants = db.query(func.count(func.distinct(ReviewAssignment.reviewee_id))).filter(
        ReviewAssignment.cycle_id == cycle_id,
        ReviewAssignment.reviewee_id.in_(
            db.query(ReviewAssignment.reviewee_id).filter(
                ReviewAssignment.cycle_id == cycle_id
            ).group_by(ReviewAssignment.reviewee_id).having(
                func.count(ReviewAssignment.id) == func.count(
                    func.case([(ReviewAssignment.status == 'completed', 1)])
                )
            )
        )
    ).scalar() or 0

    # Get assignment statistics by type
    assignment_stats = {}
    for review_type in ['self', 'peer', 'supervisor']:
        total = db.query(ReviewAssignment).filter(
            ReviewAssignment.cycle_id == cycle_id,
            ReviewAssignment.review_type == review_type
        ).count()

        completed = db.query(ReviewAssignment).filter(
            ReviewAssignment.cycle_id == cycle_id,
            ReviewAssignment.review_type == review_type,
            ReviewAssignment.status == 'completed'
        ).count()

        assignment_stats[review_type] = {
            "total": total,
            "completed": completed,
            "completion_rate": (completed / total * 100) if total > 0 else 0
        }

    # Get department breakdown
    dept_stats = db.query(
        Organization.name,
        func.count(func.distinct(ReviewAssignment.reviewee_id)).label('total'),
        func.count(func.distinct(
            func.case([(ReviewAssignment.status == 'completed', ReviewAssignment.reviewee_id)])
        )).label('completed')
    ).join(User, User.id == ReviewAssignment.reviewee_id)\
     .join(Organization, Organization.id == User.organization_id)\
     .filter(ReviewAssignment.cycle_id == cycle_id)\
     .group_by(Organization.name).all()

    department_breakdown = [
        {
            "department": dept_name,
            "total_participants": total,
            "completed_participants": completed,
            "completion_rate": (completed / total * 100) if total > 0 else 0
        }
        for dept_name, total, completed in dept_stats
    ]

    return {
        "cycle": {
            "id": str(cycle.id),
            "name": cycle.name,
            "period": cycle.period,
            "status": cycle.status,
            "start_date": cycle.start_date,
            "end_date": cycle.end_date
        },
        "participation": {
            "total_participants": total_participants,
            "completed_participants": completed_participants,
            "completion_rate": (completed_participants / total_participants * 100) if total_participants > 0 else 0
        },
        "assignment_statistics": assignment_stats,
        "department_breakdown": department_breakdown
    }

@router.get("/cycles/{cycle_id}/user-progress")
async def get_user_progress(
    cycle_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed progress for all users in a cycle"""
    user_permissions = UserPermissions(db)

    if "review_view_all" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view user progress"
        )

    # Get all users in the cycle with their assignment details
    user_progress = db.query(
        User.id,
        User.first_name,
        User.last_name,
        User.job_title,
        Organization.name.label('department'),
        func.count(ReviewAssignment.id).label('total_assignments'),
        func.count(
            func.case([(ReviewAssignment.status == 'completed', 1)])
        ).label('completed_assignments')
    ).join(ReviewAssignment, ReviewAssignment.reviewee_id == User.id)\
     .join(Organization, Organization.id == User.organization_id)\
     .filter(ReviewAssignment.cycle_id == cycle_id)\
     .group_by(User.id, User.first_name, User.last_name, User.job_title, Organization.name).all()

    result = []
    for progress in user_progress:
        user_id = str(progress.id)

        # Get assignment breakdown by type
        assignments_by_type = {}
        for review_type in ['self', 'peer', 'supervisor']:
            type_assignments = db.query(ReviewAssignment).filter(
                ReviewAssignment.cycle_id == cycle_id,
                ReviewAssignment.reviewee_id == progress.id,
                ReviewAssignment.review_type == review_type
            ).all()

            completed_type = [a for a in type_assignments if a.status == 'completed']

            assignments_by_type[review_type] = {
                "total": len(type_assignments),
                "completed": len(completed_type),
                "pending": len(type_assignments) - len(completed_type)
            }

        result.append({
            "user_id": user_id,
            "name": f"{progress.first_name} {progress.last_name}",
            "job_title": progress.job_title,
            "department": progress.department,
            "overall_progress": {
                "total_assignments": progress.total_assignments,
                "completed_assignments": progress.completed_assignments,
                "completion_rate": (progress.completed_assignments / progress.total_assignments * 100) if progress.total_assignments > 0 else 0
            },
            "assignments_by_type": assignments_by_type
        })

    return result

@router.get("/users/{user_id}/review-scores/{cycle_id}")
async def get_user_review_scores(
    user_id: str,
    cycle_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed review scores for a user in a specific cycle"""
    user_permissions = UserPermissions(db)

    # Check if user can view these scores (self or has permission)
    if str(current_user.user_id) != user_id and "review_view_all" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view user scores"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cycle = db.query(ReviewCycle).filter(ReviewCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Review cycle not found")

    # Get review scores for this user in this cycle
    scores = db.query(ReviewScore).filter(
        ReviewScore.cycle_id == cycle_id,
        ReviewScore.user_id == user_id
    ).all()

    trait_scores = []
    overall_scores = {"self": [], "peer": [], "supervisor": [], "weighted": []}

    for score in scores:
        trait = db.query(ReviewTrait).filter(ReviewTrait.id == score.trait_id).first()
        if trait:
            trait_data = {
                "trait_name": trait.name,
                "trait_description": trait.description,
                "self_score": float(score.self_score) if score.self_score else None,
                "peer_score": float(score.peer_score) if score.peer_score else None,
                "supervisor_score": float(score.supervisor_score) if score.supervisor_score else None,
                "weighted_score": float(score.weighted_score) if score.weighted_score else None
            }
            trait_scores.append(trait_data)

            # Collect for overall averages
            if score.self_score:
                overall_scores["self"].append(float(score.self_score))
            if score.peer_score:
                overall_scores["peer"].append(float(score.peer_score))
            if score.supervisor_score:
                overall_scores["supervisor"].append(float(score.supervisor_score))
            if score.weighted_score:
                overall_scores["weighted"].append(float(score.weighted_score))

    # Calculate overall averages
    overall_averages = {}
    for score_type, values in overall_scores.items():
        overall_averages[f"{score_type}_average"] = sum(values) / len(values) if values else None

    return {
        "user": {
            "id": user_id,
            "name": f"{user.first_name} {user.last_name}",
            "job_title": user.job_title,
            "department": user.organization.name if user.organization else None
        },
        "cycle": {
            "id": str(cycle.id),
            "name": cycle.name,
            "period": cycle.period
        },
        "trait_scores": trait_scores,
        "overall_averages": overall_averages
    }