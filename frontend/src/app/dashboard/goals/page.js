"use client"

import React, { useState, useMemo, useEffect } from "react"
import {
  Plus,
  Target,
  Calendar,
  TrendingUp,
  MoreHorizontal,
  Edit,
  Trash2,
  FileText,
  Building2,
  Clock,
  Award,
  AlertCircle,
  CheckCircle2,
  CheckCircle,
  XCircle,
  CircleDot,
  MinusCircle,
  Lock,
  User,
  Users,
  Send,
  MessageSquare,
  Search,
  Filter,
  X
} from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { SearchableSelect } from "@/components/ui/searchable-select"
import { RichTextEditor } from "@/components/ui/rich-text-editor"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useAuth, usePermission } from "@/lib/auth-context"
import {
  useGoals,
  useCreateGoal,
  useUpdateGoal,
  useUpdateGoalProgress,
  useUpdateGoalStatus,
  useDeleteGoal,
  useApproveGoal,
  useSuperviseeGoals,
  useMySupervisees,
  useCreateGoalForSupervisee,
  useRespondToGoal,
  useRequestGoalChange,
  useUsers,
  useOrganizations,
  useGoalTags,
  useAssessGoal,
  useSupervisorScore
} from "@/lib/react-query"

const statusColors = {
  PENDING_APPROVAL: "bg-yellow-100 text-yellow-800 border-yellow-200",
  ACTIVE: "bg-blue-100 text-blue-800 border-blue-200",
  COMPLETED: "bg-sky-100 text-sky-800 border-sky-200",
  ACHIEVED: "bg-green-100 text-green-800 border-green-200",
  DISCARDED: "bg-gray-100 text-gray-800 border-gray-200",
  REJECTED: "bg-red-100 text-red-800 border-red-200",
}

const formatStatus = (status) => {
  if (!status) return ''
  return status.split('_').map(word =>
    word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
  ).join(' ')
}

const STATUS_CONFIG = {
  ACTIVE:           { icon: CircleDot,    className: "text-sky-700 bg-sky-50 border-sky-200",             label: "Active" },
  COMPLETED:        { icon: CheckCircle2, className: "text-green-700 bg-green-50 border-green-300",        label: "Completed" },
  ACHIEVED:         { icon: CheckCircle,  className: "text-emerald-50 bg-emerald-700 border-emerald-700",  label: "Achieved" },
  DISCARDED:        { icon: MinusCircle,  className: "text-gray-500 bg-gray-50 border-gray-200",           label: "Discarded" },
  PENDING_APPROVAL: { icon: Clock,        className: "text-amber-700 bg-amber-50 border-amber-200",        label: "Pending" },
  REJECTED:         { icon: XCircle,      className: "text-red-600 bg-red-50 border-red-200",              label: "Rejected" },
}

function GoalStatusBadge({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.ACTIVE
  const Icon = config.icon
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded border ${config.className}`}>
      <Icon className="h-2.5 w-2.5" />
      {config.label}
    </span>
  )
}

const TYPE_CONFIG_GOAL = {
  YEARLY:       { label: "Yearly" },
  QUARTERLY:    { label: "Quarterly" },
  DEPARTMENTAL: { label: "Departmental" },
  INDIVIDUAL:   { label: "Individual" },
}

function GoalTypeBadge({ type }) {
  const config = TYPE_CONFIG_GOAL[type]
  if (!config) return null
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded border border-gray-300 text-gray-500 bg-transparent">
      {config.label}
    </span>
  )
}

function GoalCard({
  goal,
  onEdit,
  onDelete,
  onUpdateProgress,
  onStatusChange,
  onApprove,
  onRespond,
  onRequestChange,
  onScoreGoal,
  canEdit = false,
  canApprove = false,
  isSuperviseeGoal = false,
  onViewDetails,
  currentUserId
}) {
  const isPendingApproval = goal.status === "PENDING_APPROVAL"
  const isActive = goal.status === "ACTIVE"
  const isAssignedByOther = goal.created_by !== goal.owner_id
  const isOwnGoal = goal.owner_id === currentUserId

  return (
    <Card
      className="relative cursor-pointer group flex flex-col h-full border-border/60 hover:border-border transition-colors duration-150"
      onClick={() => onViewDetails && onViewDetails(goal)}
    >
      <CardHeader className="space-y-2 pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <CardTitle className="text-sm font-semibold leading-snug line-clamp-2 break-words">
                    {goal.title}
                  </CardTitle>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-sm">
                  <p>{goal.title}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0 flex-shrink-0">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
              {/* Approve option for supervisors on supervisee goals (created by supervisees) */}
              {canApprove && isPendingApproval && isSuperviseeGoal && !isAssignedByOther && (
                <>
                  <DropdownMenuItem onClick={(e) => {
                    e.stopPropagation();
                    onApprove(goal);
                  }}>
                    <CheckCircle className="mr-2 h-4 w-4" />
                    Approve Goal
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                </>
              )}

              {/* Respond option for supervisees on goals assigned by supervisor */}
              {isPendingApproval && isAssignedByOther && isOwnGoal && (
                <>
                  <DropdownMenuItem onClick={(e) => {
                    e.stopPropagation();
                    onRespond(goal, true);
                  }}>
                    <CheckCircle className="mr-2 h-4 w-4" />
                    Accept Goal
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={(e) => {
                    e.stopPropagation();
                    onRespond(goal, false);
                  }}>
                    <XCircle className="mr-2 h-4 w-4" />
                    Decline Goal
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                </>
              )}

              {/* Supervisor: Score Goal for completed supervisee goals */}
              {isSuperviseeGoal && goal.status === "COMPLETED" && onScoreGoal && (
                <>
                  <DropdownMenuItem onClick={(e) => {
                    e.stopPropagation();
                    onScoreGoal(goal);
                  }}>
                    <Award className="mr-2 h-4 w-4" />
                    Score Goal
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                </>
              )}

              {/* Edit and delete options for supervisee goals (supervisor can edit assigned goals) */}
              {isSuperviseeGoal && !goal.frozen && (
                <>
                  <DropdownMenuItem onClick={(e) => {
                    e.stopPropagation();
                    onEdit(goal);
                  }}>
                    <Edit className="mr-2 h-4 w-4" />
                    Edit Goal
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={(e) => {
                    e.stopPropagation();
                    onDelete(goal);
                  }} className="text-red-600">
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete Goal
                  </DropdownMenuItem>
                </>
              )}

              {/* Edit and progress options for own goals */}
              {canEdit && !goal.frozen && !isSuperviseeGoal && (
                <>
                  <DropdownMenuItem onClick={(e) => {
                    e.stopPropagation();
                    onEdit(goal);
                  }}>
                    <Edit className="mr-2 h-4 w-4" />
                    Edit Goal
                  </DropdownMenuItem>

                  {isActive && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={(e) => {
                        e.stopPropagation();
                        onUpdateProgress(goal);
                      }}>
                        <Target className="mr-2 h-4 w-4" />
                        Update Progress
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={(e) => {
                        e.stopPropagation();
                        onRequestChange(goal);
                      }}>
                        Request Change
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={(e) => {
                        e.stopPropagation();
                        onStatusChange(goal, "MARK_COMPLETE");
                      }}>
                        <CheckCircle className="mr-2 h-4 w-4" />
                        Mark as Complete
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={(e) => {
                        e.stopPropagation();
                        onStatusChange(goal, "DISCARDED");
                      }}>
                        Discard Goal
                      </DropdownMenuItem>
                    </>
                  )}

                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={(e) => {
                    e.stopPropagation();
                    onDelete(goal);
                  }} className="text-red-600">
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete Goal
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="flex flex-wrap items-center gap-1 mt-1">
          <GoalStatusBadge status={goal.status} />
          <GoalTypeBadge type={goal.type} />
          {goal.frozen && (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded border border-slate-300 text-slate-500 bg-slate-50">
              <Lock className="h-2.5 w-2.5" />Frozen
            </span>
          )}
          {goal.quarter && goal.year && goal.type === "QUARTERLY" && (
            <span className="text-[11px] text-muted-foreground border border-border px-1.5 py-0.5 rounded">
              {goal.quarter} {goal.year}
            </span>
          )}
          {goal.scope === "DEPARTMENTAL" && goal.organization_name && (
            <span className="text-[11px] text-muted-foreground border border-border px-1.5 py-0.5 rounded truncate max-w-[120px]">
              {goal.organization_name}
            </span>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="space-y-2 flex-1 flex flex-col pt-0 px-4 pb-4">
        {goal.description && (
          <div className="text-xs text-gray-600 line-clamp-2 break-words" 
               dangerouslySetInnerHTML={{ __html: goal.description }} />
        )}
        
        {goal.tags && goal.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {goal.tags.slice(0, 2).map((tag) => (
              <Badge
                key={tag.id}
                variant="outline"
                className="text-xs px-1.5 py-0 max-w-[100px]"
                style={{
                  borderColor: tag.color,
                  color: tag.color,
                  backgroundColor: `${tag.color}15`
                }}
              >
                <span className="truncate">{tag.name}</span>
              </Badge>
            ))}
            {goal.tags.length > 2 && (
              <Badge variant="outline" className="text-xs px-1.5 py-0">
                +{goal.tags.length - 2}
              </Badge>
            )}
          </div>
        )}
        
        {(goal.start_date || goal.end_date) && (
          <div className="flex items-center gap-2 text-xs text-gray-500 pt-1.5 border-t">
            {goal.start_date && (
              <div className="flex items-center gap-1 flex-1 min-w-0">
                <Clock className="h-3 w-3 flex-shrink-0" />
                <span className="truncate">{new Date(goal.start_date).toLocaleDateString()}</span>
              </div>
            )}
            {goal.end_date && (
              <div className="flex items-center gap-1 flex-1 min-w-0">
                <Calendar className="h-3 w-3 flex-shrink-0" />
                <span className="truncate text-right">Due: {new Date(goal.end_date).toLocaleDateString()}</span>
              </div>
            )}
          </div>
        )}

        {goal.owner_name && isSuperviseeGoal && (
          <div className="flex items-center gap-2 pt-2 mt-auto border-t">
            <Avatar className="h-5 w-5 flex-shrink-0">
              <AvatarFallback className="text-[9px] bg-muted text-muted-foreground font-medium">
                {goal.owner_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-gray-900 truncate">{goal.owner_name}</p>
            </div>
            {goal.supervisor_score != null ? (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 whitespace-nowrap flex-shrink-0">
                Score: {goal.supervisor_score}/5
              </span>
            ) : goal.status === "COMPLETED" ? (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 whitespace-nowrap flex-shrink-0">
                Not scored
              </span>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function OrganizationalGoalForm({ goal, isOpen, onClose, onSubmit, canCreateYearly = false, canCreateQuarterly = false, canCreateDepartmental = false, organizations = [], isDepartmentalOnly = false, userOrganization = null, userScope = null }) {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1
  const currentQuarter = Math.ceil(currentMonth / 3)

  
  const availableTypes = useMemo(() => {
    const types = []
    if (isDepartmentalOnly) {
     
      if (canCreateDepartmental) types.push({ value: "DEPARTMENTAL", label: "Departmental" })
    } else {
       
      if (canCreateYearly) types.push({ value: "COMPANY_WIDE", label: "Company-wide" })
      
    }
    return types
  }, [isDepartmentalOnly, canCreateDepartmental, canCreateYearly, canCreateQuarterly])

   
  const scopedOrganizations = useMemo(() => {
    if (!organizations || organizations.length === 0) return []

    // If user has global scope, show all departments and directorates
    if (userScope === 'global') {
      const filtered = organizations.filter(org =>
        org.level === 'DEPARTMENT' ||
        org.level === 'DIRECTORATE' ||
        org.level === 'department' ||
        org.level === 'directorate'
      )
      return filtered.length > 0 ? filtered : organizations.filter(org =>
        org.level !== 'GLOBAL' && org.level !== 'global'
      )
    }

    // Otherwise, only show user's own organization if it's a department or directorate
    if (userOrganization) {
      const userOrg = organizations.find(org => org.id === userOrganization)
      if (userOrg && (
        userOrg.level === 'DEPARTMENT' ||
        userOrg.level === 'DIRECTORATE' ||
        userOrg.level === 'department' ||
        userOrg.level === 'directorate'
      )) {
        return [userOrg]
      }
    }

    // Fallback: if user has departmental goal creation permission, show all valid organizations
    if (canCreateDepartmental) {
      return organizations.filter(org =>
        org.level === 'DEPARTMENT' ||
        org.level === 'DIRECTORATE' ||
        org.level === 'department' ||
        org.level === 'directorate'
      )
    }

    return []
  }, [organizations, userOrganization, userScope, canCreateDepartmental])

  // Auto-set organization_id for departmental goals based on user's scope
  const defaultOrgId = useMemo(() => {
    if (isDepartmentalOnly && scopedOrganizations.length === 1) {
      return scopedOrganizations[0].id
    }
    return ""
  }, [isDepartmentalOnly, scopedOrganizations])

  const [formData, setFormData] = useState({
    title: "",
    description: "",
    scope: availableTypes[0]?.value || (isDepartmentalOnly ? "DEPARTMENTAL" : "COMPANY_WIDE"),
    type: "QUARTERLY",  // Time period: YEARLY or QUARTERLY
    kpis: [],
    difficulty_level: 3,
    start_date: "",
    end_date: "",
    quarter: `Q${currentQuarter}`,
    year: currentYear,
    organization_id: defaultOrgId,
    parent_goal_id: "",
    tag_ids: [],
  })

  const { data: goals = [] } = useGoals()
  const { data: tags = [] } = useGoalTags()

  // Update form data when goal changes
  useEffect(() => {
    if (goal) {
      setFormData({
        title: goal.title || "",
        description: goal.description || "",
        scope: goal.scope || availableTypes[0]?.value || (isDepartmentalOnly ? "DEPARTMENTAL" : "COMPANY_WIDE"),
        type: goal.type || "QUARTERLY",
        kpis: Array.isArray(goal.kpis)
          ? goal.kpis.map(k => typeof k === 'string'
              ? { id: Date.now().toString(), description: k, target_value: null, target_unit: null }
              : k)
          : [],
        difficulty_level: goal.difficulty_level || 3,
        start_date: goal.start_date || "",
        end_date: goal.end_date || "",
        quarter: goal.quarter || `Q${currentQuarter}`,
        year: goal.year || currentYear,
        organization_id: goal.organization_id || defaultOrgId,
        parent_goal_id: goal.parent_goal_id || "",
        tag_ids: goal.tags?.map(t => t.id) || [],
      })
    } else {
      setFormData({
        title: "",
        description: "",
        scope: availableTypes[0]?.value || (isDepartmentalOnly ? "DEPARTMENTAL" : "COMPANY_WIDE"),
        type: "QUARTERLY",
        kpis: [],
        difficulty_level: 3,
        start_date: "",
        end_date: "",
        quarter: `Q${currentQuarter}`,
        year: currentYear,
        organization_id: defaultOrgId,
        parent_goal_id: "",
        tag_ids: [],
      })
    }
  }, [goal, currentQuarter, currentYear, availableTypes, isDepartmentalOnly, defaultOrgId])

  const handleSubmit = (e) => {
    e.preventDefault()
    const submitData = {
      ...formData,
      start_date: formData.start_date || null,
      end_date: formData.end_date || null,
      parent_goal_id: formData.parent_goal_id || null,
    }

    // Only include organization_id for DEPARTMENTAL goals
    if (formData.scope === "DEPARTMENTAL") {
      submitData.organization_id = formData.organization_id
    } else {
      delete submitData.organization_id
    }

    // Don't send quarter/year for YEARLY goals
    if (formData.type === "YEARLY") {
      delete submitData.quarter
      delete submitData.year
    }

    if (Array.isArray(submitData.kpis)) {
      submitData.kpis = submitData.kpis
        .map(k => typeof k === 'string'
          ? { id: Date.now().toString(), description: k, target_value: null, target_unit: null }
          : { ...k, target_value: k.target_value != null ? parseFloat(k.target_value) : null }
        )
        .filter(k => k.description?.trim())
    }

    onSubmit(submitData)
    onClose()
  }

  // Potential parents: Company-wide goals for departmental goals
  const potentialParents = goals.filter((g) => {
    if (formData.scope === "DEPARTMENTAL") {
      // Departmental goals can have company-wide (YEARLY/QUARTERLY) parents
      return g.scope === "COMPANY_WIDE" && g.status === "ACTIVE"
    }
    // Company-wide goals don't have parents
    return false
  })

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{goal ? "Edit Organizational Goal" : "Create Organizational Goal"}</DialogTitle>
            <DialogDescription>
              Create a company-wide or departmental goal
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-6 py-4">
            {/* Goal Scope Selection */}
            {availableTypes.length > 1 && !goal && (
              <div className="grid gap-2">
                <Label htmlFor="scope">Goal Scope <span className="text-red-500">*</span></Label>
                <Select
                  value={formData.scope}
                  onValueChange={(value) => setFormData({ ...formData, scope: value, organization_id: "", parent_goal_id: "" })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {availableTypes.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Organization Selector (for DEPARTMENTAL goals only) */}
            {formData.scope === "DEPARTMENTAL" && (
              <div className="grid gap-2">
                <Label htmlFor="organization">Department/Directorate <span className="text-red-500">*</span></Label>
                {scopedOrganizations.length === 1 ? (
                  <div className="p-3 bg-blue-50 rounded-md border border-blue-200">
                    <p className="text-sm font-medium text-blue-900">
                      {scopedOrganizations[0].name} ({scopedOrganizations[0].level})
                    </p>
                    <p className="text-xs text-blue-700 mt-1">
                      Auto-selected based on your organizational scope
                    </p>
                  </div>
                ) : (
                  <SearchableSelect
                    value={formData.organization_id}
                    onValueChange={(value) => setFormData({ ...formData, organization_id: value })}
                    options={scopedOrganizations.map(org => ({
                      value: org.id,
                      label: `${org.name} (${org.level})`
                    }))}
                    placeholder="Select department or directorate"
                    searchPlaceholder="Search organization..."
                    emptyText="No organizations found."
                    required
                  />
                )}
              </div>
            )}

            <div className="grid gap-2">
              <Label htmlFor="title">Goal Title <span className="text-red-500">*</span></Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Enter goal title"
                required
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <RichTextEditor
                content={formData.description}
                onChange={(html) => setFormData({ ...formData, description: html })}
                placeholder="Describe what this goal aims to achieve..."
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="difficulty">Difficulty Level</Label>
              <Select
                value={formData.difficulty_level.toString()}
                onValueChange={(value) => setFormData({ ...formData, difficulty_level: parseInt(value) })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 - Very Easy</SelectItem>
                  <SelectItem value="2">2 - Easy</SelectItem>
                  <SelectItem value="3">3 - Medium</SelectItem>
                  <SelectItem value="4">4 - Hard</SelectItem>
                  <SelectItem value="5">5 - Very Hard</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label>KPIs (Key Performance Indicators)</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setFormData({ ...formData, kpis: [...formData.kpis, { id: Date.now().toString(), description: "", target_value: null, target_unit: null }] })}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  Add KPI
                </Button>
              </div>
              <div className="space-y-2">
                {formData.kpis.length === 0 && (
                  <p className="text-sm text-gray-500 italic">No KPIs added yet. Click &ldquo;Add KPI&rdquo; to add one.</p>
                )}
                {formData.kpis.map((kpi, index) => (
                  <div key={typeof kpi === 'object' ? kpi.id : index} className="border border-gray-200 rounded-md p-3 space-y-2 bg-gray-50">
                    <div className="flex items-start gap-2">
                      <div className="flex-1 space-y-2">
                        <Input
                          value={typeof kpi === 'string' ? kpi : (kpi.description || '')}
                          onChange={(e) => {
                            const newKpis = [...formData.kpis]
                            newKpis[index] = typeof kpi === 'string'
                              ? { id: Date.now().toString(), description: e.target.value, target_value: null, target_unit: null }
                              : { ...kpi, description: e.target.value }
                            setFormData({ ...formData, kpis: newKpis })
                          }}
                          placeholder={`KPI #${index + 1} description`}
                        />
                        <div className="grid grid-cols-2 gap-2">
                          <Input
                            type="number"
                            value={typeof kpi === 'string' ? '' : (kpi.target_value ?? '')}
                            onChange={(e) => {
                              const newKpis = [...formData.kpis]
                              const base = typeof kpi === 'string' ? { id: Date.now().toString(), description: kpi, target_unit: null } : kpi
                              newKpis[index] = { ...base, target_value: e.target.value ? parseFloat(e.target.value) : null }
                              setFormData({ ...formData, kpis: newKpis })
                            }}
                            placeholder="Target value (e.g. 30)"
                          />
                          <Select
                            value={typeof kpi === 'string' ? 'none' : (kpi.target_unit || 'none')}
                            onValueChange={(val) => {
                              const newKpis = [...formData.kpis]
                              const base = typeof kpi === 'string' ? { id: Date.now().toString(), description: kpi, target_value: null } : kpi
                              newKpis[index] = { ...base, target_unit: val === 'none' ? null : val }
                              setFormData({ ...formData, kpis: newKpis })
                            }}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Unit" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">None</SelectItem>
                              <SelectItem value="%">%</SelectItem>
                              <SelectItem value="count">count</SelectItem>
                              <SelectItem value="NGN">NGN</SelectItem>
                              <SelectItem value="days">days</SelectItem>
                              <SelectItem value="hours">hours</SelectItem>
                              <SelectItem value="score">score</SelectItem>
                              <SelectItem value="km">km</SelectItem>
                              <SelectItem value="units">units</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="mt-0.5"
                        onClick={() => {
                          const newKpis = formData.kpis.filter((_, i) => i !== index)
                          setFormData({ ...formData, kpis: newKpis })
                        }}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="tags">Tags (Optional)</Label>
              <Select
                value={formData.tag_ids.length > 0 ? "multi" : "none"}
                onValueChange={() => {}}
              >
                <SelectTrigger>
                  <SelectValue>
                    {formData.tag_ids.length > 0
                      ? `${formData.tag_ids.length} tag(s) selected`
                      : "Select tags..."}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <div className="p-2 space-y-2">
                    {tags.map((tag) => (
                      <div key={tag.id} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id={`tag-${tag.id}`}
                          checked={formData.tag_ids.includes(tag.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setFormData({
                                ...formData,
                                tag_ids: [...formData.tag_ids, tag.id]
                              })
                            } else {
                              setFormData({
                                ...formData,
                                tag_ids: formData.tag_ids.filter(id => id !== tag.id)
                              })
                            }
                          }}
                          className="h-4 w-4 cursor-pointer"
                        />
                        <label
                          htmlFor={`tag-${tag.id}`}
                          className="flex items-center gap-2 cursor-pointer flex-1"
                        >
                          <div
                            className="w-3 h-3 rounded"
                            style={{ backgroundColor: tag.color }}
                          />
                          <span className="text-sm">{tag.name}</span>
                        </label>
                      </div>
                    ))}
                    {tags.length === 0 && (
                      <p className="text-sm text-gray-500">No tags available. Create tags in the Goals Management page.</p>
                    )}
                  </div>
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="type">Time Period <span className="text-red-500">*</span></Label>
              <Select
                value={formData.type}
                onValueChange={(value) => setFormData({
                  ...formData,
                  type: value,
                  // Clear quarter and year when switching to YEARLY
                  quarter: value === "YEARLY" ? "" : formData.quarter || `Q${currentQuarter}`,
                  year: value === "YEARLY" ? "" : formData.year || currentYear
                })}
                disabled={!!goal}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="min-w-[200px]">
                  <SelectItem value="YEARLY" className="py-3">Yearly</SelectItem>
                  <SelectItem value="QUARTERLY" className="py-3">Quarterly</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {formData.type === "QUARTERLY" && (
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="quarter">Quarter <span className="text-red-500">*</span></Label>
                  <Select
                    value={formData.quarter}
                    onValueChange={(value) => setFormData({ ...formData, quarter: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="min-w-[180px]">
                      <SelectItem value="Q1" className="py-3">Q1 (Jan-Mar)</SelectItem>
                      <SelectItem value="Q2" className="py-3">Q2 (Apr-Jun)</SelectItem>
                      <SelectItem value="Q3" className="py-3">Q3 (Jul-Sep)</SelectItem>
                      <SelectItem value="Q4" className="py-3">Q4 (Oct-Dec)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="year">Year <span className="text-red-500">*</span></Label>
                  <Input
                    id="year"
                    type="number"
                    min={currentYear - 1}
                    max={currentYear + 5}
                    value={formData.year}
                    onChange={(e) => setFormData({ ...formData, year: parseInt(e.target.value) })}
                    required
                  />
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="start_date">Start Date (Optional)</Label>
                <Input
                  id="start_date"
                  type="date"
                  value={formData.start_date}
                  onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="end_date">End Date (Optional)</Label>
                <Input
                  id="end_date"
                  type="date"
                  value={formData.end_date}
                  onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                />
              </div>
            </div>

            {potentialParents.length > 0 && (
              <div className="grid gap-2">
                <Label htmlFor="parent">Link to Parent Goal (Optional)</Label>
                <SearchableSelect
                  value={formData.parent_goal_id || "none"}
                  onValueChange={(value) => setFormData({ ...formData, parent_goal_id: value === "none" ? "" : value })}
                  options={[
                    { value: "none", label: "No parent goal" },
                    ...potentialParents.map((g) => ({
                      value: g.id,
                      label: `${g.title} (${g.type}${g.quarter ? ` - ${g.quarter} ${g.year}` : ''})`
                    }))
                  ]}
                  placeholder="Select parent goal"
                  searchPlaceholder="Search parent goals..."
                  emptyText="No parent goals found."
                />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">{goal ? "Update Goal" : "Create Goal"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function IndividualGoalForm({ goal, isOpen, onClose, onSubmit, canCreateForSupervisee = false, supervisees = [] }) {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1
  const currentQuarter = Math.ceil(currentMonth / 3)

  const [formData, setFormData] = useState({
    title: "",
    description: "",
    type: "QUARTERLY",  // Time period: YEARLY or QUARTERLY
    kpis: [],
    difficulty_level: 3,
    start_date: "",
    end_date: "",
    quarter: `Q${currentQuarter}`,
    year: currentYear,
    supervisee_id: "",
    tag_ids: [],
  })

  const [createForSupervisee, setCreateForSupervisee] = useState(false)

  const { data: goals = [] } = useGoals()
  const { data: tags = [] } = useGoalTags()

  // Update form data when goal changes
  useEffect(() => {
    if (goal) {
      setFormData({
        title: goal.title || "",
        description: goal.description || "",
        type: goal.type || "QUARTERLY",
        kpis: Array.isArray(goal.kpis)
          ? goal.kpis.map(k => typeof k === 'string'
              ? { id: Date.now().toString(), description: k, target_value: null, target_unit: null }
              : k)
          : [],
        difficulty_level: goal.difficulty_level || 3,
        start_date: goal.start_date || "",
        end_date: goal.end_date || "",
        quarter: goal.quarter || `Q${currentQuarter}`,
        year: goal.year || currentYear,
        supervisee_id: goal.owner_id || "",
        tag_ids: goal.tags?.map(t => t.id) || [],
      })
      setCreateForSupervisee(!!goal.owner_id && goal.owner_id !== goal.created_by)
    } else {
      setFormData({
        title: "",
        description: "",
        type: "QUARTERLY",
        kpis: [],
        difficulty_level: 3,
        start_date: "",
        end_date: "",
        quarter: `Q${currentQuarter}`,
        year: currentYear,
        supervisee_id: "",
        tag_ids: [],
      })
      setCreateForSupervisee(false)
    }
  }, [goal, currentQuarter, currentYear])

  const handleSubmit = (e) => {
    e.preventDefault()
    const submitData = {
      ...formData,
      scope: "INDIVIDUAL",  // Individual goals always have INDIVIDUAL scope
      start_date: formData.start_date || null,
      end_date: formData.end_date || null,
      supervisee_id: createForSupervisee ? formData.supervisee_id : undefined
    }

    // Don't send quarter/year for YEARLY goals
    if (formData.type === "YEARLY") {
      delete submitData.quarter
      delete submitData.year
    }

    if (Array.isArray(submitData.kpis)) {
      submitData.kpis = submitData.kpis
        .map(k => typeof k === 'string'
          ? { id: Date.now().toString(), description: k, target_value: null, target_unit: null }
          : { ...k, target_value: k.target_value != null ? parseFloat(k.target_value) : null }
        )
        .filter(k => k.description?.trim())
    }

    onSubmit(submitData)
    onClose()
  }

  const potentialParents = goals.filter((g) =>
    g.scope === "DEPARTMENTAL" && g.status === "ACTIVE"
  )

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{goal ? "Edit Goal" : "Create Individual Goal"}</DialogTitle>
            <DialogDescription>
              Create a personal performance goal for the quarter
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-6 py-4">
            {canCreateForSupervisee && !goal && (
              <div className="flex items-center gap-2 p-4 bg-blue-50 rounded-lg">
                <input
                  type="checkbox"
                  id="createForSupervisee"
                  checked={createForSupervisee}
                  onChange={(e) => setCreateForSupervisee(e.target.checked)}
                  className="h-4 w-4"
                />
                <Label htmlFor="createForSupervisee" className="cursor-pointer">
                  Create this goal for a supervisee
                </Label>
              </div>
            )}

            {createForSupervisee && (
              <div className="grid gap-2">
                <Label htmlFor="supervisee">Select Supervisee <span className="text-red-500">*</span></Label>
                <Select
                  value={formData.supervisee_id}
                  onValueChange={(value) => setFormData({ ...formData, supervisee_id: value })}
                  required={createForSupervisee}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select supervisee" />
                  </SelectTrigger>
                  <SelectContent>
                    {supervisees.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name} - {s.job_title || 'No title'}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formData.supervisee_id && (
                  <div className="flex items-center gap-2 mt-2 p-2 bg-blue-50 rounded-md border border-blue-200">
                    <User className="h-4 w-4 text-blue-600" />
                    <span className="text-sm text-blue-900">
                      Assigning to: <span className="font-semibold">
                        {supervisees.find(s => s.id === formData.supervisee_id)?.name}
                      </span>
                    </span>
                  </div>
                )}
              </div>
            )}

            <div className="grid gap-2">
              <Label htmlFor="title">Goal Title <span className="text-red-500">*</span></Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Enter goal title"
                required
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <RichTextEditor
                content={formData.description}
                onChange={(html) => setFormData({ ...formData, description: html })}
                placeholder="Describe what this goal aims to achieve..."
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="difficulty">Difficulty Level</Label>
              <Select
                value={formData.difficulty_level.toString()}
                onValueChange={(value) => setFormData({ ...formData, difficulty_level: parseInt(value) })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 - Very Easy</SelectItem>
                  <SelectItem value="2">2 - Easy</SelectItem>
                  <SelectItem value="3">3 - Medium</SelectItem>
                  <SelectItem value="4">4 - Hard</SelectItem>
                  <SelectItem value="5">5 - Very Hard</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label>KPIs (Key Performance Indicators)</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setFormData({ ...formData, kpis: [...formData.kpis, { id: Date.now().toString(), description: "", target_value: null, target_unit: null }] })}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  Add KPI
                </Button>
              </div>
              <div className="space-y-2">
                {formData.kpis.length === 0 && (
                  <p className="text-sm text-gray-500 italic">No KPIs added yet. Click &ldquo;Add KPI&rdquo; to add one.</p>
                )}
                {formData.kpis.map((kpi, index) => (
                  <div key={typeof kpi === 'object' ? kpi.id : index} className="border border-gray-200 rounded-md p-3 space-y-2 bg-gray-50">
                    <div className="flex items-start gap-2">
                      <div className="flex-1 space-y-2">
                        <Input
                          value={typeof kpi === 'string' ? kpi : (kpi.description || '')}
                          onChange={(e) => {
                            const newKpis = [...formData.kpis]
                            newKpis[index] = typeof kpi === 'string'
                              ? { id: Date.now().toString(), description: e.target.value, target_value: null, target_unit: null }
                              : { ...kpi, description: e.target.value }
                            setFormData({ ...formData, kpis: newKpis })
                          }}
                          placeholder={`KPI #${index + 1} description`}
                        />
                        <div className="grid grid-cols-2 gap-2">
                          <Input
                            type="number"
                            value={typeof kpi === 'string' ? '' : (kpi.target_value ?? '')}
                            onChange={(e) => {
                              const newKpis = [...formData.kpis]
                              const base = typeof kpi === 'string' ? { id: Date.now().toString(), description: kpi, target_unit: null } : kpi
                              newKpis[index] = { ...base, target_value: e.target.value ? parseFloat(e.target.value) : null }
                              setFormData({ ...formData, kpis: newKpis })
                            }}
                            placeholder="Target value (e.g. 30)"
                          />
                          <Select
                            value={typeof kpi === 'string' ? 'none' : (kpi.target_unit || 'none')}
                            onValueChange={(val) => {
                              const newKpis = [...formData.kpis]
                              const base = typeof kpi === 'string' ? { id: Date.now().toString(), description: kpi, target_value: null } : kpi
                              newKpis[index] = { ...base, target_unit: val === 'none' ? null : val }
                              setFormData({ ...formData, kpis: newKpis })
                            }}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Unit" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">None</SelectItem>
                              <SelectItem value="%">%</SelectItem>
                              <SelectItem value="count">count</SelectItem>
                              <SelectItem value="NGN">NGN</SelectItem>
                              <SelectItem value="days">days</SelectItem>
                              <SelectItem value="hours">hours</SelectItem>
                              <SelectItem value="score">score</SelectItem>
                              <SelectItem value="km">km</SelectItem>
                              <SelectItem value="units">units</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="mt-0.5"
                        onClick={() => {
                          const newKpis = formData.kpis.filter((_, i) => i !== index)
                          setFormData({ ...formData, kpis: newKpis })
                        }}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="tags">Tags (Optional)</Label>
              <Select
                value={formData.tag_ids.length > 0 ? "multi" : "none"}
                onValueChange={() => {}}
              >
                <SelectTrigger>
                  <SelectValue>
                    {formData.tag_ids.length > 0
                      ? `${formData.tag_ids.length} tag(s) selected`
                      : "Select tags..."}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <div className="p-2 space-y-2">
                    {tags.map((tag) => (
                      <div key={tag.id} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id={`ind-tag-${tag.id}`}
                          checked={formData.tag_ids.includes(tag.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setFormData({
                                ...formData,
                                tag_ids: [...formData.tag_ids, tag.id]
                              })
                            } else {
                              setFormData({
                                ...formData,
                                tag_ids: formData.tag_ids.filter(id => id !== tag.id)
                              })
                            }
                          }}
                          className="h-4 w-4 cursor-pointer"
                        />
                        <label
                          htmlFor={`ind-tag-${tag.id}`}
                          className="flex items-center gap-2 cursor-pointer flex-1"
                        >
                          <div
                            className="w-3 h-3 rounded"
                            style={{ backgroundColor: tag.color }}
                          />
                          <span className="text-sm">{tag.name}</span>
                        </label>
                      </div>
                    ))}
                    {tags.length === 0 && (
                      <p className="text-sm text-gray-500">No tags available. Create tags in the Goals Management page.</p>
                    )}
                  </div>
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="type">Time Period <span className="text-red-500">*</span></Label>
              <Select
                value={formData.type}
                onValueChange={(value) => setFormData({
                  ...formData,
                  type: value,
                  // Clear quarter and year when switching to YEARLY
                  quarter: value === "YEARLY" ? "" : formData.quarter || `Q${currentQuarter}`,
                  year: value === "YEARLY" ? "" : formData.year || currentYear
                })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="min-w-[200px]">
                  <SelectItem value="YEARLY" className="py-3">Yearly</SelectItem>
                  <SelectItem value="QUARTERLY" className="py-3">Quarterly</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {formData.type === "QUARTERLY" && (
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="quarter">Quarter <span className="text-red-500">*</span></Label>
                <Select
                  value={formData.quarter}
                  onValueChange={(value) => setFormData({ ...formData, quarter: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="min-w-[180px]">
                    <SelectItem value="Q1" className="py-3">Q1 (Jan-Mar)</SelectItem>
                    <SelectItem value="Q2" className="py-3">Q2 (Apr-Jun)</SelectItem>
                    <SelectItem value="Q3" className="py-3">Q3 (Jul-Sep)</SelectItem>
                    <SelectItem value="Q4" className="py-3">Q4 (Oct-Dec)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="year">Year <span className="text-red-500">*</span></Label>
                <Input
                  id="year"
                  type="number"
                  min={currentYear - 1}
                  max={currentYear + 5}
                  value={formData.year}
                  onChange={(e) => setFormData({ ...formData, year: parseInt(e.target.value) })}
                  required
                />
              </div>
            </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="start_date">Start Date (Optional)</Label>
                <Input
                  id="start_date"
                  type="date"
                  value={formData.start_date}
                  onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="end_date">End Date (Optional)</Label>
                <Input
                  id="end_date"
                  type="date"
                  value={formData.end_date}
                  onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                />
              </div>
            </div>

            {potentialParents.length > 0 && (
              <div className="grid gap-2">
                <Label htmlFor="parent">Link to Organizational Goal (Optional)</Label>
                <SearchableSelect
                  value={formData.parent_goal_id || "none"}
                  onValueChange={(value) => setFormData({ ...formData, parent_goal_id: value === "none" ? "" : value })}
                  options={[
                    { value: "none", label: "No parent goal" },
                    ...potentialParents.map((g) => ({
                      value: g.id,
                      label: `${g.title} (${g.type}${g.quarter ? ` - ${g.quarter} ${g.year}` : ''})`
                    }))
                  ]}
                  placeholder="Select parent goal"
                  searchPlaceholder="Search organizational goals..."
                  emptyText="No parent goals found."
                />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">{goal ? "Update Goal" : "Create Goal"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ProgressUpdateDialog({ goal, isOpen, onClose, onSubmit, initialPercentage }) {
  const [formData, setFormData] = useState({
    new_percentage: goal?.progress_percentage || 0,
    report: "",
    employee_comment: "",
    kpiActuals: {},
  })
  const [kpiError, setKpiError] = useState("")

  useEffect(() => {
    if (goal) {
      const init = {}
      goal.kpis?.forEach(k => {
        init[k.id] = { actual_value: k.actual_value ?? '' }
      })
      setFormData({
        new_percentage: initialPercentage ?? goal.progress_percentage ?? 0,
        report: "",
        employee_comment: "",
        kpiActuals: init,
      })
      setKpiError("")
    }
  }, [goal?.id])

  const hasKpis = (goal?.kpis?.length ?? 0) > 0
  const is100 = formData.new_percentage === 100
  const isMarkComplete = !!goal?._targetStatus

  const calcKpiScore = (kpi) => {
    const actual = parseFloat(formData.kpiActuals[kpi.id]?.actual_value)
    if (isNaN(actual) || !kpi.target_value) return null
    return (Math.min(actual / kpi.target_value, 1) * 5).toFixed(2)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (is100 && hasKpis) {
      const unfilled = goal.kpis.filter(k => {
        const val = formData.kpiActuals[k.id]?.actual_value
        return val === '' || val === null || val === undefined
      })
      if (unfilled.length > 0) {
        setKpiError(`Please enter actual values for all ${unfilled.length} KPI(s) before marking as complete.`)
        return
      }
    }
    setKpiError("")
    const payload = {
      new_percentage: formData.new_percentage,
      report: formData.report,
    }
    if (is100) {
      payload.employee_comment = formData.employee_comment || null
      if (hasKpis) {
        payload.kpi_assessments = (goal?.kpis || []).map(k => ({
          id: k.id,
          actual_value: parseFloat(formData.kpiActuals[k.id]?.actual_value) || 0,
        }))
      }
    }
    onSubmit(payload)
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[560px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Update Goal Progress</DialogTitle>
            <DialogDescription>Update progress for &quot;{goal?.title}&quot;</DialogDescription>
          </DialogHeader>
          <div className="grid gap-5 py-4">
            <div className="grid gap-3">
              <Label htmlFor="percentage">Progress Percentage</Label>
              <div className="space-y-2">
                <Input
                  id="percentage"
                  type="number"
                  min="0"
                  max="100"
                  value={formData.new_percentage}
                  onChange={(e) => !isMarkComplete && setFormData({ ...formData, new_percentage: parseInt(e.target.value) || 0 })}
                  readOnly={isMarkComplete}
                  className={isMarkComplete ? "bg-muted cursor-not-allowed" : ""}
                  required
                />
                <Progress value={formData.new_percentage} className="h-2" />
              </div>
            </div>

            <div className="grid gap-3">
              <Label htmlFor="report">Progress Report <span className="text-red-500">*</span></Label>
              <Textarea
                id="report"
                value={formData.report}
                onChange={(e) => setFormData({ ...formData, report: e.target.value })}
                placeholder="Explain the progress made..."
                rows={3}
                required
              />
            </div>

            {is100 && (
              <div className="grid gap-3">
                <Label htmlFor="emp_comment">Your Comment (optional)</Label>
                <Textarea
                  id="emp_comment"
                  value={formData.employee_comment}
                  onChange={(e) => setFormData({ ...formData, employee_comment: e.target.value })}
                  placeholder="Add any notes or context about completing this goal..."
                  rows={2}
                />
              </div>
            )}

            {is100 && hasKpis && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 border-t pt-3">
                  <Target className="h-4 w-4 text-muted-foreground" />
                  <Label className="text-sm font-semibold">KPI Actuals</Label>
                  <span className="text-xs text-muted-foreground">(required to complete)</span>
                </div>
                {goal.kpis.map(kpi => {
                  const score = calcKpiScore(kpi)
                  return (
                    <div key={kpi.id} className="rounded-md border bg-muted/30 p-3 space-y-2">
                      <p className="text-xs font-medium text-foreground">{kpi.description}</p>
                      {kpi.target_value != null && (
                        <p className="text-[11px] text-muted-foreground">
                          Target: {kpi.target_value}{kpi.target_unit ? ` ${kpi.target_unit}` : ''}
                        </p>
                      )}
                      <Input
                          type="number"
                          step="any"
                          value={formData.kpiActuals[kpi.id]?.actual_value ?? ''}
                          onChange={(e) => {
                            setKpiError("")
                            setFormData(prev => ({
                              ...prev,
                              kpiActuals: {
                                ...prev.kpiActuals,
                                [kpi.id]: { ...prev.kpiActuals[kpi.id], actual_value: e.target.value }
                              }
                            }))
                          }}
                          placeholder="Actual value"
                          className="h-8 text-sm"
                        />
                    </div>
                  )
                })}
                {kpiError && (
                  <p className="text-sm text-red-600 flex items-center gap-1">
                    <AlertCircle className="h-3.5 w-3.5" />
                    {kpiError}
                  </p>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit">
              {is100 ? "Mark as Complete" : "Update Progress"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AssessGoalDialog({ goal, isOpen, onClose, onSubmit }) {
  const [kpiActuals, setKpiActuals] = useState({})

  useEffect(() => {
    if (goal?.kpis) {
      const init = {}
      goal.kpis.forEach(k => {
        init[k.id] = { actual_value: k.actual_value ?? '', achieved: k.achieved ?? false }
      })
      setKpiActuals(init)
    }
  }, [goal?.id])

  const handleSubmit = (e) => {
    e.preventDefault()
    const kpi_assessments = (goal?.kpis || []).map(k => ({
      id: k.id,
      actual_value: parseFloat(kpiActuals[k.id]?.actual_value) || 0,
      achieved: kpiActuals[k.id]?.achieved ?? false,
    }))
    onSubmit({ kpi_assessments })
    onClose()
  }

  const calcScore = (kpi) => {
    const actual = parseFloat(kpiActuals[kpi.id]?.actual_value)
    if (isNaN(actual) || !kpi.target_value) return null
    return (Math.min(actual / kpi.target_value, 1) * 5).toFixed(2)
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Assess KPIs</DialogTitle>
            <DialogDescription>
              Enter actual values for &quot;{goal?.title}&quot;
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {(goal?.kpis || []).map((kpi) => (
              <div key={kpi.id} className="border border-gray-200 rounded-md p-3 space-y-2 bg-gray-50">
                <p className="text-sm font-medium">{kpi.description}</p>
                {kpi.target_value != null && (
                  <p className="text-xs text-gray-500">
                    Target: {kpi.target_value}{kpi.target_unit ? ` ${kpi.target_unit}` : ''}
                  </p>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label className="text-xs">Actual Value</Label>
                    <Input
                      type="number"
                      value={kpiActuals[kpi.id]?.actual_value ?? ''}
                      onChange={e => setKpiActuals(prev => ({
                        ...prev,
                        [kpi.id]: { ...prev[kpi.id], actual_value: e.target.value }
                      }))}
                      placeholder="Enter actual value"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Score /5</Label>
                    <div className="h-9 flex items-center px-3 rounded-md border border-gray-200 bg-white text-sm font-semibold text-gray-800">
                      {calcScore(kpi) ?? '—'}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id={`achieved-${kpi.id}`}
                    checked={kpiActuals[kpi.id]?.achieved ?? false}
                    onChange={e => setKpiActuals(prev => ({
                      ...prev,
                      [kpi.id]: { ...prev[kpi.id], achieved: e.target.checked }
                    }))}
                    className="h-4 w-4"
                  />
                  <Label htmlFor={`achieved-${kpi.id}`} className="text-xs cursor-pointer">Mark KPI as achieved</Label>
                </div>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit">Submit Assessment</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ScoreGoalDialog({ goal, isOpen, onClose, onSubmit }) {
  const [formData, setFormData] = useState({ supervisor_score: "", supervisor_comment: "", achieved_override: null })

  useEffect(() => {
    if (goal) {
      setFormData({
        supervisor_score: goal.supervisor_score ?? "",
        supervisor_comment: goal.supervisor_comment ?? "",
        achieved_override: goal.achieved ?? null,
      })
    }
  }, [goal?.id])

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit({
      supervisor_score: parseInt(formData.supervisor_score, 10),
      supervisor_comment: formData.supervisor_comment || null,
      achieved_override: formData.achieved_override,
    })
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Score Goal</DialogTitle>
            <DialogDescription>Score &quot;{goal?.title}&quot; for {goal?.owner_name}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {goal?.kpis?.length > 0 && (
              <div className="rounded-md border bg-muted/30 p-3 space-y-2">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">KPI Actuals (Employee Filled)</p>
                {goal.kpis.map(kpi => {
                  const fmtTarget = kpi.target_value != null
                    ? `${kpi.target_value}${kpi.target_unit ? ' ' + kpi.target_unit : ''}`
                    : null
                  const fmtActual = kpi.actual_value != null
                    ? `${kpi.actual_value}${kpi.target_unit ? ' ' + kpi.target_unit : ''}`
                    : '—'
                  return (
                    <div key={kpi.id} className="text-xs py-1.5 border-t border-border/40 first:border-0 first:pt-0 space-y-0.5">
                      <p className="text-foreground font-medium">{kpi.description}</p>
                      <div className="flex gap-4 text-muted-foreground">
                        {fmtTarget && <span>Target: <span className="text-foreground">{fmtTarget}</span></span>}
                        <span>Actual: <span className="text-foreground font-medium">{fmtActual}</span></span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
            {goal?.employee_comment && (
              <div className="space-y-1">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{goal.owner_name ? `${goal.owner_name}'s Comment` : "Employee Comment"}</p>
                <p className="text-sm text-foreground">{goal.employee_comment}</p>
              </div>
            )}
            <div className="grid gap-2">
              <Label htmlFor="sup_score">Your Score (0–5) <span className="text-red-500">*</span></Label>
              <Input
                id="sup_score"
                type="number"
                min="0"
                max="5"
                step="1"
                value={formData.supervisor_score}
                onChange={(e) => setFormData(prev => ({ ...prev, supervisor_score: e.target.value }))}
                placeholder="0, 1, 2, 3, 4, or 5"
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="sup_comment">Your Comment</Label>
              <Textarea
                id="sup_comment"
                value={formData.supervisor_comment}
                onChange={(e) => setFormData(prev => ({ ...prev, supervisor_comment: e.target.value }))}
                placeholder="Add feedback or remarks for the employee..."
                rows={3}
              />
            </div>
          </div>
          <div className="rounded-md border p-3 space-y-2 bg-muted/30">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Achievement Override</p>
              <p className="text-xs text-muted-foreground">The system auto-marks goals as achieved. You can override this below.</p>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, achieved_override: true }))}
                  className={`px-3 py-1 rounded text-xs font-medium border transition-colors ${formData.achieved_override === true ? 'bg-emerald-700 text-white border-emerald-700' : 'border-border text-muted-foreground hover:bg-muted'}`}
                >
                  Mark as Achieved
                </button>
                <button
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, achieved_override: false }))}
                  className={`px-3 py-1 rounded text-xs font-medium border transition-colors ${formData.achieved_override === false ? 'bg-gray-700 text-white border-gray-700' : 'border-border text-muted-foreground hover:bg-muted'}`}
                >
                  Not Achieved
                </button>
                <button
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, achieved_override: null }))}
                  className={`px-3 py-1 rounded text-xs font-medium border transition-colors ${formData.achieved_override === null ? 'bg-blue-600 text-white border-blue-600' : 'border-border text-muted-foreground hover:bg-muted'}`}
                >
                  Auto (no override)
                </button>
              </div>
            </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit">Submit Score</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function GoalApprovalDialog({ goal, isOpen, onClose, onSubmit }) {
  const [rejectionReason, setRejectionReason] = useState("")
  const [showReject, setShowReject] = useState(false)

  const handleApprove = () => {
    onSubmit({ approved: true, rejection_reason: "" })
    setShowReject(false)
    setRejectionReason("")
  }

  const handleRejectConfirm = () => {
    onSubmit({ approved: false, rejection_reason: rejectionReason })
    setShowReject(false)
    setRejectionReason("")
  }

  const handleClose = () => {
    setShowReject(false)
    setRejectionReason("")
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[620px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Review Goal</DialogTitle>
          <DialogDescription>
            Review the full goal details before approving or rejecting
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Title & meta */}
          <div className="space-y-1.5">
            <h3 className="font-semibold text-base leading-snug">{goal?.title}</h3>
            <div className="flex flex-wrap items-center gap-2">
              {goal?.owner_name && (
                <span className="text-sm text-muted-foreground">
                  By: <span className="font-medium text-foreground">{goal.owner_name}</span>
                </span>
              )}
              {goal?.quarter && goal?.year && (
                <Badge variant="outline" className="text-xs">{goal.quarter} {goal.year}</Badge>
              )}
              {goal?.type && (
                <Badge variant="outline" className="text-xs">{goal.type}</Badge>
              )}
            </div>
          </div>

          {/* Description */}
          {goal?.description && (
            <div className="rounded-md border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground font-medium mb-1">Description</p>
              <div
                className="text-sm text-foreground prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: goal.description }}
              />
            </div>
          )}

          {/* Dates & details */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            {goal?.start_date && (
              <div>
                <p className="text-xs text-muted-foreground">Start Date</p>
                <p className="font-medium">{new Date(goal.start_date).toLocaleDateString()}</p>
              </div>
            )}
            {goal?.end_date && (
              <div>
                <p className="text-xs text-muted-foreground">End Date</p>
                <p className="font-medium">{new Date(goal.end_date).toLocaleDateString()}</p>
              </div>
            )}
            {goal?.difficulty_level && (
              <div>
                <p className="text-xs text-muted-foreground">Difficulty</p>
                <p className="font-medium">Level {goal.difficulty_level} / 5</p>
              </div>
            )}
            {goal?.evaluation_method && (
              <div>
                <p className="text-xs text-muted-foreground">Evaluation Method</p>
                <p className="font-medium">{goal.evaluation_method}</p>
              </div>
            )}
          </div>

          {/* KPIs */}
          {goal?.kpis?.length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground font-medium mb-2">
                KPIs ({goal.kpis.length})
              </p>
              <div className="space-y-2">
                {goal.kpis.map((kpi, i) => (
                  <div key={kpi.id || i} className="rounded-md border bg-muted/20 p-2.5">
                    <p className="text-sm font-medium">{kpi.description}</p>
                    {kpi.target_value != null && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Target: {kpi.target_value}{kpi.target_unit ? ` ${kpi.target_unit}` : ''}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Rejection reason input */}
          {showReject && (
            <div className="space-y-2 border-t pt-3">
              <Label htmlFor="rejection_reason" className="text-sm font-medium">
                Rejection Reason <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="rejection_reason"
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="Explain why this goal is being rejected..."
                rows={3}
              />
              <div className="flex gap-2 justify-end">
                <Button variant="outline" size="sm" onClick={() => setShowReject(false)}>
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleRejectConfirm}
                  disabled={!rejectionReason.trim()}
                >
                  Confirm Reject
                </Button>
              </div>
            </div>
          )}
        </div>

        {!showReject && (
          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="button" variant="destructive" onClick={() => setShowReject(true)}>
              <XCircle className="h-4 w-4 mr-2" />
              Reject
            </Button>
            <Button type="button" onClick={handleApprove}>
              <CheckCircle className="h-4 w-4 mr-2" />
              Approve
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  )
}

function ChangeRequestDialog({ goal, isOpen, onClose, onSubmit }) {
  const [changeRequest, setChangeRequest] = useState("")

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit(changeRequest)
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Request Goal Change</DialogTitle>
            <DialogDescription>
              Request modifications to &quot;{goal?.title}&quot;
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="change_request">
                What changes do you need? <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="change_request"
                value={changeRequest}
                onChange={(e) => setChangeRequest(e.target.value)}
                placeholder="Describe the changes you need to this goal..."
                rows={5}
                required
              />
              <p className="text-xs text-gray-500">
                Your supervisor will review this request and may approve changes to your goal
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">Submit Request</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function RespondToGoalDialog({ goal, isOpen, onClose, onSubmit }) {
  const [formData, setFormData] = useState({
    accepted: true,
    response_message: ""
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit(formData.accepted, formData.response_message)
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Respond to Assigned Goal</DialogTitle>
            <DialogDescription>
              Your supervisor assigned you this goal
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="p-4 bg-gray-50 rounded-lg space-y-2">
              <h3 className="font-semibold">{goal?.title}</h3>
              {goal?.description && (
                <p className="text-sm text-gray-600">{goal.description}</p>
              )}
              <div className="flex items-center gap-2 text-sm">
                <Badge>{goal?.quarter} {goal?.year}</Badge>
              </div>
            </div>

            <div className="flex gap-2">
              <Button
                type="button"
                variant={formData.accepted ? "default" : "outline"}
                className="flex-1"
                onClick={() => setFormData({ accepted: true, response_message: "" })}
              >
                <CheckCircle className="h-4 w-4 mr-2" />
                Accept
              </Button>
              <Button
                type="button"
                variant={!formData.accepted ? "destructive" : "outline"}
                className="flex-1"
                onClick={() => setFormData({ ...formData, accepted: false })}
              >
                <XCircle className="h-4 w-4 mr-2" />
                Decline
              </Button>
            </div>

            {!formData.accepted && (
              <div className="grid gap-2">
                <Label htmlFor="response_message">
                  Reason for declining <span className="text-red-500">*</span>
                </Label>
                <Textarea
                  id="response_message"
                  value={formData.response_message}
                  onChange={(e) => setFormData({ ...formData, response_message: e.target.value })}
                  placeholder="Explain why you're declining this goal..."
                  rows={4}
                  required={!formData.accepted}
                />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant={formData.accepted ? "default" : "destructive"}>
              Confirm
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function GoalDetailDialog({ goal, isOpen, onClose, parentGoal, supervisor, supervisee, canApprove, onApprove, currentUserId }) {
  if (!goal) return null

  const isPendingApproval = goal.status === "PENDING_APPROVAL"
  const isAssignedByOther = goal.created_by !== goal.owner_id
  const isOwnersGoal = goal.created_by !== currentUserId && goal.owner_id !== currentUserId

  const handleApprove = () => {
    if (onApprove) {
      onApprove(goal)
      onClose()
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-start justify-between">
            <div className="space-y-2 flex-1">
              <DialogTitle className="text-xl">{goal.title}</DialogTitle>
              <div className="flex items-center gap-2 flex-wrap">
                <GoalStatusBadge status={goal.status} />
                {goal.quarter && goal.year && (
                  <Badge variant="outline">{goal.quarter} {goal.year}</Badge>
                )}
                {goal.frozen && (
                  <Badge className="bg-gray-200 text-gray-800">Frozen</Badge>
                )}
                {goal.scope === "DEPARTMENTAL" && goal.organization_name && (
                  <Badge className="bg-orange-100 text-orange-800 border-orange-200">
                    {goal.organization_name}
                  </Badge>
                )}
              </div>
              {/* Show owner name if viewing someone else's goal */}
              {goal.owner_name && isOwnersGoal && (
                <div className="flex items-center gap-1.5 text-sm text-gray-600">
                  <User className="h-3.5 w-3.5" />
                  <span>Goal Owner: {goal.owner_name}</span>
                </div>
              )}
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-6 py-4">

          {/* Tags */}
          {goal.tags && goal.tags.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-semibold text-sm text-gray-700">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {goal.tags.map((tag) => (
                  <Badge
                    key={tag.id}
                    variant="outline"
                    className="text-sm px-3 py-1"
                    style={{ borderColor: tag.color, color: tag.color, backgroundColor: `${tag.color}15` }}
                  >
                    {tag.name}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {goal.description && (
            <div className="space-y-2">
              <h3 className="font-semibold text-sm text-gray-700">Description</h3>
              <div
                className="text-sm text-gray-600 prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: goal.description }}
              />
            </div>
          )}

          {goal.kpis && goal.kpis.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-semibold text-sm text-gray-700">Key Performance Indicators</h3>
              <div className="border border-gray-200 rounded-md overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-gray-500 font-medium">KPI</th>
                      <th className="px-3 py-2 text-center text-gray-500 font-medium w-24">Target</th>
                      <th className="px-3 py-2 text-center text-gray-500 font-medium w-24">Actual</th>
                    </tr>
                  </thead>
                  <tbody>
                    {goal.kpis.map((kpi, ki) => {
                      const desc = typeof kpi === 'string' ? kpi : kpi.description
                      const targetVal = typeof kpi === 'object' ? kpi.target_value : null
                      const targetUnit = typeof kpi === 'object' ? kpi.target_unit : null
                      const actualVal = typeof kpi === 'object' ? kpi.actual_value : null
                      const fmtTarget = targetVal != null ? `${targetVal}${targetUnit ? ' ' + targetUnit : ''}` : '—'
                      const fmtActual = actualVal != null ? `${actualVal}${targetUnit ? ' ' + targetUnit : ''}` : '—'
                      return (
                        <tr key={ki} className="border-t border-gray-100">
                          <td className="px-3 py-2 text-gray-700">{desc}</td>
                          <td className="px-3 py-2 text-center text-gray-500">{fmtTarget}</td>
                          <td className="px-3 py-2 text-center text-gray-700 font-medium">{fmtActual}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Employee Comment */}
          {goal.employee_comment && (
            <div className="space-y-1">
              <h3 className="font-semibold text-sm text-gray-700">Employee Comment</h3>
              <p className="text-sm text-gray-600">{goal.employee_comment}</p>
            </div>
          )}

          {/* Supervisor Score & Comment */}
          {goal.supervisor_score != null && (
            <div className="space-y-2 p-3 rounded-md border border-gray-200 bg-gray-50">
              <h3 className="font-semibold text-sm text-gray-700">Supervisor Assessment</h3>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Score:</span>
                <span className="text-sm font-bold text-gray-900">{goal.supervisor_score} / 5</span>
              </div>
              {goal.supervisor_comment && (
                <p className="text-sm text-gray-600">{goal.supervisor_comment}</p>
              )}
            </div>
          )}

          {/* Progress */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm text-gray-700">Progress</h3>
              <span className="text-sm font-semibold">{goal.progress_percentage || 0}%</span>
            </div>
            <Progress value={goal.progress_percentage || 0} className="h-2" />
          </div>

          {/* Dates */}
          {(goal.start_date || goal.end_date) && (
            <div className="grid grid-cols-2 gap-4">
              {goal.start_date && (
                <div className="space-y-1">
                  <h3 className="font-semibold text-sm text-gray-700">Start Date</h3>
                  <p className="text-sm text-gray-600">
                    {new Date(goal.start_date).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </p>
                </div>
              )}
              {goal.end_date && (
                <div className="space-y-1">
                  <h3 className="font-semibold text-sm text-gray-700">End Date</h3>
                  <p className="text-sm text-gray-600">
                    {new Date(goal.end_date).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Parent Goal */}
          {parentGoal && (
            <div className="space-y-2 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h3 className="font-semibold text-sm text-blue-900">Linked to Organizational Goal</h3>
              <div className="space-y-1">
                <p className="text-sm font-medium text-blue-800">{parentGoal.title}</p>
                <div className="flex items-center gap-2">
                  <GoalStatusBadge status={parentGoal.status} />
                </div>
              </div>
            </div>
          )}

          {/* Supervisee Info (for supervisors viewing supervisee goals) */}
          {supervisee && (
            <div className="space-y-2 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h3 className="font-semibold text-sm text-blue-900">Supervisee</h3>
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-blue-200 flex items-center justify-center">
                  <User className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-blue-900">{supervisee.name}</p>
                  <p className="text-xs text-blue-700">{supervisee.job_title || 'Supervisee'}</p>
                  {supervisee.email && (
                    <p className="text-xs text-blue-600">{supervisee.email}</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Supervisor Info (for employees viewing their own goals) */}
          {supervisor && !supervisee && (
            <div className="space-y-2 p-4 bg-gray-50 rounded-lg border border-gray-200">
              <h3 className="font-semibold text-sm text-gray-700">Reporting Supervisor</h3>
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-gray-300 flex items-center justify-center">
                  <User className="h-5 w-5 text-gray-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">{supervisor.name}</p>
                  <p className="text-xs text-gray-600">{supervisor.job_title || 'Supervisor'}</p>
                  {supervisor.email && (
                    <p className="text-xs text-gray-500">{supervisor.email}</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Rejection Reason */}
          {goal.status === 'REJECTED' && goal.rejection_reason && (
            <div className="space-y-2 p-4 bg-red-50 rounded-lg border border-red-200">
              <h3 className="font-semibold text-sm text-red-900">Rejection Reason</h3>
              <p className="text-sm text-red-800">{goal.rejection_reason}</p>
            </div>
          )}

          {/* Achievement Date */}
          {goal.status === 'ACHIEVED' && goal.achieved_at && (
            <div className="space-y-1">
              <h3 className="font-semibold text-sm text-gray-700">Achieved On</h3>
              <p className="text-sm text-gray-600">
                {new Date(goal.achieved_at).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                })}
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          {canApprove && isPendingApproval && !isAssignedByOther && (
            <Button type="button" onClick={handleApprove} className="mr-auto">
              <CheckCircle className="mr-2 h-4 w-4" />
              Approve Goal
            </Button>
          )}
          <Button type="button" variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function GoalsPage() {
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [isProgressOpen, setIsProgressOpen] = useState(false)
  const [isApprovalOpen, setIsApprovalOpen] = useState(false)
  const [isChangeRequestOpen, setIsChangeRequestOpen] = useState(false)
  const [isRespondOpen, setIsRespondOpen] = useState(false)
  const [isDetailOpen, setIsDetailOpen] = useState(false)
  const [isAssessOpen, setIsAssessOpen] = useState(false)
  const [isScoreOpen, setIsScoreOpen] = useState(false)
  const [editingGoal, setEditingGoal] = useState(null)
  const [updatingGoal, setUpdatingGoal] = useState(null)
  const [approvingGoal, setApprovingGoal] = useState(null)
  const [changingGoal, setChangingGoal] = useState(null)
  const [respondingGoal, setRespondingGoal] = useState(null)
  const [detailGoal, setDetailGoal] = useState(null)
  const [assessingGoal, setAssessingGoal] = useState(null)
  const [scoringGoal, setScoringGoal] = useState(null)
  const [activeTab, setActiveTab] = useState("organizational")
  const [searchTerm, setSearchTerm] = useState("")
  const [yearFilter, setYearFilter] = useState("all")
  const [quarterFilter, setQuarterFilter] = useState("all")
  const [superviseeFilter, setSuperviseeFilter] = useState("all")
  const [scoringFilter, setScoringFilter] = useState("all")
  const [departmentFilter, setDepartmentFilter] = useState("all")
  const [tagFilter, setTagFilter] = useState("all")

  const { user } = useAuth()
  const canEditGoals = usePermission("goal_edit")
  const canUpdateProgress = usePermission("goal_progress_update")
  const canApproveGoals = usePermission("goal_approve")
  const canCreateYearlyGoals = usePermission("goal_create_yearly")
  const canCreateQuarterlyGoals = usePermission("goal_create_quarterly")
  const canCreateDepartmentalGoals = usePermission("goal_create_departmental")

  // Fetch goals based on active tab with appropriate scope parameter
  const getScopeForTab = (tab) => {
    switch (tab) {
      case "organizational":
        return "COMPANY_WIDE"
      case "departmental":
        return "DEPARTMENTAL"
      case "my":
        return "INDIVIDUAL"
      default:
        return null // No scope filter for other tabs
    }
  }

  const currentScope = getScopeForTab(activeTab)
  const scopeParams = currentScope ? { scope: currentScope } : {}

  const { data: goals = [], isLoading } = useGoals(scopeParams)
  const [teamTabVisited, setTeamTabVisited] = useState(false)
  const { data: superviseeGoals = [] } = useSuperviseeGoals({ enabled: teamTabVisited })
  const { data: usersData, isLoading: isLoadingUsers } = useUsers()
  const users = usersData?.users || []
  const { data: organizations = [] } = useOrganizations()
  const { data: tags = [] } = useGoalTags()

  // Enable supervisee goals fetch on first visit to team tab
  useEffect(() => {
    if (activeTab === "team" && !teamTabVisited) {
      setTeamTabVisited(true)
    }
  }, [activeTab, teamTabVisited])

  const createMutation = useCreateGoal()
  const createForSuperviseeMutation = useCreateGoalForSupervisee()
  const updateMutation = useUpdateGoal()
  const updateProgressMutation = useUpdateGoalProgress()
  const updateStatusMutation = useUpdateGoalStatus()
  const deleteMutation = useDeleteGoal()
  const approvalMutation = useApproveGoal()
  const respondMutation = useRespondToGoal()
  const requestChangeMutation = useRequestGoalChange()
  const assessMutation = useAssessGoal()
  const scoreMutation = useSupervisorScore()

  // Get supervisees for supervisor view via dedicated endpoint
  const { data: supervisees = [] } = useMySupervisees()

  // Consider user a supervisor if they have supervisees OR have supervisee goals
  const isSupervisor = supervisees.length > 0 || superviseeGoals.length > 0

  // Get unique years from goals for filter
  const availableYears = useMemo(() => {
    const years = new Set()
    goals.forEach(g => {
      if (g.year) years.add(g.year.toString())
    })
    return Array.from(years).sort((a, b) => b - a)
  }, [goals])

  const yearOptions = [
    { value: "all", label: "All Years" },
    ...availableYears.map(year => ({ value: year, label: year }))
  ]

  const quarterOptions = [
    { value: "all", label: "All Quarters" },
    { value: "Q1", label: "Q1 (Jan-Mar)" },
    { value: "Q2", label: "Q2 (Apr-Jun)" },
    { value: "Q3", label: "Q3 (Jul-Sep)" },
    { value: "Q4", label: "Q4 (Oct-Dec)" }
  ]

  const superviseeOptions = [
    { value: "all", label: "All Supervisees" },
    ...supervisees.map(s => ({ value: s.id, label: s.name }))
  ]

  const tagOptions = useMemo(() => {
    return [
      { value: "all", label: "All Tags" },
      ...tags.map(tag => ({ value: tag.id, label: tag.name }))
    ]
  }, [tags])

  const departmentOptions = useMemo(() => {
    const deptOrgs = organizations.filter(org =>
      org.level === 'DEPARTMENT' || org.level === 'department' ||
      org.level === 'DIRECTORATE' || org.level === 'directorate'
    )
    return [
      { value: "all", label: "All Departments" },
      ...deptOrgs.map(org => ({ value: org.id, label: org.name }))
    ]
  }, [organizations])

  // Helper function for tag filtering
  const applyTagFilter = (filtered) => {
    if (tagFilter !== "all") {
      filtered = filtered.filter(g =>
        g.tags && g.tags.some(tag => tag.id === tagFilter)
      )
    }
    return filtered
  }


// Apply common filters (year, quarter, search, tags)
// Note: Scope filtering is now handled by the API based on activeTab
const filteredBase = useMemo(() => {
  let list = [...goals];

  // Year Filter
  if (yearFilter !== "all") {
    list = list.filter(g => g.year?.toString() === yearFilter);
  }

  // Quarter Filter
  if (quarterFilter !== "all") {
    list = list.filter(g => g.quarter === quarterFilter);
  }

  // Search Filter
  if (searchTerm) {
    const term = searchTerm.toLowerCase();
    list = list.filter(g =>
      g.title?.toLowerCase().includes(term) ||
      g.description?.toLowerCase().includes(term)
    );
  }

  // Tag Filter
  return applyTagFilter(list);
}, [goals, yearFilter, quarterFilter, searchTerm, tagFilter]);

// For organizational tab - goals are already filtered by API as COMPANY_WIDE
const organizationalGoals = useMemo(() => {
  return filteredBase;
}, [filteredBase]);

// For departmental tab - goals are already filtered by API as DEPARTMENTAL
// Apply additional department filter if specific department is selected
const departmentalGoals = useMemo(() => {
  if (departmentFilter !== "all") {
    return filteredBase.filter(g => g.organization_id === departmentFilter);
  }
  return filteredBase;
}, [filteredBase, departmentFilter]);

// For my goals tab - goals are already filtered by API as INDIVIDUAL
// No additional filtering needed since API handles scope
const myIndividualGoals = useMemo(() => {
  return filteredBase;
}, [filteredBase]);

  // Filtered supervisee goals
  const filteredSuperviseeGoals = useMemo(() => {
    let filtered = superviseeGoals

    if (yearFilter !== "all") {
      filtered = filtered.filter(g => g.year?.toString() === yearFilter)
    }

    if (quarterFilter !== "all") {
      filtered = filtered.filter(g => g.quarter === quarterFilter)
    }

    if (searchTerm) {
      filtered = filtered.filter(g =>
        g.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        g.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        g.owner_name?.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }

    if (superviseeFilter !== "all") {
      filtered = filtered.filter(g => g.owner_id === superviseeFilter)
    }

    if (scoringFilter === "scored") {
      filtered = filtered.filter(g => g.supervisor_score != null)
    } else if (scoringFilter === "not_scored") {
      filtered = filtered.filter(g => g.supervisor_score == null && g.status === "COMPLETED")
    }

    return filtered
  }, [superviseeGoals, yearFilter, quarterFilter, searchTerm, superviseeFilter, scoringFilter])

  // Handlers
  const handleCreate = (data) => {
    if (data.supervisee_id) {
      // Create goal for supervisee using the special endpoint
      createForSuperviseeMutation.mutate({
        ...data,
        parent_goal_id: data.parent_goal_id === "" ? null : data.parent_goal_id,
      }, {
        onSuccess: () => {
          setIsFormOpen(false)
          setEditingGoal(null)
        }
      })
    } else {
      createMutation.mutate({
        ...data,
        parent_goal_id: data.parent_goal_id === "" ? null : data.parent_goal_id,
      }, {
        onSuccess: () => {
          setIsFormOpen(false)
          setEditingGoal(null)
        }
      })
    }
  }

  const handleUpdate = (data) => {
    if (editingGoal) {
      updateMutation.mutate({ id: editingGoal.id, ...data })
    }
  }

  const handleUpdateProgress = (data) => {
    if (updatingGoal) {
      const goalId = updatingGoal.id
      const targetStatus = updatingGoal._targetStatus
      updateProgressMutation.mutate({ id: goalId, ...data })
    }
  }

  const handleAssess = (data) => {
    if (assessingGoal) {
      assessMutation.mutate({ id: assessingGoal.id, ...data })
    }
  }

  const handleApprove = (data) => {
    if (approvingGoal) {
      approvalMutation.mutate({ id: approvingGoal.id, ...data }, {
        onSuccess: () => {
          setIsApprovalOpen(false)
          setApprovingGoal(null)
        }
      })
    }
  }

  const handleRequestChange = (changeRequest) => {
    if (changingGoal) {
      requestChangeMutation.mutate({
        id: changingGoal.id,
        changeRequest
      }, {
        onSuccess: () => {
          setIsChangeRequestOpen(false)
          setChangingGoal(null)
        }
      })
    }
  }

  const handleRespond = (accepted, message) => {
    if (respondingGoal) {
      respondMutation.mutate({
        id: respondingGoal.id,
        accepted,
        response_message: message
      }, {
        onSuccess: () => {
          setIsRespondOpen(false)
          setRespondingGoal(null)
        }
      })
    }
  }

  const handleEdit = (goal) => {
    setEditingGoal(goal)
    setIsFormOpen(true)
  }

  const handleUpdateProgressDialog = (goal) => {
    setUpdatingGoal(goal)
    setIsProgressOpen(true)
  }

  const handleApprovalDialog = (goal) => {
    setApprovingGoal(goal)
    setIsApprovalOpen(true)
  }

  const handleChangeRequestDialog = (goal) => {
    setChangingGoal(goal)
    setIsChangeRequestOpen(true)
  }

  const handleRespondDialog = (goal, accepted) => {
    setRespondingGoal({ ...goal, initialAccepted: accepted })
    setIsRespondOpen(true)
  }

  const handleStatusChange = (goal, status) => {
    if (status === "ASSESS") {
      setAssessingGoal(goal)
      setIsAssessOpen(true)
      return
    }
    // "Mark as Complete" — open progress dialog at 100%
    if (status === "MARK_COMPLETE") {
      // Pre-fill progress at 100 then open progress dialog
      setUpdatingGoal({ ...goal, _targetStatus: status })
      setIsProgressOpen(true)
      return
    }
    updateStatusMutation.mutate({ id: goal.id, status })
  }

  const handleScoreGoal = (goal) => {
    setScoringGoal(goal)
    setIsScoreOpen(true)
  }

  const handleScoreSubmit = (data) => {
    if (scoringGoal) {
      scoreMutation.mutate({ id: scoringGoal.id, ...data })
    }
  }

  const handleDelete = (goal) => {
    if (confirm(`Delete "${goal.title}"?`)) {
      deleteMutation.mutate(goal.id)
    }
  }

  const handleViewDetails = (goal) => {
    setDetailGoal(goal)
    setIsDetailOpen(true)
  }

  // Get parent goal and related user info for detail view
  const parentGoalForDetail = detailGoal?.parent_goal_id
    ? goals.find(g => g.id === detailGoal.parent_goal_id)
    : null

  // Get supervisee information when supervisor is viewing supervisee's goal
  const superviseeForDetail = useMemo(() => {
    if (!detailGoal) return null

    // If I'm viewing someone else's goal and I'm their supervisor, show their info
    const goalOwner = users.find(u => u.id === detailGoal.owner_id)
    if (goalOwner && goalOwner.supervisor_id === user?.user_id) {
      return goalOwner
    }

    return null
  }, [detailGoal, users, user?.user_id])

  // Get supervisor information when viewing my own goal
  const supervisorForDetail = useMemo(() => {
    if (!detailGoal || superviseeForDetail) return null // Don't show supervisor if showing supervisee

    // If this is my goal, show my supervisor
    if (detailGoal.owner_id === user?.user_id && user?.supervisor_id) {
      return users.find(u => u.id === user.supervisor_id)
    }

    return null
  }, [detailGoal, users, user?.user_id, user?.supervisor_id, superviseeForDetail])

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b border-gray-200 pb-6">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold text-gray-900">Goals</h1>
            <p className="text-base text-gray-600">
              Track organizational goals and manage your personal performance goals
            </p>
          </div>
        </div>
      </div>

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full max-w-4xl grid-cols-4">
          <TabsTrigger value="organizational" className="flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Organizational
          </TabsTrigger>
          <TabsTrigger value="departmental" className="flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Departmental
          </TabsTrigger>
          <TabsTrigger value="my" className="flex items-center gap-2">
            <User className="h-4 w-4" />
            My Goals
          </TabsTrigger>
          <TabsTrigger value="team" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Supervisee Goals
          </TabsTrigger>
        </TabsList>

        {/* Organizational Goals Tab */}
        <TabsContent value="organizational" className="space-y-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Company-wide yearly and quarterly goals
            </p>
            {(canCreateYearlyGoals || canCreateQuarterlyGoals) && (
              <Button onClick={() => {
                setEditingGoal(null)
                setIsFormOpen(true)
              }}>
                <Plus className="mr-2 h-4 w-4" />
                Create Organizational Goal
              </Button>
            )}
          </div>

          {/* Search and Filters */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="relative flex-1 min-w-[250px]">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search goals..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>

            <SearchableSelect
              value={yearFilter}
              onValueChange={setYearFilter}
              options={yearOptions}
              placeholder="Filter by year"
              searchPlaceholder="Search year..."
              emptyText="No years found."
              className="w-[160px]"
            />

            <SearchableSelect
              value={quarterFilter}
              onValueChange={setQuarterFilter}
              options={quarterOptions}
              placeholder="Filter by quarter"
              searchPlaceholder="Search quarter..."
              emptyText="No quarters found."
              className="w-[180px]"
            />

            <SearchableSelect
              value={tagFilter}
              onValueChange={setTagFilter}
              options={[
                { value: "all", label: "All Tags" },
                ...tags.map(tag => ({ value: tag.id, label: tag.name }))
              ]}
              placeholder="Filter by tag"
              searchPlaceholder="Search tags..."
              emptyText="No tags found."
              className="w-[160px]"
            />

            {(searchTerm || yearFilter !== "all" || quarterFilter !== "all" || tagFilter !== "all") && (
              <Button
                variant="outline"
                onClick={() => {
                  setSearchTerm("")
                  setYearFilter("all")
                  setQuarterFilter("all")
                  setTagFilter("all")
                }}
                className="whitespace-nowrap"
              >
                <X className="mr-2 h-4 w-4" />
                Clear Filters
              </Button>
            )}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Company Goals</CardTitle>
              <CardDescription>
                View yearly and quarterly organizational goals
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {[...Array(6)].map((_, i) => (
                    <Skeleton key={i} className="h-48" />
                  ))}
                </div>
              ) : organizationalGoals.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {organizationalGoals.map((goal) => (
                    <GoalCard
                      key={goal.id}
                      goal={goal}
                      onEdit={handleEdit}
                      onDelete={handleDelete}
                      onUpdateProgress={handleUpdateProgressDialog}
                      onStatusChange={handleStatusChange}
                      onViewDetails={handleViewDetails}
                      canEdit={false}
                      currentUserId={user?.user_id}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Target className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">No organizational goals</h3>
                  <p className="text-gray-600">
                    {(canCreateYearlyGoals || canCreateQuarterlyGoals)
                      ? "Create your first organizational goal to get started"
                      : "Check back later for company-wide goals"}
                  </p>
                  {(canCreateYearlyGoals || canCreateQuarterlyGoals) && (
                    <Button onClick={() => {
                      setEditingGoal(null)
                      setIsFormOpen(true)
                    }} className="mt-4">
                      <Plus className="mr-2 h-4 w-4" />
                      Create Organizational Goal
                    </Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Departmental Goals Tab */}
        <TabsContent value="departmental" className="space-y-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Department and directorate-specific goals
            </p>
            {(canCreateDepartmentalGoals) && (
              <Button onClick={() => {
                setEditingGoal(null)
                setIsFormOpen(true)
              }}>
                <Plus className="mr-2 h-4 w-4" />
                Create Departmental Goal
              </Button>
            )}
          </div>

          {/* Search and Filters */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="relative flex-1 min-w-[250px]">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search goals..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>

            <SearchableSelect
              value={departmentFilter}
              onValueChange={setDepartmentFilter}
              options={departmentOptions}
              placeholder="Filter by department"
              searchPlaceholder="Search department..."
              emptyText="No departments found."
              className="w-[200px]"
            />

            <SearchableSelect
              value={yearFilter}
              onValueChange={setYearFilter}
              options={yearOptions}
              placeholder="Filter by year"
              searchPlaceholder="Search year..."
              emptyText="No years found."
              className="w-[160px]"
            />

            <SearchableSelect
              value={quarterFilter}
              onValueChange={setQuarterFilter}
              options={quarterOptions}
              placeholder="Filter by quarter"
              searchPlaceholder="Search quarter..."
              emptyText="No quarters found."
              className="w-[180px]"
            />

            <SearchableSelect
              value={tagFilter}
              onValueChange={setTagFilter}
              options={[
                { value: "all", label: "All Tags" },
                ...tags.map(tag => ({ value: tag.id, label: tag.name }))
              ]}
              placeholder="Filter by tag"
              searchPlaceholder="Search tags..."
              emptyText="No tags found."
              className="w-[160px]"
            />

            {(searchTerm || departmentFilter !== "all" || yearFilter !== "all" || quarterFilter !== "all" || tagFilter !== "all") && (
              <Button
                variant="outline"
                onClick={() => {
                  setSearchTerm("")
                  setDepartmentFilter("all")
                  setYearFilter("all")
                  setQuarterFilter("all")
                  setTagFilter("all")
                }}
                className="whitespace-nowrap"
              >
                <X className="mr-2 h-4 w-4" />
                Clear Filters
              </Button>
            )}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Departmental Goals</CardTitle>
              <CardDescription>
                View department and directorate-specific goals
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {[...Array(6)].map((_, i) => (
                    <Skeleton key={i} className="h-48" />
                  ))}
                </div>
              ) : departmentalGoals.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {departmentalGoals.map((goal) => (
                    <GoalCard
                      key={goal.id}
                      goal={goal}
                      onEdit={handleEdit}
                      onDelete={handleDelete}
                      onUpdateProgress={handleUpdateProgressDialog}
                      onStatusChange={handleStatusChange}
                      onViewDetails={handleViewDetails}
                      canEdit={canEditGoals}
                      currentUserId={user?.user_id}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Building2 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">No departmental goals</h3>
                  <p className="text-gray-600">
                    {canCreateDepartmentalGoals
                      ? "Create your first departmental goal to get started"
                      : "Check back later for departmental goals"}
                  </p>
                  {canCreateDepartmentalGoals && (
                    <Button onClick={() => {
                      setEditingGoal(null)
                      setIsFormOpen(true)
                    }} className="mt-4">
                      <Plus className="mr-2 h-4 w-4" />
                      Create Departmental Goal
                    </Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* My Individual Goals Tab */}
        <TabsContent value="my" className="space-y-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Create and manage your personal performance goals
            </p>
            <Button onClick={() => setIsFormOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Goal
            </Button>
          </div>

          {/* Search and Filters */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="relative flex-1 min-w-[250px]">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search goals..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>

            <SearchableSelect
              value={yearFilter}
              onValueChange={setYearFilter}
              options={yearOptions}
              placeholder="Filter by year"
              searchPlaceholder="Search year..."
              emptyText="No years found."
              className="w-[160px]"
            />

            <SearchableSelect
              value={quarterFilter}
              onValueChange={setQuarterFilter}
              options={quarterOptions}
              placeholder="Filter by quarter"
              searchPlaceholder="Search quarter..."
              emptyText="No quarters found."
              className="w-[180px]"
            />

            <SearchableSelect
              value={tagFilter}
              onValueChange={setTagFilter}
              options={[
                { value: "all", label: "All Tags" },
                ...tags.map(tag => ({ value: tag.id, label: tag.name }))
              ]}
              placeholder="Filter by tag"
              searchPlaceholder="Search tags..."
              emptyText="No tags found."
              className="w-[160px]"
            />

            {(searchTerm || yearFilter !== "all" || quarterFilter !== "all" || tagFilter !== "all") && (
              <Button
                variant="outline"
                onClick={() => {
                  setSearchTerm("")
                  setYearFilter("all")
                  setQuarterFilter("all")
                  setTagFilter("all")
                }}
                className="whitespace-nowrap"
              >
                <X className="mr-2 h-4 w-4" />
                Clear Filters
              </Button>
            )}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>My Individual Goals ({myIndividualGoals.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {myIndividualGoals.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {myIndividualGoals.map((goal) => (
                    <GoalCard
                      key={goal.id}
                      goal={goal}
                      onEdit={handleEdit}
                      onDelete={handleDelete}
                      onUpdateProgress={handleUpdateProgressDialog}
                      onStatusChange={handleStatusChange}
                      onApprove={handleApprovalDialog}
                      onRespond={handleRespondDialog}
                      onRequestChange={handleChangeRequestDialog}
                      onViewDetails={handleViewDetails}
                      canEdit={canEditGoals || goal.created_by === user?.user_id}
                      currentUserId={user?.user_id}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Target className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">No individual goals yet</h3>
                  <p className="text-gray-600 mb-4">Create your first personal goal to get started</p>
                  <Button onClick={() => setIsFormOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Create Goal
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Supervisee Goals Tab */}
        <TabsContent value="team" className="space-y-6">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-600">
                Review and approve your supervisees&apos; goals
              </p>
              <Button onClick={() => setIsFormOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Create Goal for Supervisee
              </Button>
            </div>

            {/* Search and Filters */}
            <div className="flex items-center gap-4 flex-wrap">
              <div className="relative flex-1 min-w-[250px]">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search goals or supervisees..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>

              <SearchableSelect
                value={yearFilter}
                onValueChange={setYearFilter}
                options={yearOptions}
                placeholder="Filter by year"
                searchPlaceholder="Search year..."
                emptyText="No years found."
                className="w-[160px]"
              />

              <SearchableSelect
                value={quarterFilter}
                onValueChange={setQuarterFilter}
                options={quarterOptions}
                placeholder="Filter by quarter"
                searchPlaceholder="Search quarter..."
                emptyText="No quarters found."
                className="w-[180px]"
              />

              <SearchableSelect
                value={superviseeFilter}
                onValueChange={setSuperviseeFilter}
                options={superviseeOptions}
                placeholder="Filter by member"
                searchPlaceholder="Search supervisee..."
                emptyText="No supervisees found."
                className="w-[220px]"
              />

              <SearchableSelect
                value={tagFilter}
                onValueChange={setTagFilter}
                options={[
                  { value: "all", label: "All Tags" },
                  ...tags.map(tag => ({ value: tag.id, label: tag.name }))
                ]}
                placeholder="Filter by tag"
                searchPlaceholder="Search tags..."
                emptyText="No tags found."
                className="w-[160px]"
              />

              <SearchableSelect
                value={scoringFilter}
                onValueChange={setScoringFilter}
                options={[
                  { value: "all", label: "All (Scoring)" },
                  { value: "scored", label: "Scored" },
                  { value: "not_scored", label: "Not Yet Scored" },
                ]}
                placeholder="Filter by scoring"
                className="w-[180px]"
              />

              {(searchTerm || yearFilter !== "all" || quarterFilter !== "all" || superviseeFilter !== "all" || tagFilter !== "all" || scoringFilter !== "all") && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setSearchTerm("")
                    setYearFilter("all")
                    setQuarterFilter("all")
                    setSuperviseeFilter("all")
                    setTagFilter("all")
                    setScoringFilter("all")
                  }}
                  className="whitespace-nowrap"
                >
                  <X className="mr-2 h-4 w-4" />
                  Clear Filters
                </Button>
              )}
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Supervisee Goals ({filteredSuperviseeGoals.length})</CardTitle>
                <CardDescription>
                  {supervisees.length} supervisees
                </CardDescription>
              </CardHeader>
              <CardContent>
                {filteredSuperviseeGoals.length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {filteredSuperviseeGoals.map((goal) => (
                      <GoalCard
                        key={goal.id}
                        goal={goal}
                        onEdit={handleEdit}
                        onDelete={handleDelete}
                        onUpdateProgress={handleUpdateProgressDialog}
                        onStatusChange={handleStatusChange}
                        onApprove={handleApprovalDialog}
                        onScoreGoal={handleScoreGoal}
                        onViewDetails={handleViewDetails}
                        canEdit={canEditGoals}
                        canApprove={canApproveGoals}
                        isSuperviseeGoal={true}
                        currentUserId={user?.user_id}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">No supervisee goals found</h3>
                    <p className="text-gray-600 mb-4">
                      {(searchTerm || yearFilter !== "all" || superviseeFilter !== "all" || scoringFilter !== "all")
                        ? "Try adjusting your filters"
                        : "Create goals for your supervisees or wait for them to create their own"}
                    </p>
                    <Button onClick={() => setIsFormOpen(true)}>
                      <Plus className="mr-2 h-4 w-4" />
                      Create Goal for Supervisee
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
      </Tabs>

      {/* Dialogs */}
      {/* Show OrganizationalGoalForm for organizational/departmental tabs if user has permissions */}
      {(activeTab === "organizational" || activeTab === "departmental") &&
       (canCreateYearlyGoals || canCreateQuarterlyGoals || canCreateDepartmentalGoals) ? (
        <OrganizationalGoalForm
          goal={editingGoal}
          isOpen={isFormOpen}
          onClose={() => {
            setIsFormOpen(false)
            setEditingGoal(null)
          }}
          onSubmit={editingGoal ? handleUpdate : handleCreate}
          canCreateYearly={canCreateYearlyGoals}
          canCreateQuarterly={canCreateQuarterlyGoals}
          canCreateDepartmental={canCreateDepartmentalGoals}
          organizations={organizations}
          isDepartmentalOnly={activeTab === "departmental"}
          userOrganization={user?.organization_id}
          userScope={user?.scope}
        />
      ) : (
        <IndividualGoalForm
          goal={editingGoal}
          isOpen={isFormOpen}
          onClose={() => {
            setIsFormOpen(false)
            setEditingGoal(null)
          }}
          onSubmit={editingGoal ? handleUpdate : handleCreate}
          canCreateForSupervisee={isSupervisor && activeTab === "team"}
          supervisees={supervisees}
        />
      )}

      <ProgressUpdateDialog
        goal={updatingGoal}
        isOpen={isProgressOpen}
        onClose={() => {
          setIsProgressOpen(false)
          setUpdatingGoal(null)
        }}
        onSubmit={handleUpdateProgress}
        initialPercentage={updatingGoal?._targetStatus ? 100 : undefined}
      />

      <GoalApprovalDialog
        goal={approvingGoal}
        isOpen={isApprovalOpen}
        onClose={() => {
          setIsApprovalOpen(false)
          setApprovingGoal(null)
        }}
        onSubmit={handleApprove}
      />

      <ChangeRequestDialog
        goal={changingGoal}
        isOpen={isChangeRequestOpen}
        onClose={() => {
          setIsChangeRequestOpen(false)
          setChangingGoal(null)
        }}
        onSubmit={handleRequestChange}
      />

      <RespondToGoalDialog
        goal={respondingGoal}
        isOpen={isRespondOpen}
        onClose={() => {
          setIsRespondOpen(false)
          setRespondingGoal(null)
        }}
        onSubmit={handleRespond}
      />

      <GoalDetailDialog
        goal={detailGoal}
        isOpen={isDetailOpen}
        onClose={() => {
          setIsDetailOpen(false)
          setDetailGoal(null)
        }}
        parentGoal={parentGoalForDetail}
        supervisor={supervisorForDetail}
        supervisee={superviseeForDetail}
        canApprove={canApproveGoals}
        onApprove={handleApprovalDialog}
        currentUserId={user?.user_id}
      />

      <AssessGoalDialog
        goal={assessingGoal}
        isOpen={isAssessOpen}
        onClose={() => { setIsAssessOpen(false); setAssessingGoal(null) }}
        onSubmit={handleAssess}
      />

      <ScoreGoalDialog
        goal={scoringGoal}
        isOpen={isScoreOpen}
        onClose={() => { setIsScoreOpen(false); setScoringGoal(null) }}
        onSubmit={handleScoreSubmit}
      />
    </div>
  )
}
