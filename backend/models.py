from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Enum, Date, Float, Numeric, UniqueConstraint, CheckConstraint, Table, Index, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum
import uuid
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

# Enums for Organization Levels
class OrganizationLevel(str, enum.Enum):
    GLOBAL = "GLOBAL"
    DIRECTORATE = "DIRECTORATE"
    DEPARTMENT = "DEPARTMENT"
    DIVISION = "DIVISION"  # NEW: Between Department and Unit
    UNIT = "UNIT"

# Enums for Scope Overrides
class ScopeOverride(str, enum.Enum):
    NONE = "none"
    GLOBAL = "global"
    CROSS_DIRECTORATE = "cross_directorate"

# User Status Enums
class UserStatus(str, enum.Enum):
    PENDING_ACTIVATION = "PENDING_ACTIVATION"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ON_LEAVE = "ON_LEAVE"
    ARCHIVED = "ARCHIVED"

# Goal Enums
class GoalScope(str, enum.Enum):
    COMPANY_WIDE = "COMPANY_WIDE"  # Organizational-level goals
    DEPARTMENTAL = "DEPARTMENTAL"  # Department/Directorate-specific goals
    INDIVIDUAL = "INDIVIDUAL"  # Individual employee goals

class GoalType(str, enum.Enum):
    YEARLY = "YEARLY"
    QUARTERLY = "QUARTERLY"

class GoalStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"  # Individual goals awaiting approval
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"  # Assessment submitted; avg KPI ratio < 80%
    ACHIEVED = "ACHIEVED"    # Assessment submitted; avg KPI ratio >= 80%
    DISCARDED = "DISCARDED"
    REJECTED = "REJECTED"  # Individual goals rejected by supervisor/HOD

class Quarter(str, enum.Enum):
    Q1 = "Q1"  # Jan-Mar
    Q2 = "Q2"  # Apr-Jun
    Q3 = "Q3"  # Jul-Sep
    Q4 = "Q4"  # Oct-Dec

# Initiative Enums (formerly Task)
class InitiativeType(str, enum.Enum):
    INDIVIDUAL = "INDIVIDUAL"
    GROUP = "GROUP"

class InitiativeStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"  # Created by staff, waiting for supervisor approval
    ASSIGNED = "ASSIGNED"  # Supervisor created and assigned to me, waiting for acceptance
    PENDING = "PENDING"  # Accepted or approved, ready to start work
    ONGOING = "ONGOING"  # Actively working on the initiative
    UNDER_REVIEW = "UNDER_REVIEW"  # Submitted for supervisor review
    COMPLETED = "COMPLETED"  # Supervisor reviewed and approved with grade
    REJECTED = "REJECTED"  # Supervisor rejected during approval
    OVERDUE = "OVERDUE"  # Past due date

class InitiativeUrgency(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"

class ExtensionStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"

# Review System Enums
class ReviewCycleStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class ReviewStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    OVERDUE = "overdue"

class ReviewType(str, enum.Enum):
    SELF = "self"
    SUPERVISOR = "supervisor"
    SUBORDINATE = "subordinate"
    MULTISOURCE = "360"

class TraitScopeType(str, enum.Enum):
    GLOBAL = "global"
    DIRECTORATE = "directorate"
    DEPARTMENT = "department"
    UNIT = "unit"

# Performance System Enums
class PerformanceRating(str, enum.Enum):
    OUTSTANDING = "outstanding"
    EXCEEDS_EXPECTATIONS = "exceeds_expectations"
    MEETS_EXPECTATIONS = "meets_expectations"
    BELOW_EXPECTATIONS = "below_expectations"
    UNSATISFACTORY = "unsatisfactory"

class DevelopmentPlanStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    OVERDUE = "overdue"

# Core Models

class Organization(Base):
    """
    4-level organizational hierarchy: Global → Directorate → Department → Unit
    Foundation for all access control decisions
    """
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    level = Column(Enum(OrganizationLevel), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    parent = relationship("Organization", remote_side=[id], back_populates="children")
    children = relationship("Organization", back_populates="parent")
    users = relationship("User", back_populates="organization")

class Role(Base):
    """
    Permission templates with scope override capabilities
    Enables flexible access control beyond organizational boundaries
    """
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    is_leadership = Column(Boolean, default=False)
    scope_override = Column(Enum(ScopeOverride), default=ScopeOverride.NONE)
    permissions = Column(JSON, nullable=False, default=list)  # Array of permission strings
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", back_populates="role")

class User(Base):
    """
    Complete user profiles with organizational assignment and status management
    Status affects system behavior including task assignments and access
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)  # Full name for display purposes
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    middle_name = Column(String(100), nullable=True)
    phone = Column(String(20))
    address = Column(Text)
    skillset = Column(Text)
    level = Column(Integer)  # Changed to Integer for civil service grade levels (1-17)
    job_title = Column(String(255))
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE)
    password_hash = Column(String(255))
    email_verified_at = Column(DateTime(timezone=True))
    onboarding_token = Column(String(255))
    onboarding_token_expires_at = Column(DateTime(timezone=True))  # Token expiration time
    profile_image_path = Column(String(500), nullable=True)  # Local file path for profile images
    last_login = Column(DateTime(timezone=True), nullable=True)  # Updated on successful login
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    supervisor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    level_rank = Column(Integer, default=2)  # For level comparison

    # Relationships
    organization = relationship("Organization", back_populates="users")
    supervisor = relationship("User", remote_side=[id], backref="subordinates")
    role = relationship("Role", back_populates="users")
    created_initiatives = relationship("Initiative", foreign_keys="Initiative.created_by", back_populates="creator")
    initiative_assignments = relationship("InitiativeAssignment", back_populates="user")
    goals = relationship("Goal", foreign_keys="Goal.created_by", back_populates="creator")
    owned_goals = relationship("Goal", foreign_keys="Goal.owner_id", back_populates="owner")
    user_history = relationship("UserHistory", foreign_keys="UserHistory.user_id", back_populates="user")

class UserHistory(Base):
    """
    Comprehensive audit trail for all user changes
    Enables compliance reporting and rollback capabilities
    """
    __tablename__ = "user_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    action = Column(String(100), nullable=False)  # role_change, status_change, profile_edit, etc.
    old_value = Column(JSON)
    new_value = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Foreign Keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="user_history")
    admin = relationship("User", foreign_keys=[admin_id])


class RefreshToken(Base):
    """
    Refresh tokens for extended session management
    Allows users to get new access tokens without re-authenticating
    """
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    token = Column(String(255), nullable=False, unique=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Device/session tracking (optional)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Relationships
    user = relationship("User", backref="refresh_tokens")


class LoginSession(Base):
    """
    One row per platform login; session duration is computed at read time as
    COALESCE(logout_at, last_active_at) - login_at (never stored).
    The frontend heartbeat endpoint keeps last_active_at fresh (~2 min pings);
    a gap larger than STALE_AFTER_SECONDS closes the row (ended_reason='stale')
    and the next ping opens a new one.
    """
    __tablename__ = "login_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)

    # Denormalized so deleted users still appear in weekly aggregates (mirrors ActivityLog.user_email)
    user_email = Column(String(255), nullable=True)
    user_name = Column(String(255), nullable=True)

    login_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    logout_at = Column(DateTime(timezone=True), nullable=True)
    ended_reason = Column(String(20), nullable=True)  # 'logout' | 'stale'

    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_login_sessions_login_at", "login_at"),
        Index("ix_login_sessions_user_time", "user_id", "login_at"),
        Index("ix_login_sessions_open", "user_id", postgresql_where=text("logout_at IS NULL")),
    )


class Goal(Base):
    """
    Hierarchical goal management with cascading achievement
    Supports:
    - Scope: COMPANY_WIDE (organizational), DEPARTMENTAL (specific dept/directorate), INDIVIDUAL (employee)
    - Type: YEARLY, QUARTERLY
    Goals can be any combination (e.g., DEPARTMENTAL + YEARLY, INDIVIDUAL + QUARTERLY)
    """
    __tablename__ = "goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(1000), nullable=False)
    description = Column(Text)  # Now supports rich text (HTML)
    kpis = Column(Text, nullable=True)  # Key Performance Indicators
    scope = Column(Enum(GoalScope), nullable=True)  # Nullable for backward compatibility with existing goals
    type = Column(Enum(GoalType), nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    progress_percentage = Column(Integer, default=0)
    status = Column(Enum(GoalStatus), default=GoalStatus.ACTIVE)

    # Time period fields
    quarter = Column(Enum(Quarter), nullable=True)  # Required for QUARTERLY type
    year = Column(Integer, nullable=True)  # Required for QUARTERLY type
    frozen = Column(Boolean, default=False)  # Frozen goals cannot be edited
    frozen_at = Column(DateTime(timezone=True))  # When goal was frozen
    frozen_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Approval fields for INDIVIDUAL scope goals
    rejection_reason = Column(Text, nullable=True)  # Why goal was rejected
    approved_at = Column(DateTime(timezone=True))
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    achieved = Column(Boolean, default=False)  # Set by supervisor assess; True if avg KPI ratio >= 80%
    achieved_at = Column(DateTime(timezone=True))
    discarded_at = Column(DateTime(timezone=True))

    # Comments & supervisor scoring
    employee_comment = Column(Text, nullable=True)   # Employee comment when completing goal
    supervisor_comment = Column(Text, nullable=True) # Supervisor comment when scoring
    supervisor_score = Column(Float, nullable=True)  # Supervisor manual score 0–5

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    parent_goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # For INDIVIDUAL scope goals
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)  # For DEPARTMENTAL scope goals

    # Relationships
    parent_goal = relationship("Goal", remote_side=[id], back_populates="child_goals")
    child_goals = relationship("Goal", back_populates="parent_goal")
    creator = relationship("User", foreign_keys=[created_by], back_populates="goals")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_goals")
    approver = relationship("User", foreign_keys=[approved_by])
    freezer = relationship("User", foreign_keys=[frozen_by])
    organization = relationship("Organization")  # For DEPARTMENTAL scope goals
    progress_reports = relationship("GoalProgressReport", back_populates="goal")
    initiatives = relationship("Initiative", back_populates="goal")
    tags = relationship("GoalTag", secondary="goal_tag_assignments", back_populates="goals")

class GoalProgressReport(Base):
    """
    Progress documentation for manual goal updates
    Required for any manual progress percentage changes
    """
    __tablename__ = "goal_progress_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    old_percentage = Column(Integer)
    new_percentage = Column(Integer)
    report = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Foreign Keys
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    goal = relationship("Goal", back_populates="progress_reports")
    updater = relationship("User")

class Initiative(Base):
    """
    Core initiative management with individual and group support
    Includes approval workflow and performance scoring
    Can be linked to goals
    """
    __tablename__ = "initiatives"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    type = Column(Enum(InitiativeType), nullable=False)
    urgency = Column(Enum(InitiativeUrgency), default=InitiativeUrgency.MEDIUM)
    due_date = Column(DateTime, nullable=False)
    status = Column(Enum(InitiativeStatus), default=InitiativeStatus.PENDING_APPROVAL)
    score = Column(Integer)  # 1-10 scale, set during final approval
    feedback = Column(Text)

    # Workflow timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))  # When supervisor completed final review
    rejected_at = Column(DateTime(timezone=True))  # When supervisor rejected
    reviewed_at = Column(DateTime(timezone=True))  # When final review completed

    # Foreign Keys
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)  # Who created
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Who approved/assigned
    team_head_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # For group initiatives
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=True)  # Optional link to goal

    # Relationships
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_initiatives")
    assigner = relationship("User", foreign_keys=[assigned_by])
    team_head = relationship("User", foreign_keys=[team_head_id])
    goal = relationship("Goal", back_populates="initiatives")
    assignments = relationship("InitiativeAssignment", back_populates="initiative", cascade="all, delete-orphan")
    submissions = relationship("InitiativeSubmission", back_populates="initiative", cascade="all, delete-orphan")
    documents = relationship("InitiativeDocument", back_populates="initiative", cascade="all, delete-orphan")
    extensions = relationship("InitiativeExtension", back_populates="initiative", cascade="all, delete-orphan")
    subtasks = relationship("InitiativeSubTask", back_populates="initiative", cascade="all, delete-orphan")

class InitiativeAssignment(Base):
    """
    Many-to-many relationship between initiatives and users
    Supports both individual and group initiative assignments
    """
    __tablename__ = "initiative_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Foreign Keys
    initiative_id = Column(UUID(as_uuid=True), ForeignKey("initiatives.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    initiative = relationship("Initiative", back_populates="assignments")
    user = relationship("User", back_populates="initiative_assignments")

class InitiativeSubmission(Base):
    """
    Initiative completion reports from assignees
    One submission per initiative (team head submits for group initiatives)
    """
    __tablename__ = "initiative_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    report = Column(Text, nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Foreign Keys
    initiative_id = Column(UUID(as_uuid=True), ForeignKey("initiatives.id"), nullable=False)
    submitted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    initiative = relationship("Initiative", back_populates="submissions")
    submitter = relationship("User")

class InitiativeDocument(Base):
    """
    File attachments for initiative submissions
    Supports multiple documents per initiative
    """
    __tablename__ = "initiative_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Foreign Keys
    initiative_id = Column(UUID(as_uuid=True), ForeignKey("initiatives.id"), nullable=True)  # Nullable for pre-upload
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    initiative = relationship("Initiative", back_populates="documents")
    uploader = relationship("User")

class InitiativeExtension(Base):
    """
    Deadline extension requests and approvals
    Handles overdue initiative management workflow
    """
    __tablename__ = "initiative_extensions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    new_due_date = Column(DateTime, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(Enum(ExtensionStatus), default=ExtensionStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    initiative_id = Column(UUID(as_uuid=True), ForeignKey("initiatives.id"), nullable=False)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    initiative = relationship("Initiative", back_populates="extensions")
    requester = relationship("User", foreign_keys=[requested_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])

class InitiativeSubTask(Base):
    """
    Sub-tasks for breaking down initiatives into smaller trackable units
    Created by assignees during ONGOING phase for better task management
    """
    __tablename__ = "initiative_subtasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default='pending')  # pending, completed
    sequence_order = Column(Integer, default=0)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    initiative_id = Column(UUID(as_uuid=True), ForeignKey("initiatives.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    initiative = relationship("Initiative", back_populates="subtasks")
    creator = relationship("User")

# Review System Models

class ReviewCycle(Base):
    """
    Performance review cycles with configurable components and workflows
    Supports quarterly, annual, probationary, and project-based reviews
    """
    __tablename__ = "review_cycles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # quarterly, annual, probationary, project
    period = Column(String(50), nullable=False)  # Q1-2024, FY-2024, etc.
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # JSON configurations
    phase_schedule = Column(JSON, nullable=False, default=dict)  # Timeline for different phases
    buffer_time = Column(String(20), default='1_week')  # Grace period for submissions
    target_population = Column(JSON)  # Criteria for automatic participant selection
    inclusion_criteria = Column(JSON)  # Who to include
    exclusion_criteria = Column(JSON)  # Who to exclude
    mandatory_participants = Column(JSON)  # List of user IDs that must participate
    components = Column(JSON, nullable=False, default=dict)  # Review components and weights
    ai_assistance = Column(JSON)  # AI configuration for insights and analysis
    calibration_sessions = Column(JSON)  # Calibration meeting configurations
    approval_workflow = Column(JSON)  # Multi-level approval process

    status = Column(Enum(ReviewCycleStatus), default=ReviewCycleStatus.DRAFT)
    participants_count = Column(Integer, default=0)
    completion_rate = Column(Float, default=0.0)
    quality_score = Column(Float, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    creator = relationship("User")
    reviews = relationship("Review", back_populates="cycle", cascade="all, delete-orphan")

class Review(Base):
    """
    Individual review instances within a cycle
    Supports self, supervisor, subordinate, and 360-degree reviews
    """
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    type = Column(Enum(ReviewType), nullable=False)

    # Response data and metadata
    responses = Column(JSON)  # All form responses
    completion_percentage = Column(Float, default=0.0)
    time_spent = Column(Integer, default=0)  # Minutes spent on review
    ai_insights = Column(JSON)  # AI-generated insights and suggestions

    status = Column(Enum(ReviewStatus), default=ReviewStatus.NOT_STARTED)
    deadline = Column(DateTime)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    submitted_at = Column(DateTime(timezone=True))

    # Foreign Keys
    cycle_id = Column(UUID(as_uuid=True), ForeignKey("review_cycles.id"), nullable=False)
    reviewee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))  # Null for self-reviews

    # Relationships
    cycle = relationship("ReviewCycle", back_populates="reviews")
    reviewee = relationship("User", foreign_keys=[reviewee_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])

# Performance Management Models

class PerformanceRecord(Base):
    """
    Consolidated performance records derived from reviews, tasks, and goals
    Provides historical performance tracking and analytics
    """
    __tablename__ = "performance_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    period = Column(String(50), nullable=False)  # Q1-2024, FY-2024
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Performance metrics
    overall_rating = Column(Enum(PerformanceRating))
    goal_achievement_rate = Column(Float)  # Percentage of goals achieved
    task_completion_rate = Column(Float)  # Percentage of tasks completed on time
    average_task_score = Column(Float)  # Average score from task reviews
    peer_feedback_score = Column(Float)  # Average peer review score

    # Detailed scores by category
    technical_competency = Column(Float)
    leadership_skills = Column(Float)
    communication_skills = Column(Float)
    teamwork_collaboration = Column(Float)
    innovation_creativity = Column(Float)

    # Qualitative assessments
    strengths = Column(JSON)  # List of identified strengths
    development_areas = Column(JSON)  # Areas needing improvement
    achievements = Column(JSON)  # Notable achievements
    feedback_summary = Column(Text)  # Consolidated feedback

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    review_cycle_id = Column(UUID(as_uuid=True), ForeignKey("review_cycles.id"))

    # Relationships
    user = relationship("User")
    review_cycle = relationship("ReviewCycle")

class DevelopmentPlan(Base):
    """
    Individual development plans with goals, activities, and tracking
    Supports career progression and skill development
    """
    __tablename__ = "development_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    period = Column(String(50))  # FY-2024, Q1-Q2-2024
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Development focus areas
    objectives = Column(JSON, nullable=False)  # List of development objectives
    activities = Column(JSON, nullable=False)  # Planned activities and milestones
    resources = Column(JSON)  # Required resources (training, mentoring, etc.)
    success_metrics = Column(JSON)  # How success will be measured

    progress_percentage = Column(Float, default=0.0)
    status = Column(Enum(DevelopmentPlanStatus), default=DevelopmentPlanStatus.DRAFT)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])

class CompetencyAssessment(Base):
    """
    Structured competency evaluations based on organizational competency frameworks
    Tracks skill levels and development over time
    """
    __tablename__ = "competency_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    competency_framework = Column(String(100), nullable=False)  # Technical, Leadership, Core
    assessment_date = Column(Date, nullable=False)

    # Assessment data
    competency_scores = Column(JSON, nullable=False)  # Scores for each competency
    evidence = Column(JSON)  # Evidence supporting the assessments
    assessor_notes = Column(Text)
    development_recommendations = Column(JSON)  # Specific recommendations

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Foreign Keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assessor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    performance_record_id = Column(UUID(as_uuid=True), ForeignKey("performance_records.id"))

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    assessor = relationship("User", foreign_keys=[assessor_id])
    performance_record = relationship("PerformanceRecord")

# Trait-Based Review System Models

class ReviewTrait(Base):
    """
    Configurable performance traits for review cycles with organizational scope
    Allows admin to define custom traits like Communication, Leadership, etc.

    Scope Types:
    - global: Applies to everyone in the organization
    - directorate/department/unit: Applies to specific organizational unit and all children
    """
    __tablename__ = "review_traits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer)

    # Scope configuration
    scope_type = Column(Enum(TraitScopeType, values_callable=lambda x: [e.value for e in x]), nullable=False, default=TraitScopeType.GLOBAL)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)

    # Grade level filtering: JSON list of ints (e.g. [12, 13]) or NULL = all levels
    applicable_levels = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    creator = relationship("User")
    organization = relationship("Organization")
    questions = relationship("ReviewQuestion", back_populates="trait", cascade="all, delete-orphan")
    cycle_traits = relationship("ReviewCycleTrait", back_populates="trait")
    scores = relationship("ReviewScore", back_populates="trait")

    # Constraints
    __table_args__ = (
        # Name must be unique within scope (global traits have unique names, scoped traits can have same name in different orgs)
        UniqueConstraint('name', 'scope_type', 'organization_id', name='unique_trait_name_scope'),
    )

class ReviewQuestion(Base):
    """
    Questions linked to specific traits with review type targeting
    """
    __tablename__ = "review_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    question_text = Column(Text, nullable=False)
    applies_to_self = Column(Boolean, default=True)
    applies_to_peer = Column(Boolean, default=True)
    applies_to_supervisor = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    trait_id = Column(UUID(as_uuid=True), ForeignKey("review_traits.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    trait = relationship("ReviewTrait", back_populates="questions")
    creator = relationship("User")
    responses = relationship("ReviewResponse", back_populates="question")

class ReviewCycleTrait(Base):
    """
    Junction table linking review cycles to selected traits
    """
    __tablename__ = "review_cycle_traits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Foreign Keys
    cycle_id = Column(UUID(as_uuid=True), ForeignKey("review_cycles.id", ondelete="CASCADE"), nullable=False)
    trait_id = Column(UUID(as_uuid=True), ForeignKey("review_traits.id"), nullable=False)

    # Relationships
    cycle = relationship("ReviewCycle")
    trait = relationship("ReviewTrait", back_populates="cycle_traits")

    # Constraints
    __table_args__ = (UniqueConstraint('cycle_id', 'trait_id', name='unique_cycle_trait'),)

class ReviewAssignment(Base):
    """
    Individual review assignments within a cycle
    Tracks self, peer, and supervisor review assignments
    """
    __tablename__ = "review_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    review_type = Column(String(20), nullable=False)  # self, peer, supervisor
    status = Column(String(20), default='pending')  # pending, in_progress, completed, overdue
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    cycle_id = Column(UUID(as_uuid=True), ForeignKey("review_cycles.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reviewee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    cycle = relationship("ReviewCycle")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    reviewee = relationship("User", foreign_keys=[reviewee_id])
    responses = relationship("ReviewResponse", back_populates="assignment", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('cycle_id', 'reviewer_id', 'reviewee_id', 'review_type', name='unique_assignment'),
        CheckConstraint("review_type IN ('self', 'peer', 'supervisor')", name='valid_review_type'),
        CheckConstraint("status IN ('pending', 'in_progress', 'completed', 'overdue')", name='valid_status')
    )

class ReviewResponse(Base):
    """
    Individual question responses within review assignments
    """
    __tablename__ = "review_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    rating = Column(Integer, nullable=False)  # 1-10 scale
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("review_assignments.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("review_questions.id"), nullable=False)

    # Relationships
    assignment = relationship("ReviewAssignment", back_populates="responses")
    question = relationship("ReviewQuestion", back_populates="responses")

    # Constraints
    __table_args__ = (
        UniqueConstraint('assignment_id', 'question_id', name='unique_response'),
        CheckConstraint("rating BETWEEN 1 AND 10", name='valid_rating')
    )

class ReviewScore(Base):
    """
    Calculated trait scores using weighted formula
    """
    __tablename__ = "review_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    self_score = Column(Numeric(3, 2))
    peer_score = Column(Numeric(3, 2))
    supervisor_score = Column(Numeric(3, 2))
    weighted_score = Column(Numeric(3, 2))  # self*0.2 + peer*0.3 + supervisor*0.5
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    cycle_id = Column(UUID(as_uuid=True), ForeignKey("review_cycles.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    trait_id = Column(UUID(as_uuid=True), ForeignKey("review_traits.id"), nullable=False)

    # Relationships
    cycle = relationship("ReviewCycle")
    user = relationship("User")
    trait = relationship("ReviewTrait", back_populates="scores")

    # Constraints
    __table_args__ = (UniqueConstraint('cycle_id', 'user_id', 'trait_id', name='unique_user_trait_score'),)

class PerformanceScore(Base):
    """
    Overall performance scores combining task and review performance
    """
    __tablename__ = "performance_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    task_performance_score = Column(Numeric(5, 2))
    review_performance_score = Column(Numeric(5, 2))
    overall_performance_score = Column(Numeric(5, 2))  # task*0.6 + review*0.4
    performance_band = Column(String(30))  # outstanding, exceeds_expectations, etc.
    organization_rank = Column(Integer)
    department_rank = Column(Integer)
    directorate_rank = Column(Integer)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Foreign Keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    cycle_id = Column(UUID(as_uuid=True), ForeignKey("review_cycles.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    user = relationship("User")
    cycle = relationship("ReviewCycle")

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'cycle_id', name='unique_user_cycle_performance'),
        CheckConstraint("performance_band IN ('outstanding', 'exceeds_expectations', 'meets_expectations', 'below_expectations', 'needs_improvement')", name='valid_performance_band')
    )

# Notification System Models

class NotificationType(str, enum.Enum):
    """Types of notifications in the system"""
    # Goal notifications
    GOAL_CREATED = "goal_created"
    GOAL_ASSIGNED = "goal_assigned"
    GOAL_APPROVED = "goal_approved"
    GOAL_REJECTED = "goal_rejected"
    GOAL_ACCEPTANCE_REQUIRED = "goal_acceptance_required"
    GOAL_ACCEPTED = "goal_accepted"
    GOAL_DECLINED = "goal_declined"
    GOAL_PROGRESS_UPDATED = "goal_progress_updated"
    GOAL_SCORED = "goal_scored"
    GOAL_COMPLETED = "goal_completed"

    # Initiative notifications
    INITIATIVE_CREATED = "initiative_created"
    INITIATIVE_ASSIGNED = "initiative_assigned"
    INITIATIVE_APPROVED = "initiative_approved"
    INITIATIVE_REJECTED = "initiative_rejected"
    INITIATIVE_SUBMITTED = "initiative_submitted"
    INITIATIVE_REVIEWED = "initiative_reviewed"
    INITIATIVE_OVERDUE = "initiative_overdue"
    INITIATIVE_EXTENSION_REQUESTED = "initiative_extension_requested"
    INITIATIVE_EXTENSION_APPROVED = "initiative_extension_approved"
    INITIATIVE_EXTENSION_DENIED = "initiative_extension_denied"

    # Review notifications
    REVIEW_ASSIGNED = "review_assigned"
    REVIEW_DUE_SOON = "review_due_soon"
    REVIEW_OVERDUE = "review_overdue"
    REVIEW_SUBMITTED = "review_submitted"

    # User notifications
    USER_CREATED = "user_created"
    USER_STATUS_CHANGED = "user_status_changed"
    USER_ROLE_CHANGED = "user_role_changed"

    # System notifications
    SYSTEM_ANNOUNCEMENT = "system_announcement"

class NotificationPriority(str, enum.Enum):
    """Priority levels for notifications"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class Notification(Base):
    """
    System-wide notification management
    Supports real-time and batched notifications for all user actions
    """
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    type = Column(Enum(NotificationType), nullable=False)
    priority = Column(Enum(NotificationPriority), default=NotificationPriority.MEDIUM)

    # Notification content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    action_url = Column(String(500))  # URL to navigate to when clicked

    # Metadata
    data = Column(JSON)  # Additional data (goal_id, initiative_id, etc.)

    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))  # Optional expiration for temporary notifications

    # Foreign Keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Who caused this notification

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    trigger_user = relationship("User", foreign_keys=[triggered_by])

class GoalAssignment(Base):
    """
    Track supervisor-assigned goals to supervisees
    Enables accept/reject workflow for assigned goals
    """
    __tablename__ = "goal_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Assignment status
    status = Column(Enum(GoalStatus), default=GoalStatus.PENDING_APPROVAL)
    response_message = Column(Text)  # Supervisee's response message

    # Timestamps
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True))

    # Foreign Keys
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)  # Supervisor
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)  # Supervisee

    # Relationships
    goal = relationship("Goal", backref="assignments")
    assigner = relationship("User", foreign_keys=[assigned_by])
    assignee = relationship("User", foreign_keys=[assigned_to])

    # Constraints
    __table_args__ = (
        UniqueConstraint('goal_id', 'assigned_to', name='unique_goal_assignment'),
    )

class GoalFreezeLog(Base):
    """
    Audit log for goal freeze/unfreeze actions
    Tracks who froze/unfroze goals, when, and why (especially for emergency overrides)
    """
    __tablename__ = "goal_freeze_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Freeze/Unfreeze action
    action = Column(String(20), nullable=False)  # 'freeze' or 'unfreeze'
    quarter = Column(Enum(Quarter), nullable=False)
    year = Column(Integer, nullable=False)
    affected_goals_count = Column(Integer, default=0)

    # Unfreeze scheduling
    scheduled_unfreeze_date = Column(DateTime(timezone=True), nullable=True)  # When goals should auto-unfreeze

    # Emergency override
    is_emergency_override = Column(Boolean, default=False)
    emergency_reason = Column(Text, nullable=True)  # Required for emergency unfreeze

    # Audit fields
    performed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    performed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    performer = relationship("User")

    # Constraints
    __table_args__ = (
        CheckConstraint("action IN ('freeze', 'unfreeze')", name='valid_freeze_action'),
    )

# Goal Tags/Labels - Association Table
goal_tag_assignments = Table(
    'goal_tag_assignments',
    Base.metadata,
    Column('goal_id', UUID(as_uuid=True), ForeignKey('goals.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', UUID(as_uuid=True), ForeignKey('goal_tags.id', ondelete='CASCADE'), primary_key=True),
    Column('assigned_at', DateTime(timezone=True), server_default=func.now())
)

# Activity tracking enums
class ActivityAction(str, enum.Enum):
    """Types of user activity events recorded for analytics"""
    # Authentication
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    PASSWORD_RESET = "PASSWORD_RESET"

    # Profile
    PROFILE_UPDATE = "PROFILE_UPDATE"
    PROFILE_IMAGE_UPDATE = "PROFILE_IMAGE_UPDATE"

    # Goals
    GOAL_CREATE = "GOAL_CREATE"
    GOAL_UPDATE = "GOAL_UPDATE"
    GOAL_PROGRESS_UPDATE = "GOAL_PROGRESS_UPDATE"
    GOAL_APPROVE = "GOAL_APPROVE"
    GOAL_DELETE = "GOAL_DELETE"
    GOAL_ASSESS = "GOAL_ASSESS"
    GOAL_FREEZE = "GOAL_FREEZE"

    # Initiatives
    INITIATIVE_CREATE = "INITIATIVE_CREATE"
    INITIATIVE_UPDATE = "INITIATIVE_UPDATE"
    INITIATIVE_SUBMIT = "INITIATIVE_SUBMIT"
    INITIATIVE_APPROVE = "INITIATIVE_APPROVE"
    INITIATIVE_COMPLETE = "INITIATIVE_COMPLETE"
    INITIATIVE_DOCUMENT_UPLOAD = "INITIATIVE_DOCUMENT_UPLOAD"

    # Reviews
    REVIEW_SUBMIT = "REVIEW_SUBMIT"
    REVIEW_CYCLE_CREATE = "REVIEW_CYCLE_CREATE"

    # Users (admin)
    USER_CREATE = "USER_CREATE"
    USER_UPDATE = "USER_UPDATE"
    USER_STATUS_CHANGE = "USER_STATUS_CHANGE"
    USER_DELETE = "USER_DELETE"
    SUPERVISOR_ASSIGN = "SUPERVISOR_ASSIGN"
    ROLE_CHANGE = "ROLE_CHANGE"

    # Reports
    REPORT_EXPORT = "REPORT_EXPORT"
    DOWNLOAD = "DOWNLOAD"

class ActivityLog(Base):
    """
    User activity audit trail for analytics and reporting
    Captures authentication events and business-object changes
    (no GET/page-view logging — write-side events only)
    """
    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_email = Column(String(255), nullable=True)  # Attempted email for LOGIN_FAILED
    action = Column(Enum(ActivityAction), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True)  # goal | initiative | user | review | report
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSON, nullable=True)  # NOTE: cannot be named "metadata" (reserved by SQLAlchemy)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_activity_user_time", "user_id", "created_at"),
        Index("ix_activity_action_time", "action", "created_at"),
    )


class GoalTag(Base):
    """
    Tags/Labels for categorizing goals (e.g., Infrastructure, Strategy)
    Can be filtered and have custom colors
    """
    __tablename__ = "goal_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False, unique=True)
    color = Column(String(7), nullable=False, default="#6B7280")  # Hex color code
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    creator = relationship("User")
    goals = relationship("Goal", secondary="goal_tag_assignments", back_populates="tags")