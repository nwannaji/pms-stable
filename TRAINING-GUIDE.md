# Nigcomsat Performance Management System (PMS) — Staff Training Guide

> **A complete, step-by-step practical guide for every user of the PMS application.**
> Covers login, goals, initiatives, tasks, scorecards, performance reviews, and more.

---

## Table of Contents

1. [Getting Started — Logging In](#1-getting-started--logging-in)
2. [Understanding Your Dashboard](#2-understanding-your-dashboard)
3. [Navigating the System](#3-navigating-the-system)
4. [Goals — Setting and Managing Performance Goals](#4-goals--setting-and-managing-performance-goals)
5. [Initiatives — Assigning and Tracking Work](#5-initiatives--assigning-and-tracking-work)
6. [Tasks — Day-to-Day Task Management](#6-tasks--day-to-day-task-management)
7. [Scorecards — Goal Scoring and Evaluation](#7-scorecards--goal-scoring-and-evaluation)
8. [Performance Reviews](#8-performance-reviews)
9. [Notifications — Staying Informed](#9-notifications--staying-informed)
10. [Calendar](#10-calendar)
11. [Supervisor-Specific Features](#11-supervisor-specific-features)
12. [Admin-Specific Features](#12-admin-specific-features)
13. [Settings — Updating Your Profile](#13-settings--updating-your-profile)
14. [Frequently Asked Questions (FAQ)](#14-frequently-asked-questions-faq)
15. [Glossary](#15-glossary)

---

## 1. Getting Started — Logging In

### 1.1 First-Time Login (Onboarding)

When an administrator creates your account, you will receive an email with an onboarding link.

1. Click the onboarding link in your email.
2. You will be taken to the **"Set Up Your Password"** page.
3. Enter your new password (must be at least **8 characters** — we recommend a mix of letters, numbers, and special characters).
4. Confirm your password by typing it again.
5. Click **"Complete Setup"**.
6. A success message will appear: *"Welcome to Nigcomsat PMS! Your account has been set up successfully."*
7. You will be automatically redirected to the **Login** page.

### 1.2 Regular Login

1. Open your web browser and go to the PMS website address (provided by your administrator).
2. You will see the **Sign In** page with the Nigcomsat logo.
3. Enter your **email address** in the "Email" field.
4. Enter your **password** in the "Password" field.
5. Click the **eye icon** (👁) next to the password field if you want to see what you are typing.
6. Click **"Sign in"**.
7. If successful, you will be taken to your **Dashboard**.

> **Tip:** If you see an error message, double-check your email and password. After multiple failed attempts, you may be temporarily rate-limited. Contact your administrator if you are still unable to log in.

> **Session Timeout:** Your login session expires after **30 minutes** of inactivity. If your session expires, you will see a notification and be redirected back to the login page.

### 1.3 Forgot Password

1. On the Sign In page, click **"Forgot your password?"**.
2. Enter your email address and submit the form.
3. You will receive an email with a password reset link.
4. Click the link and set a new password.

### 1.4 Logging Out

- Click your name/avatar in the **bottom-left corner** of the sidebar.
- Click **"Sign out"**.

---

## 2. Understanding Your Dashboard

After logging in, you land on the **Dashboard** — your home base. The dashboard shows different views depending on your role:

### 2.1 Employee Dashboard

If you do **not** supervise any staff, you see the **Employee Dashboard**:

| Section | What It Shows |
|---|---|
| **Welcome Banner** | "Welcome back, [Your First Name]" with a performance overview |
| **KPI Cards** | Number of your initiatives, completed initiatives, active goals, and items pending approval |
| **Upcoming Initiatives** | Initiatives due within 7 days, with urgency and status badges |
| **Awaiting Supervisor Approval** | Items you created that your supervisor has not yet approved |
| **My Goals (sidebar)** | Your active personal goals with progress bars |
| **Quick Actions** | Shortcuts to "Manage Initiatives" and "Manage Goals" |

### 2.2 Supervisor Dashboard

If you **supervise other staff**, you see the **Supervisor Dashboard**:

| Section | What It Shows |
|---|---|
| **Supervisor Banner** | "Supervisor Dashboard — Manage your performance and your team's progress" |
| **KPI Cards** | Pending approvals (for your team), number of team members, your own initiatives, and your own goals |
| **Requires Your Approval** | A highlighted section showing team initiatives and goals that need your review |
| **Team Performance** | Active goals belonging to your team members |
| **My Goals (sidebar)** | Your own active personal goals |
| **Quick Actions** | Shortcuts to Team Initiatives, Team Goals, and My Initiatives |

> **Tip:** Click any KPI card to navigate directly to the relevant page.

---

## 3. Navigating the System

The **sidebar** on the left side of the screen is your primary navigation. It is organized into sections:

### Main Navigation (visible to all users)

| Menu Item | Icon | What It Does |
|---|---|---|
| **Dashboard** | 🏠 | Your home page with performance overview |
| **Initiatives** | ☑️ | Manage your initiatives and work assignments |
| **Goals** | 🎯 | Set and track personal and team performance goals |
| **Calendar** | 📅 | View goals and initiatives on a calendar |
| **Reviews** | ⭐ | Complete your self-reviews and supervisor reviews |

### Management Section (visible to admins and managers only)

| Menu Item | Icon | Required Permission |
|---|---|---|
| **Organization** | 🏢 | `organization_create` |
| **Users** | 👥 | `user_view_all` |
| **Roles** | 🛡️ | `role_create` |
| **Goals Management** | 🎯 | `goal_create_yearly` |
| **Review Management** | ⭐ | `review_create_cycle` |
| **Performance Management** | 📈 | `performance_view_all` |

### Reports Section (visible to authorized users only)

| Menu Item | Icon | Required Permission |
|---|---|---|
| **Analytics** | 📊 | `reports_generate` |
| **Reports** | 📄 | `reports_generate` |

### Settings (visible to all users)

| Menu Item | Icon | What It Does |
|---|---|---|
| **Settings** | ⚙️ | Update your profile and preferences |

> **Note:** Menu items you do not have permission for will be hidden automatically.

---

## 4. Goals — Setting and Managing Performance Goals

Goals are the foundation of the PMS. They define what you aim to achieve during a performance period. Every staff member should have goals set at the beginning of each review cycle.

### 4.1 Goal Types

The system supports the following goal types:

| Goal Type | Who Creates It | Description |
|---|---|---|
| **Individual** | Any employee (for themselves) or supervisor (for a supervisee) | A personal performance goal tied to your role |
| **Company-Wide** (Yearly) | Admins with `goal_create_yearly` permission | Strategic goals that apply to the entire organization |
| **Departmental** | Users with `goal_create_departmental` permission | Goals scoped to a specific department or directorate |

### 4.2 Creating an Individual Goal (Employee)

1. Click **"Goals"** in the sidebar.
2. You will see two tabs: **"My Goals"** (your personal goals) and **"Team"** (supervisee goals, if you are a supervisor).
3. On the **"My Goals"** tab, click the **"+ Create Goal"** button.
4. In the dialog that appears:
   - **Goal Title** *(required)*: Enter a clear, specific title (e.g., "Increase customer satisfaction score by 15%").
   - **Description** *(optional)*: Use the rich text editor to describe what this goal aims to achieve.
   - **Difficulty Level**: Select 1 (Very Easy) through 5 (Very Hard).
   - **KPIs (Key Performance Indicators)**: Click **"+ Add KPI"** to add measurable targets:
     - Enter a **KPI description** (e.g., "Customer satisfaction score").
     - Enter a **Target value** (e.g., 85).
     - Select a **Unit** (%, count, NGN, days, hours, score, km, units).
     - You can add multiple KPIs.
   - **Tags** *(optional)*: Select from predefined tags to categorize your goal.
   - **Time Period** *(required)*: Choose **Yearly** or **Quarterly**.
     - If Quarterly, select the **Quarter** (Q1, Q2, Q3, Q4) and **Year**.
   - **Start Date / End Date** *(optional)*: Set specific date ranges.
   - **Link to Organizational Goal** *(optional)*: If departmental goals exist, you can link this individual goal to a parent organizational goal.
4. Click **"Create Goal"**.

> **Important:** Newly created individual goals start with **"Pending Approval"** status. Your supervisor must approve them before they become active.

### 4.3 Creating a Goal for a Supervisee (Supervisor)

1. Go to **Goals** → **Team** tab.
2. Click **"+ Create Goal"**.
3. Check the box **"Create this goal for a supervisee"**.
4. Select the supervisee from the dropdown.
5. Fill in the goal details as described above.
6. Click **"Create Goal"**.

> The supervisee will see this goal as **"Pending Approval"** and must **Accept** or **Decline** it.

### 4.4 Goal Statuses and Lifecycle

| Status | What It Means | What You Can Do |
|---|---|---|
| **Pending Approval** | Newly created, waiting for supervisor approval | Employee: wait for approval. Supervisor: Approve or Reject. |
| **Active** | Approved and currently in progress | Update progress, request changes, mark as complete, or discard. |
| **Completed** | Employee has marked the goal as complete (100% progress) | Supervisor: Score the goal (rate 0–5). |
| **Achieved** | Supervisor has scored and confirmed the goal as achieved | View only. Goal is finalized. |
| **Rejected** | Supervisor rejected this goal | Review the rejection reason and create a new goal if needed. |
| **Discarded** | Employee chose to discard this goal | No further action needed. |
| **Frozen** | Goal is locked and cannot be edited | Contact your administrator if you need changes. |

### 4.5 Updating Goal Progress

1. Go to **Goals** → find your active goal.
2. Click the **three-dot menu (⋮)** on the goal card.
3. Select **"Update Progress"**.
4. In the dialog:
   - **Progress Percentage**: Enter a number from 0 to 100.
   - **Progress Report** *(required)*: Describe the progress you have made.
   - If you set progress to **100%**, additional fields appear:
     - **Your Comment** *(optional)*: Add notes about completing the goal.
     - **KPI Actuals**: Enter the actual value you achieved for each KPI (required when marking complete).
5. Click **"Update Progress"** or **"Mark as Complete"**.

### 4.6 Responding to a Goal Assigned by Your Supervisor

When your supervisor creates a goal for you:

1. The goal appears with **"Pending Approval"** status and a badge showing it was assigned.
2. Click the **three-dot menu (⋮)** on the goal card.
3. Select **"Accept Goal"** or **"Decline Goal"**.
4. If declining, you must provide a reason.
5. Once accepted, the goal becomes **Active** and you can update its progress.

### 4.7 Requesting a Goal Change

If you need to modify an active goal:

1. Click the **three-dot menu (⋮)** on the goal card.
2. Select **"Request Change"**.
3. Describe the changes you need in the text box.
4. Click **"Submit Request"**.

Your supervisor will review the request and may update the goal.

### 4.8 Supervisor: Approving and Scoring Goals

#### Approving a Goal

1. Go to **Goals** → **Team** tab (or see the "Requires Your Approval" section on the Dashboard).
2. Click the **three-dot menu (⋮)** on a pending goal.
3. Select **"Approve Goal"** to open the review dialog.
4. Review the goal details: title, description, KPIs, dates, and difficulty.
5. Click **"Approve"** to approve or **"Reject"** to reject (with a reason).

#### Scoring a Completed Goal

When an employee marks a goal as **Completed**, you as the supervisor should score it:

1. Go to **Goals** → **Team** tab.
2. Find the goal with **"Completed"** status.
3. Click the **three-dot menu (⋮)** → **"Score Goal"**.
4. Review the employee's KPI actuals and comments.
5. Enter your **Score (0–5)**:
   - 0 = Not achieved at all
   - 1 = Very poor performance
   - 2 = Below expectations
   - 3 = Meets expectations
   - 4 = Exceeds expectations
   - 5 = Outstanding performance
6. Enter your **Comment** *(optional)*: Provide feedback.
7. Choose an **Achievement Override** (optional):
   - **Mark as Achieved**: Override the system and mark the goal as achieved.
   - **Not Achieved**: Override and mark the goal as not achieved.
   - **Auto (no override)**: Let the system decide based on progress percentage.
8. Click **"Submit Score"**.

---

## 5. Initiatives — Assigning and Tracking Work

Initiatives are specific work assignments or tasks that contribute toward your goals. They can be assigned to individuals or groups.

### 5.1 Creating an Initiative

1. Click **"Initiatives"** in the sidebar.
2. Click the **"+ Create Initiative"** button.
3. Fill in the form:
   - **Title** *(required)*: A clear name for the initiative.
   - **Description** *(optional)*: Detailed description of what needs to be done.
   - **Type** *(required)*: Choose **Individual** or **Group**.
   - **Priority** *(required)*: Select **Low**, **Medium**, **High**, or **Urgent**.
   - **Due Date** *(required)*: Must be a future date.
   - **Linked Goal** *(optional)*: Search and select an active goal to link this initiative to.
   - **Assignee** (for Individual type):
     - Check **"Create for myself"** to assign to yourself, OR
     - Uncheck and search for a colleague to assign to.
   - **Group Members** (for Group type): Select at least 2 members and a **Team Head**.
   - **Sub-tasks** *(optional)*: Add smaller trackable items within the initiative:
     - Type a sub-task title and click **+** to add it.
     - Optionally add a description for each sub-task.
   - **Attach Documents** *(optional)*: Upload files (PDF, Word, Excel, images, etc.) up to 10MB each, max 5 files.
4. Click **"Create"**.

### 5.2 Initiative Types

- **Individual**: Assigned to one person. You can assign it to yourself ("Create for myself") or to another colleague.
- **Group**: Assigned to 2 or more people. You must select a **Team Head** who will be responsible for the group's work and can submit on behalf of the team.

### 5.3 Initiative Statuses and Lifecycle

| Status | What It Means | Who Acts |
|---|---|---|
| **Pending Approval** | Newly created by a supervisor for a supervisee, waiting for approval | Supervisor approves/rejects |
| **Assigned** | Initiative has been assigned to someone, waiting for them to accept | Assignee accepts |
| **Pending** | Accepted and ready to begin | Assignee starts |
| **Ongoing** | Work is in progress | Assignee submits when done |
| **Under Review** | Assignee has submitted their work for review | Supervisor reviews |
| **Approved** | Supervisor has approved with a grade | Initiative is complete |
| **Rejected** | Supervisor has rejected the submission | Assignee may need to redo |
| **Overdue** | Past the due date | Assignee should submit ASAP |

### 5.4 Initiative Workflow — Step by Step

#### As the Assignee (Person Doing the Work):

1. **Receive Assignment**: You see the initiative in your **"My Initiatives"** tab.
2. **Accept**: If the status is **"Assigned"**, click the initiative → click **"Accept Initiative"**.
3. **Start**: Once accepted (status: **"Pending"**), click **"Start Initiative"** to begin work.
4. **Work on It**: The status changes to **"Ongoing"**. You can track sub-tasks by checking them off.
5. **Submit**: When done, click **"Submit Initiative"**. Write a **Completion Report** (rich text) and optionally attach supporting documents. Click **"Submit Initiative"**.
6. **If Rejected**: If your supervisor rejects your submission, you will see **Redo Instructions** in orange. Address the feedback and resubmit.

#### As the Supervisor (Person Who Created or Reviews):

1. **Create and Assign**: Create an initiative for a supervisee.
2. **Approve** (if created by the supervisee): If the initiative is in "Pending Approval" status, click **"Review & Approve"**.
3. **Review Submission**: When the status becomes **"Under Review"**, click **"Review Initiative"**.
4. **Grade and Provide Feedback**:
   - Select a **Grade (1–10)**:
     - 1–3 = Poor
     - 4–6 = Fair
     - 7–8 = Good
     - 9–10 = Excellent
   - Enter **Feedback** *(optional for approval, required for rejection)*.
5. Click **"Accept & Grade"** to approve, or **"Reject"** to send it back for redo.

### 5.5 Viewing Initiative Details

Click on any initiative row in the table to open the **detail dialog**. This shows:
- Title, description, urgency, and status
- List of assignees (with Team Head badge for group initiatives)
- Sub-tasks with checkboxes
- Created date and due date
- Score (if reviewed)
- Attached documents (with download buttons)
- Submission report (if the initiative has been submitted)
- Supervisor feedback (if the initiative was reviewed or sent back for redo)

### 5.6 Filtering and Searching Initiatives

On the Initiatives page:
- Use the **search bar** to search by title, description, or assignee name.
- Use **filters** for Status (e.g., Ongoing, Under Review), Priority (Low, Medium, High, Urgent), and Type (Individual, Group).
- Switch between tabs: **My Initiatives** (assigned to you), **Team Initiatives** (supervisor view of supervisee initiatives), and **All Initiatives** (admin view).

---

## 6. Tasks — Day-to-Day Task Management

Tasks are similar to initiatives but are simpler and more focused on day-to-day work items. The task workflow mirrors the initiative lifecycle.

### 6.1 Task Statuses

| Status | Description |
|---|---|
| **Pending Approval** | Task created for someone else, awaiting supervisor approval |
| **Assigned** | Task assigned, waiting for the assignee to accept |
| **Started** | Work has begun |
| **Completed** | Assignee has marked the task as complete |
| **Approved** | Supervisor has approved the completed task |
| **Overdue** | Past the due date without completion |
| **Rejected** | Supervisor has rejected the task |

### 6.2 Creating a Task

1. Go to **Tasks** from the sidebar.
2. Click **"+ Create Task"**.
3. Fill in: title, description, priority, due date, assignee, and optionally link to a goal.
4. Click **"Create"**.

### 6.3 Completing and Reviewing Tasks

- **As assignee**: Accept → Start → Submit (with completion report) → Awaiting review.
- **As supervisor**: Review the submission → Approve (with a score) or Reject (with feedback).

The workflow is the same as initiatives but simplified.

---

## 7. Scorecards — Goal Scoring and Evaluation

Scorecards are the evaluation component of the PMS. They bring together goal scores, initiative grades, and performance review results into a comprehensive view.

### 7.1 How Scoring Works

Each goal can be scored by the supervisor on a **0–5 scale**:

| Score | Meaning |
|---|---|
| 0 | Not achieved at all |
| 1 | Very poor — far below expectations |
| 2 | Below expectations |
| 3 | Meets expectations |
| 4 | Exceeds expectations |
| 5 | Outstanding performance |

### 7.2 KPI-Based Scoring

If a goal has KPIs defined, the system automatically calculates a **KPI score** based on the actual values the employee enters versus the target values:

- **KPI Score** = min(actual / target, 1) × 5

For example, if the target was 30 and the actual was 27, the KPI score would be: min(27/30, 1) × 5 = **4.5/5**.

### 7.3 Achievement Status

A goal's achievement status is determined by:
1. **Progress percentage**: If 100%, the goal is considered for "Achieved" status.
2. **Supervisor override**: The supervisor can manually mark a goal as "Achieved" or "Not Achieved" regardless of progress.
3. **Auto (default)**: The system marks a goal as achieved when progress reaches 100%.

### 7.4 Viewing the Performance/Scorecard Page

1. Go to **Performance Management** (visible with `performance_view_all` permission).
2. Select a **Review Cycle** from the dropdown.
3. Filter by **Department** if needed.
4. The page shows a table of all employees with:
   - Their name, job title, department, and supervisor.
   - Overall scores across all performance dimensions.
5. Click on an employee's row to see their detailed performance breakdown, including:
   - Goal scores (weighted by difficulty level)
   - Initiative grades
   - Review scores for each trait

### 7.5 How Overall Performance Scores Are Calculated

The system combines multiple dimensions into an overall performance score:

**Review Score per Trait:**
- Weighted formula: `Self Score × 20% + Peer Score × 30% + Supervisor Score × 50%`
- Each trait receives a weighted average of self, peer, and supervisor ratings.

**Overall Performance Score:**
- `Task Performance × 60% + Review Performance × 40%`
- This combines initiative/task grades with review scores.

**Performance Bands:**

| Band | Meaning |
|---|---|
| **Outstanding** | Exceptional performance, well above expectations |
| **Exceeds Expectations** | Strong performance, above the expected standard |
| **Meets Expectations** | Solid performance at the expected level |
| **Below Expectations** | Performance needs improvement |
| **Needs Improvement** | Performance is significantly below expectations |

### 7.6 Employee Scorecard View

For individual employees, their scorecard shows:
- All goals and their progress, scores, and achievement status.
- KPI actuals vs targets.
- Initiative grades.
- Review results per trait.

---

## 8. Performance Reviews

Performance reviews are formal assessments conducted during a review cycle. They consist of structured questionnaires that cover various performance traits.

### 8.1 Review Cycles

A **Review Cycle** is a period (e.g., "Q1 2025 Performance Review") created by an administrator. Each cycle contains:
- **Traits**: Performance dimensions being evaluated (e.g., "Communication", "Leadership", "Technical Skills").
- **Questions**: Specific questions under each trait, rated on a scale of 1–10.
- **Assignments**: Each employee gets a **self-review** assignment and their supervisor gets a **supervisor review** assignment.

Review cycles can be one of four types: **Quarterly**, **Annual**, **Probationary**, or **Project**.

### 8.2 Completing a Self-Review

1. Go to **Reviews** from the sidebar.
2. Select a **Review Cycle** from the dropdown at the top.
3. Under the **Self** tab, you will see your self-review assignment.
4. Click **"Start Review"**.
5. For each question:
   - Read the question carefully.
   - Select your rating (typically 1–5).
   - Add any comments if the field is available.
6. Your progress is saved automatically. You can leave and come back.
7. When all questions are answered, the review is marked as **"Completed"**.

### 8.3 Completing a Supervisor Review (for Supervisors)

1. Go to **Reviews** from the sidebar.
2. Select the appropriate **Review Cycle**.
3. Under the **Supervisee** tab, you will see review assignments for each of your supervisees.
4. Click **"Start Review"** next to a supervisee's name.
5. Answer each question about the supervisee's performance.
6. Complete all questions to finalize the review.

### 8.4 Review Management (Admins)

Administrators with the `review_create_cycle` permission can:

1. Go to **Review Management** from the sidebar.
2. **Create a Review Cycle**:
   - Enter a name (e.g., "Q1 2025 Performance Review").
   - Set the period (start and end dates).
   - Select which traits to include.
   - Configure questions for each trait.
3. **Launch a Cycle**: When ready, change the cycle status from "Draft" to "Active" to begin collecting reviews.
4. **Monitor Progress**: View which employees have completed their reviews and who is still pending.
5. **View Results**: See aggregated scores for each trait and employee.

---

## 9. Notifications — Staying Informed

The PMS sends real-time notifications to keep you informed about important events.

### 9.1 Notification Types

| Notification | What It Means |
|---|---|
| **Initiative Assigned** | A new initiative has been assigned to you |
| **Initiative Approved** | Your initiative submission was approved |
| **Initiative Rejected** | Your initiative submission was rejected (with feedback) |
| **Initiative Status Changed** | An initiative's status has been updated |
| **Initiative Submitted** | A supervisee has submitted an initiative for your review |
| **Initiative Reviewed** | Your supervisor has reviewed your initiative |
| **Initiative Deadline Approaching** | An initiative is due soon |
| **Goal Assigned** | A goal has been assigned to you by your supervisor |
| **Goal Approved** | Your goal has been approved |
| **Goal Rejected** | Your goal has been rejected (with reason) |
| **Goal Progress Updated** | Progress has been updated on a goal |
| **Goal Deadline Approaching** | A goal deadline is approaching |
| **Task Assigned** | A new task has been assigned to you |
| **Task Submitted** | A task has been submitted for review |
| **Task Reviewed** | A task review has been completed |
| **Task Deadline Approaching** | A task deadline is approaching |
| **Role Changed** | Your role or permissions have been updated |
| **General** | A general system notification |

### 9.2 Viewing Notifications

1. Click the **bell icon 🔔** in the top-right header of the application.
2. A dropdown shows your most recent notifications.
3. Click **"View All"** to go to the full Notifications page.
4. On the Notifications page:
   - Filter by **Type** (e.g., Goals, Initiatives, Tasks).
   - Filter by **Priority** (Low, Normal, High, Urgent).
   - Toggle **"Show unread only"** to focus on new items.
   - Click **"Mark All as Read"** to clear your unread count.
   - Click on a notification to navigate to the related item.

---

## 10. Calendar

The Calendar page provides a visual view of your goals and initiatives on a calendar timeline.

1. Click **"Calendar"** in the sidebar.
2. Use the month/year navigation to browse different periods.
3. Goals and initiatives appear as events on their due dates.
4. Color coding helps you quickly identify the type and status of each item.

---

## 11. Supervisor-Specific Features

If you supervise one or more staff members, you have additional capabilities:

### 11.1 Team View Tabs

On the **Goals** and **Initiatives** pages, you will see a **"Team"** tab alongside your own items. This tab shows all goals and initiatives belonging to your supervisees.

### 11.2 Approval Workflows

As a supervisor, you are responsible for:

| Action | Where | Description |
|---|---|---|
| **Approve/Reject Goals** | Goals → Team tab | Review and approve or reject goals created by your supervisees |
| **Score Completed Goals** | Goals → Team tab | Rate supervisee goals on a 0–5 scale when they are marked complete |
| **Approve/Reject Initiatives** | Initiatives → Team tab | Review and approve initiatives created by your supervisees |
| **Review Initiative Submissions** | Initiatives → Team tab | Grade and provide feedback on completed initiative submissions |
| **Complete Supervisor Reviews** | Reviews → Supervisee tab | Evaluate your supervisees during review cycles |

### 11.3 Dashboard Alerts

The Supervisor Dashboard prominently highlights:
- **Pending Approvals**: Items awaiting your review, shown in a yellow-highlighted section.
- **Team Performance**: Active goals across your team with progress bars.
- **Team Initiatives**: Quick access to your team's ongoing work.

---

## 12. Admin-Specific Features

Administrators with special permissions have access to the **Management** section in the sidebar:

### 12.1 Organization Management

- View, create, and edit the organizational structure.
- Hierarchy: **Global → Directorate → Department → Division → Unit**.
- Each organizational unit has a name, level, and parent unit.
- A unit's scope determines what data its users can see:
  - **Global** level users can see everything.
  - **Directorate** level users see their directorate and all departments/divisions/units below.
  - **Department/Division/Unit** level users see only their own org and descendants.
- Role scope overrides (`GLOBAL` or `CROSS_DIRECTORATE`) can extend a user's visibility beyond their org level.

### 12.2 User Management

- **View all users** with search and filter capabilities.
- **Create users**: Enter name, email, job title, department, role, and supervisor.
- **Edit users**: Update user information, change roles, assign supervisors.
- **User statuses**:
  - **Pending Activation**: User has been created but has not yet set their password.
  - **Active**: User is fully set up and can use the system.
  - **Suspended**: User account has been temporarily disabled.
  - **On Leave**: User is on leave.
  - **Archived**: User account has been permanently deactivated.
- **Resend onboarding email**: If a user has not activated their account, you can resend the invitation.
- **Reset password**: Generate a password reset link for a user.

### 12.3 Roles and Permissions

- Create custom roles with specific permissions.
- Each role defines what actions a user can perform.
- **Scope** options for roles:
  - **None (Organizational Scope)**: Access limited to the user's own department and below.
  - **Global Access**: Access to all data across the entire system.
  - **Cross-Directorate**: Access across multiple directorates.
- Permissions include granular controls like:
  - `user_view_all`, `user_create`, `user_edit`, `user_deactivate`
  - `goal_create_yearly`, `goal_create_departmental`
  - `initiative_approve`
  - `review_create_cycle`, `review_manage_traits`
  - `performance_view_all`
  - `reports_generate`
  - `system_admin` (superuser — full access)

### 12.4 Goals Management

- Create **Company-Wide (Yearly)** and **Departmental** goals.
- Manage goal tags (categories with colors).
- View and manage all goals across the organization.

### 12.5 Review Management

- Create and manage **Review Cycles**.
- Define **Traits** (performance dimensions) and **Questions**.
- **Trait types**: Value traits (rated numerically) and Competency traits (rated against standards).
- Assign review questionnaires to employees and their supervisors.
- Monitor review completion progress.
- View aggregated results.

### 12.6 Performance Management

- View organization-wide performance data.
- Filter by department and review cycle.
- See individual employee performance profiles.
- Compare scores across traits, goals, and initiatives.

---

## 13. Settings — Updating Your Profile

1. Click **"Settings"** in the sidebar.
2. Here you can:
   - Update your **name** and **contact information**.
   - Change your **profile picture**.
   - Change your **password**.
   - Set notification preferences.

---

## 14. Frequently Asked Questions (FAQ)

### Login & Access

**Q: I can't log in. What should I do?**
> A: First, make sure you are using the correct email address. If you have forgotten your password, click "Forgot your password?" on the login page. If you still can't access your account, contact your administrator.

**Q: How do I get an account?**
> A: Your administrator creates your account and sends you an onboarding email with a link to set your password.

### Goals

**Q: Why is my goal showing "Pending Approval"?**
> A: All new individual goals need to be approved by your supervisor before they become active. Contact your supervisor if they haven't reviewed it.

**Q: Can I edit a goal after it's been approved?**
> A: You can use the "Request Change" option on an active goal. This sends a request to your supervisor, who can then update the goal.

**Q: What are KPIs and do I have to add them?**
> A: KPIs (Key Performance Indicators) are measurable targets that make your goal specific and trackable. They are optional but strongly recommended. For example, instead of "Improve sales," a KPI would be "Achieve 30% increase in sales" with a target value of 30 and unit of %.

**Q: What does the difficulty level mean?**
> A: The difficulty level (1–5) helps weight your goals in the scorecard. Higher difficulty goals contribute more to your overall performance score.
> - 1 = Very Easy
> - 2 = Easy
> - 3 = Medium (default)
> - 4 = Hard
> - 5 = Very Hard

### Initiatives

**Q: What's the difference between an initiative and a goal?**
> A: A **Goal** is a high-level performance target (e.g., "Improve customer satisfaction by 15%"). An **Initiative** is a specific piece of work or task that helps achieve that goal (e.g., "Conduct customer feedback survey by March 31"). Goals define *what* you want to achieve; initiatives define *how* you will achieve it.

**Q: Can I assign an initiative to a group?**
> A: Yes. When creating an initiative, select "Group" as the type. Then choose at least 2 group members and select one as the **Team Head**.

**Q: What happens when I submit an initiative?**
> A: Your supervisor receives a notification and can review your submission. They will grade it (1–10) and may provide feedback. If approved, the initiative is marked as "Approved." If rejected, you will see redo instructions and can resubmit.

### Reviews

**Q: When will I receive a review assignment?**
> A: Review assignments are created when your administrator launches a review cycle. You will receive a notification when your review is available.

**Q: Can I save my review and come back later?**
> A: Yes, your progress is saved automatically. You can leave and return to complete the review at any time before the deadline.

**Q: What is the difference between a self-review and a supervisor review?**
> A: A **Self-review** is where you evaluate your own performance. A **Supervisor review** is where your manager evaluates your performance. Both use the same set of questions but from different perspectives.

### Notifications

**Q: How do I know when something needs my attention?**
> A: Check the bell icon 🔔 in the top-right corner. A number badge shows how many unread notifications you have. The Dashboard also highlights items needing your approval.

---

## 15. Glossary

| Term | Definition |
|---|---|
| **PMS** | Performance Management System — the application you are using |
| **Goal** | A performance target set for a specific period (yearly, quarterly, or departmental) |
| **KPI** | Key Performance Indicator — a measurable target that tracks progress toward a goal |
| **Initiative** | A specific work assignment or task that may be linked to a goal |
| **Scorecard** | A comprehensive evaluation that combines goal scores, initiative grades, and review ratings |
| **Review Cycle** | A defined period during which performance reviews are conducted |
| **Self-Review** | An assessment where an employee evaluates their own performance |
| **Supervisor Review** | An assessment where a manager evaluates a supervisee's performance |
| **Trait** | A performance dimension (e.g., Communication, Leadership) evaluated during reviews |
| **Scope** | The level of data access a user has (Organizational, Global, or Cross-Directorate) |
| **Onboarding** | The initial account setup process where a new user sets their password |
| **Dashboard** | The main landing page that shows an overview of your performance data |
| **Difficulty Level** | A rating (1–5) that weights a goal's importance in the overall scorecard |
| **Sub-task** | A smaller, trackable item within an initiative that can be checked off as completed |

---

*This training guide covers the Nigcomsat Performance Management System (PMS). For additional help, contact your system administrator or refer to the in-app tooltips and guides.*