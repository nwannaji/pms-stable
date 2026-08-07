'use client'

import { useState, useEffect, useMemo } from "react"
import { Plus, CheckSquare, Calendar, User, Users, MoreHorizontal, Edit, Trash2, Eye, FileText, Clock, Star, Search, Filter, X, Check, ChevronsUpDown, Download } from "lucide-react"
import { SubTaskList } from "@/components/initiatives/SubTaskList"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { FileUpload } from "@/components/ui/file-upload"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
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
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"
import { useAuth, PermissionGuard } from "@/lib/auth-context"
import { RichTextEditor } from "@/components/ui/rich-text-editor"
import {
  useInitiatives,
  useSuperviseeInitiatives,
  useAssignableUsers,
  useHasSupervisees,
  useCreateInitiative,
  useUpdateInitiative,
  useUpdateInitiativeStatus,
  useSubmitInitiative,
  useReviewInitiative,
  useApproveInitiative,
  useAcceptInitiative,
  useStartInitiative,
  useCompleteInitiative,
  useGoals,
  useRequestInitiativeExtension,
  useDeleteInitiative,
  useUsers,
} from "@/lib/react-query"

const statusColors = {
  PENDING_APPROVAL: "bg-yellow-100 text-yellow-800",      // Waiting supervisor approval
  ASSIGNED: "bg-blue-100 text-blue-800",                  // Need to accept
  PENDING: "bg-cyan-100 text-cyan-800",                   // Ready to start
  ONGOING: "bg-green-100 text-green-800",                 // Actively working
  UNDER_REVIEW: "bg-orange-100 text-orange-800",          // Submitted for review
  APPROVED: "bg-emerald-100 text-emerald-800",            // Approved with grade
  REJECTED: "bg-red-100 text-red-800",                    // Rejected
  OVERDUE: "bg-red-100 text-red-800",                     // Past due date
  // Legacy status support for backward compatibility
  pending_approval: "bg-yellow-100 text-yellow-800",
  assigned: "bg-blue-100 text-blue-800",
  pending: "bg-cyan-100 text-cyan-800",
  ongoing: "bg-green-100 text-green-800",
  under_review: "bg-orange-100 text-orange-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-800",
  overdue: "bg-red-100 text-red-800"
}

const typeColors = {
  INDIVIDUAL: "bg-blue-100 text-blue-800",
  GROUP: "bg-purple-100 text-purple-800",
  // Legacy support
  individual: "bg-blue-100 text-blue-800",
  group: "bg-purple-100 text-purple-800"
}

const urgencyColors = {
  LOW: "bg-gray-100 text-gray-800 border-gray-200",
  MEDIUM: "bg-yellow-100 text-yellow-800 border-yellow-200",
  HIGH: "bg-orange-100 text-orange-800 border-orange-200",
  URGENT: "bg-red-100 text-red-800 border-red-200",
  // Legacy support
  low: "bg-gray-100 text-gray-800 border-gray-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  urgent: "bg-red-100 text-red-800 border-red-200"
}

function InitiativeForm({ initiative, isOpen, onClose, onSubmit }) {
  const { user } = useAuth()
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    type: "INDIVIDUAL",
    urgency: "MEDIUM",
    due_date: "",
    assignee_ids: [],
    team_head_id: "",
    goal_id: "none"
  })
  const [createForMyself, setCreateForMyself] = useState(true) // Checkbox state
  const [attachedFiles, setAttachedFiles] = useState([])
  const [goalOpen, setGoalOpen] = useState(false)
  const [assigneeOpen, setAssigneeOpen] = useState(false)
  const [subtasks, setSubtasks] = useState([]) // Subtasks for the initiative
  const [newSubtaskTitle, setNewSubtaskTitle] = useState("")

  const { data: assignableUsers = [] } = useAssignableUsers()
  const { data: goals = [] } = useGoals()

  // Update form data when initiative changes (for editing)
  useEffect(() => {
    if (initiative && isOpen) {
      // Editing mode - prefill with initiative data
      const assigneeIds = initiative.assignments?.map(a => a.user_id) || []
      const isForMyself = assigneeIds.length === 1 && assigneeIds[0] === user?.user_id

      setFormData({
        title: initiative.title || "",
        description: initiative.description || "",
        type: initiative.type || "INDIVIDUAL",
        urgency: initiative.urgency || "MEDIUM",
        due_date: initiative.due_date ? initiative.due_date.split('T')[0] : "",
        assignee_ids: assigneeIds,
        team_head_id: initiative.team_head_id || "",
        goal_id: initiative.goal_id || "none"
      })
      setCreateForMyself(isForMyself)
      setAttachedFiles([])
      setSubtasks([]) // Clear subtasks when editing (they're managed separately)
      setNewSubtaskTitle("")
    } else if (!initiative && isOpen) {
      // Create mode - reset to defaults
      setFormData({
        title: "",
        description: "",
        type: "INDIVIDUAL",
        urgency: "MEDIUM",
        due_date: "",
        assignee_ids: [],
        team_head_id: "",
        goal_id: "none"
      })
      setCreateForMyself(true)
      setAttachedFiles([])
      setSubtasks([])
      setNewSubtaskTitle("")
    }
  }, [initiative, isOpen, user?.user_id])

  // Reset form when closing
  useEffect(() => {
    if (!isOpen) {
      setAttachedFiles([])
      setSubtasks([])
      setNewSubtaskTitle("")
    }
  }, [isOpen])

  // Helper functions for subtasks
  const addSubtask = () => {
    if (newSubtaskTitle.trim()) {
      setSubtasks([...subtasks, { title: newSubtaskTitle.trim(), description: "" }])
      setNewSubtaskTitle("")
    }
  }

  const removeSubtask = (index) => {
    setSubtasks(subtasks.filter((_, i) => i !== index))
  }

  const updateSubtaskDescription = (index, description) => {
    const updated = [...subtasks]
    updated[index].description = description
    setSubtasks(updated)
  }

  const handleSubmit = (e) => {
    e.preventDefault()

    // Validate due date is in the future
    const selectedDate = new Date(formData.due_date + 'T00:00:00')
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    if (selectedDate < today) {
      alert('Due date must be in the future')
      return
    }

    // Format the data for submission
    let assigneeIds = []

    // For individual initiatives
    if (formData.type === 'INDIVIDUAL') {
      if (createForMyself) {
        // Assign to myself
        if (!user.user_id) {
          alert('User ID not found')
          return
        }
        assigneeIds = [user.user_id]
      } else {
        // Assign to someone else (should be selected in formData.assignee_ids)
        if (!formData.assignee_ids || formData.assignee_ids.length === 0 || !formData.assignee_ids[0]) {
          alert('Please select an assignee')
          return
        }
        assigneeIds = [formData.assignee_ids[0]]
      }
    }
    // For group initiatives
    else if (formData.type === 'GROUP') {
      // Filter out any null values
      const validAssignees = formData.assignee_ids.filter(id => id !== null && id !== undefined)

      if (validAssignees.length < 2) {
        alert('Please select at least 2 group members')
        return
      }
      if (!formData.team_head_id) {
        alert('Please select a team head')
        return
      }
      assigneeIds = validAssignees
    }

    // Final validation - ensure no null values in assigneeIds
    if (assigneeIds.some(id => !id || id === null)) {
      alert('Invalid assignee selection. Please try again.')
      return
    }

    const submitData = {
      title: formData.title,
      description: formData.description,
      type: formData.type,
      urgency: formData.urgency,
      due_date: formData.due_date + 'T23:59:59',
      assignee_ids: assigneeIds,
      team_head_id: formData.team_head_id || null,
      goal_id: formData.goal_id === 'none' ? null : formData.goal_id,
      files: attachedFiles,
      subtasks: subtasks.length > 0 ? subtasks : undefined
    }

    console.log('Submitting initiative:', submitData)

    // Pass initiative ID if editing
    if (initiative) {
      onSubmit({ ...submitData, id: initiative.id })
    } else {
      onSubmit(submitData)
    }
    onClose()
  }

  // Filter out current user from assignable users list
  const availableUsers = Array.isArray(assignableUsers)
    ? assignableUsers.filter(u => u.id !== user?.user_id)
    : []

  // Filter goals based on user's department and scope
  const activeGoals = Array.isArray(goals) ? goals.filter(g => {
    // Only show active goals
    if (g.status !== 'active' && g.status !== 'ACTIVE') return false

    // Show yearly and quarterly goals to everyone
    if (g.type === 'yearly' || g.type === 'YEARLY' || g.type === 'quarterly' || g.type === 'QUARTERLY') {
      return true
    }

    // For departmental goals, filter by user's department unless user has global scope
    if (g.type === 'departmental' || g.type === 'DEPARTMENTAL') {
      // If user has global scope, show all departmental goals
      if (user?.scope === 'global') {
        return true
      }
      // Otherwise, only show goals from user's department
      return g.organization_id === user?.organization_id
    }

    return true
  }) : []

  // Get selected goal
  const selectedGoal = activeGoals.find(g => g.id === formData.goal_id)

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] flex flex-col ">
        <form onSubmit={handleSubmit} className="flex flex-col h-full overflow-y-scroll w-full">
          <DialogHeader>
            <DialogTitle>
              {initiative ? 'Edit Initiative' : 'Create Initiative'}
            </DialogTitle>
            <DialogDescription>
              {initiative
                ? 'Update the initiative details below.'
                : 'Create a new initiative assignment.'}
            </DialogDescription>
          </DialogHeader>

          <ScrollArea className="flex-1 pr-4">
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Initiative title"
                required
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Detailed description of the initiative"
                rows={3}
              />
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="type">Type</Label>
                <Select
                  value={formData.type}
                  onValueChange={(value) => {
                    setFormData({
                      ...formData,
                      type: value,
                      assignee_ids: [],
                      team_head_id: ""
                    })
                    // Reset checkbox when switching to individual
                    if (value === 'INDIVIDUAL') {
                      setCreateForMyself(true)
                    }
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="INDIVIDUAL">Individual</SelectItem>
                    <SelectItem value="GROUP">Group</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="urgency">Priority</Label>
                <Select
                  value={formData.urgency}
                  onValueChange={(value) => setFormData({ ...formData, urgency: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select priority" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="LOW">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-gray-400"></div>
                        Low
                      </div>
                    </SelectItem>
                    <SelectItem value="MEDIUM">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-yellow-400"></div>
                        Medium
                      </div>
                    </SelectItem>
                    <SelectItem value="HIGH">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-orange-400"></div>
                        High
                      </div>
                    </SelectItem>
                    <SelectItem value="URGENT">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-red-400"></div>
                        Urgent
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="due_date">Due Date</Label>
                <Input
                  id="due_date"
                  type="date"
                  value={formData.due_date}
                  onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                  min={new Date(new Date().setDate(new Date().getDate() + 1)).toISOString().split('T')[0]}
                  required
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label>Linked Goal (Optional)</Label>
              <Popover open={goalOpen} onOpenChange={setGoalOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={goalOpen}
                    className="w-full justify-between"
                  >
                    {selectedGoal ? (
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          {selectedGoal.type === 'yearly' || selectedGoal.type === 'YEARLY' ? 'Yearly' :
                           selectedGoal.type === 'quarterly' || selectedGoal.type === 'QUARTERLY' ? 'Quarterly' :
                           'Departmental'}
                        </Badge>
                        {(selectedGoal.type === 'departmental' || selectedGoal.type === 'DEPARTMENTAL') && selectedGoal.organization_name && (
                          <Badge variant="secondary" className="text-xs">
                            {selectedGoal.organization_name}
                          </Badge>
                        )}
                        <span className="truncate">{selectedGoal.title}</span>
                      </div>
                    ) : (
                      "Search goals..."
                    )}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[500px] p-0">
                  <Command>
                    <CommandInput placeholder="Search goals..." />
                    <CommandEmpty>No goal found.</CommandEmpty>
                    <CommandGroup className="max-h-64 overflow-auto">
                      <CommandItem
                        value="none"
                        onSelect={() => {
                          setFormData({ ...formData, goal_id: "none" })
                          setGoalOpen(false)
                        }}
                      >
                        <Check
                          className={cn(
                            "mr-2 h-4 w-4",
                            formData.goal_id === "none" ? "opacity-100" : "opacity-0"
                          )}
                        />
                        <span className="text-muted-foreground">None</span>
                      </CommandItem>
                      {activeGoals.map((goal) => (
                        <CommandItem
                          key={goal.id}
                          value={`${goal.title} ${goal.type} ${goal.organization_name || ''}`}
                          onSelect={() => {
                            setFormData({ ...formData, goal_id: goal.id })
                            setGoalOpen(false)
                          }}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              formData.goal_id === goal.id ? "opacity-100" : "opacity-0"
                            )}
                          />
                          <div className="flex items-center gap-2 flex-1 flex-wrap">
                            <Badge variant="outline" className="text-xs">
                              {goal.type === 'yearly' || goal.type === 'YEARLY' ? 'Yearly' :
                               goal.type === 'quarterly' || goal.type === 'QUARTERLY' ? 'Quarterly' :
                               'Departmental'}
                            </Badge>
                            {(goal.type === 'departmental' || goal.type === 'DEPARTMENTAL') && goal.organization_name && (
                              <Badge variant="secondary" className="text-xs">
                                {goal.organization_name}
                              </Badge>
                            )}
                            <span className="flex-1">{goal.title}</span>
                          </div>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            {/* Individual Initiative Assignment */}
            {formData.type === 'INDIVIDUAL' && (
              <div className="grid gap-3">
                {/* Checkbox for creating for myself */}
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="createForMyself"
                    checked={createForMyself}
                    onChange={(e) => {
                      setCreateForMyself(e.target.checked)
                      if (e.target.checked) {
                        // Clear assignee selection when checking
                        setFormData({ ...formData, assignee_ids: [] })
                      }
                    }}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <Label htmlFor="createForMyself" className="text-sm font-medium cursor-pointer">
                    Create for myself
                  </Label>
                </div>

                {/* Show assignee selection only if not creating for myself */}
                {!createForMyself && (
                  <div className="grid gap-2">
                    <Label>Assign To <span className="text-red-500">*</span></Label>
                    <Popover open={assigneeOpen} onOpenChange={setAssigneeOpen}>
                      <PopoverTrigger asChild>
                        <Button
                          variant="outline"
                          role="combobox"
                          aria-expanded={assigneeOpen}
                          className="w-full justify-between"
                        >
                          {formData.assignee_ids.length === 0 ? (
                            "Search and select user..."
                          ) : (
                            <div className="flex items-center gap-2">
                              <Avatar className="h-5 w-5">
                                <AvatarFallback className="text-xs">
                                  {availableUsers.find(u => u.id === formData.assignee_ids[0])?.name?.split(' ').map(n => n[0]).join('') || 'U'}
                                </AvatarFallback>
                              </Avatar>
                              <span className="truncate">
                                {availableUsers.find(u => u.id === formData.assignee_ids[0])?.name || 'Selected'}
                              </span>
                            </div>
                          )}
                          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-[500px] p-0">
                        <Command>
                          <CommandInput placeholder="Search users by name or email..." />
                          <CommandEmpty>No user found.</CommandEmpty>
                          <CommandGroup className="max-h-64 overflow-auto">
                            {availableUsers.map((userItem) => {
                              const isSelected = formData.assignee_ids.includes(userItem.id)
                              return (
                                <CommandItem
                                  key={userItem.id}
                                  value={`${userItem.name} ${userItem.email}`}
                                  onSelect={() => {
                                    setFormData({ ...formData, assignee_ids: [userItem.id] })
                                    setAssigneeOpen(false)
                                  }}
                                >
                                  <Check
                                    className={cn(
                                      "mr-2 h-4 w-4",
                                      isSelected ? "opacity-100" : "opacity-0"
                                    )}
                                  />
                                  <Avatar className="h-6 w-6 mr-2">
                                    <AvatarFallback className="text-xs">
                                      {userItem.name?.split(' ').map(n => n[0]).join('') || 'U'}
                                    </AvatarFallback>
                                  </Avatar>
                                  <div className="flex flex-col flex-1">
                                    <span className="font-medium">{userItem.name}</span>
                                    <span className="text-xs text-muted-foreground">{userItem.email}</span>
                                    {userItem.job_title && (
                                      <span className="text-xs text-muted-foreground">{userItem.job_title}</span>
                                    )}
                                  </div>
                                </CommandItem>
                              )
                            })}
                          </CommandGroup>
                        </Command>
                      </PopoverContent>
                    </Popover>
                  </div>
                )}
              </div>
            )}

            {/* Group Members Selection */}
            {formData.type === 'GROUP' && (
              <div className="grid gap-2">
                <Label>Group Members</Label>

                {/* Selected Assignees Display */}
                {formData.assignee_ids.length > 0 && (
                <div className="p-3 border rounded-lg bg-muted/50">
                  <div className="flex flex-wrap gap-2">
                    {formData.assignee_ids.map((userId) => {
                      const user = availableUsers.find(u => u.id === userId)
                      if (!user) return null
                      return (
                        <div key={user.id} className="flex items-center gap-1 bg-primary/10 text-primary px-2 py-1 rounded-md text-sm">
                          <Avatar className="h-4 w-4">
                            <AvatarFallback className="text-[8px]">
                              {user.name?.split(' ').map(n => n[0]).join('') || 'U'}
                            </AvatarFallback>
                          </Avatar>
                          <span>{user.name}</span>
                          <button
                            type="button"
                            onClick={() => {
                              setFormData({
                                ...formData,
                                assignee_ids: formData.assignee_ids.filter(id => id !== user.id),
                                team_head_id: formData.team_head_id === user.id ? "" : formData.team_head_id
                              })
                            }}
                            className="ml-1 hover:text-destructive"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

                {/* Searchable Group Member Selector */}
                <Popover open={assigneeOpen} onOpenChange={setAssigneeOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      role="combobox"
                      aria-expanded={assigneeOpen}
                      className="w-full justify-between"
                    >
                      {formData.assignee_ids.length === 0 ? (
                        "Search and select group members..."
                      ) : (
                        `${formData.assignee_ids.length} member${formData.assignee_ids.length > 1 ? 's' : ''} selected`
                      )}
                      <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-[500px] p-0">
                    <Command>
                      <CommandInput placeholder="Search users by name, email, or organization..." />
                      <CommandEmpty>No user found.</CommandEmpty>
                      <CommandGroup className="max-h-64 overflow-auto">
                        {availableUsers.map((userItem) => {
                          const isSelected = formData.assignee_ids.includes(userItem.id)
                          return (
                            <CommandItem
                              key={userItem.id}
                              value={`${userItem.name} ${userItem.email} ${userItem.organization_name || ''}`}
                              onSelect={() => {
                                // Multi-selection for group initiatives
                                if (isSelected) {
                                  setFormData({
                                    ...formData,
                                    assignee_ids: formData.assignee_ids.filter(id => id !== userItem.id),
                                    team_head_id: formData.team_head_id === userItem.id ? "" : formData.team_head_id
                                  })
                                } else {
                                  setFormData({
                                    ...formData,
                                    assignee_ids: [...formData.assignee_ids, userItem.id]
                                  })
                                }
                              }}
                            >
                              <Check
                                className={cn(
                                  "mr-2 h-4 w-4",
                                  isSelected ? "opacity-100" : "opacity-0"
                                )}
                              />
                              <Avatar className="h-6 w-6 mr-2">
                                <AvatarFallback className="text-xs">
                                  {userItem.name?.split(' ').map(n => n[0]).join('') || 'U'}
                                </AvatarFallback>
                              </Avatar>
                              <div className="flex flex-col flex-1">
                                <span className="font-medium">{userItem.name}</span>
                                <span className="text-xs text-muted-foreground">{userItem.email}</span>
                                {userItem.organization_name && (
                                  <span className="text-xs text-muted-foreground">{userItem.organization_name}</span>
                                )}
                              </div>
                            </CommandItem>
                          )
                        })}
                      </CommandGroup>
                    </Command>
                  </PopoverContent>
                </Popover>
              </div>
            )}

            {/* Team Head Selection for Group Initiatives */}
            {formData.type === 'GROUP' && formData.assignee_ids.length > 0 && (
              <div className="grid gap-2">
                <Label htmlFor="team_head">Team Head</Label>
                <Select
                  value={formData.team_head_id}
                  onValueChange={(value) => setFormData({ ...formData, team_head_id: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select team head from assigned members" />
                  </SelectTrigger>
                  <SelectContent>
                    {formData.assignee_ids.map((userId) => {
                      const user = availableUsers.find(u => u.id === userId)
                      return user ? (
                        <SelectItem key={user.id} value={user.id}>
                          <div className="flex items-center gap-2">
                            <Avatar className="h-5 w-5">
                              <AvatarFallback className="text-xs">
                                {user.name?.split(' ').map(n => n[0]).join('') || 'U'}
                              </AvatarFallback>
                            </Avatar>
                            <span>{user.name}</span>
                          </div>
                        </SelectItem>
                      ) : null
                    })}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Sub-tasks Section (only shown when creating, not editing) */}
            {!initiative && (
              <div className="grid gap-3 border rounded-lg p-4 bg-slate-50">
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-medium">Sub-tasks (Optional)</Label>
                  <span className="text-xs text-muted-foreground">{subtasks.length} sub-task{subtasks.length !== 1 ? 's' : ''}</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Break down this initiative into smaller, trackable sub-tasks. These can be checked off as you progress.
                </p>

                {/* Add new subtask */}
                <div className="flex gap-2">
                  <Input
                    value={newSubtaskTitle}
                    onChange={(e) => setNewSubtaskTitle(e.target.value)}
                    placeholder="Enter sub-task title..."
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addSubtask()
                      }
                    }}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={addSubtask}
                    disabled={!newSubtaskTitle.trim()}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>

                {/* List of subtasks */}
                {subtasks.length > 0 && (
                  <div className="space-y-2 mt-2">
                    {subtasks.map((subtask, index) => (
                      <div key={index} className="flex items-start gap-2 p-2 bg-white rounded border">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium">{index + 1}.</span>
                            <span className="text-sm">{subtask.title}</span>
                          </div>
                          <Input
                            value={subtask.description || ""}
                            onChange={(e) => updateSubtaskDescription(index, e.target.value)}
                            placeholder="Add description (optional)..."
                            className="mt-1 text-xs h-8"
                          />
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeSubtask(index)}
                          className="h-6 w-6 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* File Upload Section */}
            <div className="grid gap-2">
              <FileUpload
                files={attachedFiles}
                onFilesChange={setAttachedFiles}
                label="Attach Documents (Optional)"
                description="Upload supporting documents, references, or files related to this initiative"
                maxFiles={5}
                maxSize={10 * 1024 * 1024} // 10MB
                optional={true}
                acceptedTypes=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.gif,.mp4,.mov,.zip,.rar"
              />
            </div>
          </div>
          </ScrollArea>

          <DialogFooter className="mt-4">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">
              {initiative ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function InitiativeSubmissionDialog({ initiative, isOpen, onClose, onSubmit }) {
  const [formData, setFormData] = useState({
    report: ""
  })
  const [submissionFiles, setSubmissionFiles] = useState([])

  // Reset files when dialog opens/closes
  useEffect(() => {
    if (!isOpen) {
      setSubmissionFiles([])
    }
  }, [isOpen])

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit({
      ...formData,
      files: submissionFiles
    })
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Submit Initiative</DialogTitle>
            <DialogDescription>
              Submit your completed work for &ldquo;{initiative?.title}&rdquo;
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="report">Completion Report *</Label>
              <p className="text-xs text-muted-foreground mb-2">
                Provide a detailed report of what was completed, challenges faced, outcomes achieved, and any relevant details. Use the toolbar to format your report.
              </p>
              <RichTextEditor
                content={formData.report}
                onChange={(html) => setFormData({ ...formData, report: html })}
                placeholder="Start typing your completion report here..."
              />
            </div>

            {/* File Upload for Submission */}
            <div className="grid gap-2">
              <FileUpload
                files={submissionFiles}
                onFilesChange={setSubmissionFiles}
                label="Attach Supporting Documents (Optional)"
                description="Upload completed work, screenshots, reports, or other evidence of initiative completion"
                maxFiles={10}
                maxSize={25 * 1024 * 1024} // 25MB for submissions
                optional={true}
                acceptedTypes=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.gif,.mp4,.mov,.zip,.rar"
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">
              Submit Initiative
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function InitiativeReviewDialog({ initiative, isOpen, onClose, onSubmit }) {
  const [formData, setFormData] = useState({
    score: 7,
    feedback: "",
    approved: true
  })
  const [submission, setSubmission] = useState(null)
  const [loadingSubmission, setLoadingSubmission] = useState(false)

  // Fetch submission when dialog opens
  useEffect(() => {
    const fetchSubmission = async () => {
      if (isOpen && initiative?.id) {
        setLoadingSubmission(true)
        try {
          const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
          const response = await fetch(`${API_URL}/api/initiatives/${initiative.id}/submission`)
          if (response.ok) {
            const data = await response.json()
            setSubmission(data)
          }
        } catch (error) {
          console.error('Error fetching submission:', error)
        } finally {
          setLoadingSubmission(false)
        }
      }
    }

    if (isOpen) {
      setFormData({
        score: 7,
        feedback: "",
        approved: true
      })
      fetchSubmission()
    } else {
      setSubmission(null)
    }
  }, [isOpen, initiative?.id])

  const handleApprove = () => {
    if (!formData.score || formData.score < 1 || formData.score > 10) {
      alert('Please select a valid grade between 1 and 10')
      return
    }

    onSubmit({ ...formData, approved: true })
    onClose()
  }

  const handleReject = () => {
    if (!formData.feedback || formData.feedback.trim() === '') {
      alert('Redo instructions are required. Please explain what needs to be changed.')
      return
    }

    onSubmit({ ...formData, approved: false })
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[700px] max-h-[90vh]">
        <DialogHeader>
          <DialogTitle>Review Initiative</DialogTitle>
          <DialogDescription>
            Review the submission and provide feedback
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[60vh] pr-4">
          <div className="space-y-6 py-4">
            {/* Initiative Title */}
            <div>
              <h3 className="font-semibold text-lg">{initiative?.title}</h3>
              <p className="text-sm text-muted-foreground">{initiative?.description}</p>
            </div>

            {/* Submission Report */}
            {loadingSubmission ? (
              <div className="text-sm text-muted-foreground">Loading submission...</div>
            ) : submission ? (
              <div className="border-2 border-purple-200 rounded-lg p-4 bg-purple-50">
                <h4 className="font-semibold mb-3 text-purple-900">Completion Report</h4>
                <div className="p-3 bg-white border rounded-lg prose prose-sm max-w-none">
                  <div dangerouslySetInnerHTML={{ __html: submission.report }} />
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Submitted by {submission.submitter_name} on {new Date(submission.submitted_at).toLocaleString()}
                </p>

                {/* Submitted Documents */}
                {submission.documents && submission.documents.length > 0 && (
                  <div className="mt-4">
                    <h4 className="font-medium text-sm mb-2 text-purple-900">Submitted Documents ({submission.documents.length})</h4>
                    <div className="space-y-2">
                      {submission.documents.map((doc) => (
                        <div key={doc.id} className="flex items-center gap-3 p-2 bg-white border rounded-lg hover:bg-muted/50">
                          <FileText className="h-4 w-4 text-purple-600" />
                          <div className="flex-1">
                            <p className="text-sm font-medium">{doc.file_name}</p>
                            <p className="text-xs text-muted-foreground">
                              Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}
                            </p>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
                              const url = `${API_URL}/api/initiatives/documents/${doc.id}/download`
                              const link = document.createElement('a')
                              link.href = url
                              link.download = doc.file_name
                              link.target = '_blank'
                              document.body.appendChild(link)
                              link.click()
                              document.body.removeChild(link)
                            }}
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No submission details available</p>
            )}

            <Separator />

            {/* Review Form */}
            <div className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="score">Grade (1-10) *</Label>
                <Select
                  value={formData.score.toString()}
                  onValueChange={(value) => setFormData({ ...formData, score: parseInt(value) })}
                  required
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select grade" />
                  </SelectTrigger>
                  <SelectContent>
                    {[...Array(10)].map((_, i) => (
                      <SelectItem key={i + 1} value={(i + 1).toString()}>
                        {i + 1} - {i < 3 ? 'Poor' : i < 6 ? 'Fair' : i < 8 ? 'Good' : 'Excellent'}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">Rate the quality and completion of the work</p>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="feedback">
                  Feedback
                </Label>
                <Textarea
                  id="feedback"
                  value={formData.feedback}
                  onChange={(e) => setFormData({ ...formData, feedback: e.target.value })}
                  placeholder="Provide feedback on the work quality, what was done well, or what needs to be improved..."
                  rows={5}
                  className="min-h-[120px]"
                />
                <p className="text-xs text-muted-foreground">
                  Feedback is optional for approval, but required if rejecting
                </p>
              </div>
            </div>
          </div>
        </ScrollArea>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleReject}
          >
            <X className="mr-2 h-4 w-4" />
            Reject
          </Button>
          <Button
            onClick={handleApprove}
          >
            <Check className="mr-2 h-4 w-4" />
            Accept & Grade
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function InitiativeApprovalDialog({ initiative, isOpen, onClose, onSubmit }) {
  const [formData, setFormData] = useState({
    approved: true,
    rejection_reason: ""
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit(formData)
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Approve or Reject Initiative</DialogTitle>
            <DialogDescription>
              Review and approve or reject &ldquo;{initiative?.title}&rdquo;
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Decision</Label>
              <div className="flex gap-4">
                <Button
                  type="button"
                  variant={formData.approved ? "default" : "outline"}
                  onClick={() => setFormData({ ...formData, approved: true, rejection_reason: "" })}
                  className="flex-1"
                >
                  <Check className="mr-2 h-4 w-4" />
                  Approve
                </Button>
                <Button
                  type="button"
                  variant={!formData.approved ? "destructive" : "outline"}
                  onClick={() => setFormData({ ...formData, approved: false })}
                  className="flex-1"
                >
                  <X className="mr-2 h-4 w-4" />
                  Reject
                </Button>
              </div>
            </div>

            {!formData.approved && (
              <div className="grid gap-2">
                <Label htmlFor="rejection_reason">Rejection Reason</Label>
                <Textarea
                  id="rejection_reason"
                  value={formData.rejection_reason}
                  onChange={(e) => setFormData({ ...formData, rejection_reason: e.target.value })}
                  placeholder="Explain why this initiative is being rejected"
                  rows={4}
                  required
                />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant={formData.approved ? "default" : "destructive"}
            >
              {formData.approved ? 'Approve Initiative' : 'Reject Initiative'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function InitiativeDetailModal({ initiative, isOpen, onClose, onEdit, onDelete, onUpdateStatus, onSubmit, onReview, onApprove, canUserSubmit, canUserReview, canUserApprove }) {
  const [submission, setSubmission] = useState(null)
  const [loadingSubmission, setLoadingSubmission] = useState(false)

  // Fetch submission details when initiative is pending_review and user is creator
  useEffect(() => {
    const fetchSubmission = async () => {
      if (!initiative || !isOpen) {
        setSubmission(null)
        return
      }

      if ((initiative.status === 'UNDER_REVIEW' || initiative.status === 'under_review') && canUserReview(initiative)) {
        setLoadingSubmission(true)
        try {
          const response = await fetch(`http://localhost:8000/api/initiatives/${initiative.id}/submission`, {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
          })
          if (response.ok) {
            const data = await response.json()
            setSubmission(data)
          }
        } catch (error) {
          console.error('Error fetching submission:', error)
        } finally {
          setLoadingSubmission(false)
        }
      } else {
        setSubmission(null)
      }
    }

    fetchSubmission()
  }, [initiative, isOpen, canUserReview])

  if (!initiative) return null

  const formatDate = (date) => {
    return new Date(date).toLocaleString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const isOverdue = new Date(initiative.due_date) < new Date() && initiative.status !== 'approved'

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="text-xl">{initiative.title}</DialogTitle>
          <DialogDescription className="flex items-center gap-2 mt-2">
            <Badge className={statusColors[initiative.status]}>
              {initiative.status}
            </Badge>
            <Badge className={urgencyColors[initiative.urgency || 'medium']}>
              <div className="flex items-center gap-1">
                <div className={`w-2 h-2 rounded-full ${
                  initiative.urgency === 'urgent' ? 'bg-red-500' :
                  initiative.urgency === 'high' ? 'bg-orange-500' :
                  initiative.urgency === 'low' ? 'bg-gray-500' : 'bg-yellow-500'
                }`}></div>
                {initiative.urgency ? initiative.urgency.charAt(0).toUpperCase() + initiative.urgency.slice(1) : 'Medium'}
              </div>
            </Badge>
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[50vh] pr-4">
          <div className="space-y-6">
            {/* Description */}
            <div>
              <h3 className="font-semibold mb-2">Description</h3>
              <p className="text-sm text-muted-foreground">
                {initiative.description || 'No description provided'}
              </p>
            </div>

            {/* Assignees */}
            <div>
              <h3 className="font-semibold mb-2">Assignees</h3>
              <div className="space-y-2">
                {initiative.assignments && initiative.assignments.length > 0 ? (
                  initiative.assignments.map((assignment) => (
                    <div key={assignment.user_id} className="flex items-center gap-3 p-2 border rounded-lg">
                      <Avatar>
                        <AvatarFallback>
                          {assignment.user_name?.split(' ').map(n => n[0]).join('') || 'U'}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1">
                        <p className="font-medium">{assignment.user_name}</p>
                        <p className="text-sm text-muted-foreground">{assignment.user_email}</p>
                      </div>
                      {initiative.team_head_id === assignment.user_id && (
                        <Badge variant="outline">Team Head</Badge>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No assignees</p>
                )}
              </div>
            </div>

            <Separator />

            {/* Sub-Tasks */}
            <SubTaskList
              initiativeId={initiative.id}
              initiativeStatus={initiative.status}
            />

            <Separator />

            {/* Initiative Details */}
            <div className="grid gap-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium text-sm text-muted-foreground">Created By</h4>
                  <p className="text-sm">{initiative.creator_name || 'Unknown'}</p>
                </div>
                <div>
                  <h4 className="font-medium text-sm text-muted-foreground">Created At</h4>
                  <p className="text-sm">{formatDate(initiative.created_at)}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium text-sm text-muted-foreground">Due Date</h4>
                  <p className={`text-sm ${isOverdue ? 'text-red-600 font-medium' : ''}`}>
                    {formatDate(initiative.due_date)}
                    {isOverdue && <span className="ml-2 text-xs">(Overdue)</span>}
                  </p>
                </div>
                <div>
                  <h4 className="font-medium text-sm text-muted-foreground">Score</h4>
                  <div className="text-sm">
                    {initiative.score ? (
                      <div className="flex items-center gap-1">
                        <span>{initiative.score}/10</span>
                      </div>
                    ) : (
                      <span className="text-muted-foreground">Not scored</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Initiative Documents */}
            {initiative.documents && initiative.documents.length > 0 && (
              <div>
                <h3 className="font-semibold mb-2">Attached Documents ({initiative.documents.length})</h3>
                <div className="space-y-2">
                  {initiative.documents.map((doc, index) => (
                    <div key={index} className="flex items-center gap-3 p-2 border rounded-lg hover:bg-muted/50">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <div className="flex-1">
                        <p className="text-sm font-medium">{doc.file_name}</p>
                        <p className="text-xs text-muted-foreground">
                          Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          // Download document
                          const url = `http://localhost:8000/api/initiatives/documents/${doc.id}/download`
                          const link = document.createElement('a')
                          link.href = url
                          link.download = doc.file_name
                          link.target = '_blank'
                          document.body.appendChild(link)
                          link.click()
                          document.body.removeChild(link)
                        }}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Submission Details (for creator when initiative is UNDER_REVIEW) */}
            {(initiative.status === 'UNDER_REVIEW' || initiative.status === 'under_review') && canUserReview(initiative) && (
              <div className="border-2 border-purple-200 rounded-lg p-4 bg-purple-50">
                <h3 className="font-semibold mb-3 text-purple-900">Initiative Submission</h3>

                {loadingSubmission ? (
                  <div className="text-sm text-muted-foreground">Loading submission...</div>
                ) : submission ? (
                  <div className="space-y-4">
                    {/* Submission Report */}
                    <div>
                      <h4 className="font-medium text-sm mb-2">Completion Report</h4>
                      <div className="p-3 bg-white border rounded-lg prose prose-sm max-w-none">
                        <div dangerouslySetInnerHTML={{ __html: submission.report }} />
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        Submitted by {submission.submitter_name} on {new Date(submission.submitted_at).toLocaleString()}
                      </p>
                    </div>

                    {/* Submitted Documents */}
                    {submission.documents && submission.documents.length > 0 && (
                      <div>
                        <h4 className="font-medium text-sm mb-2">Submitted Documents ({submission.documents.length})</h4>
                        <div className="space-y-2">
                          {submission.documents.map((doc) => (
                            <div key={doc.id} className="flex items-center gap-3 p-2 bg-white border rounded-lg hover:bg-muted/50">
                              <FileText className="h-4 w-4 text-purple-600" />
                              <div className="flex-1">
                                <p className="text-sm font-medium">{doc.file_name}</p>
                                <p className="text-xs text-muted-foreground">
                                  Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}
                                </p>
                              </div>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  // Download document
                                  const url = `http://localhost:8000/api/initiatives/documents/${doc.id}/download`
                                  const link = document.createElement('a')
                                  link.href = url
                                  link.download = doc.file_name
                                  link.target = '_blank'
                                  document.body.appendChild(link)
                                  link.click()
                                  document.body.removeChild(link)
                                }}
                              >
                                <Download className="h-4 w-4" />
                              </Button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No submission details available</p>
                )}
              </div>
            )}

            {/* Feedback - Show prominently for redo requests */}
            {initiative.feedback && (
              <div className={initiative.status === 'ONGOING' || initiative.status === 'ongoing'
                ? 'border-2 border-orange-200 rounded-lg p-4 bg-orange-50'
                : ''}>
                <h3 className={`font-semibold mb-2 ${initiative.status === 'ONGOING' || initiative.status === 'ongoing' ? 'text-orange-900 flex items-center gap-2' : ''}`}>
                  {(initiative.status === 'ONGOING' || initiative.status === 'ongoing') && (
                    <X className="h-5 w-5" />
                  )}
                  {(initiative.status === 'ONGOING' || initiative.status === 'ongoing')
                    ? 'Redo Instructions from Supervisor'
                    : 'Supervisor Feedback'}
                </h3>
                <div className={`p-3 rounded-lg ${initiative.status === 'ONGOING' || initiative.status === 'ongoing' ? 'bg-white border-2 border-orange-300' : 'bg-muted'}`}>
                  <p className="text-sm whitespace-pre-wrap">{initiative.feedback}</p>
                </div>
                {(initiative.status === 'ONGOING' || initiative.status === 'ongoing') && (
                  <p className="text-xs text-orange-700 font-medium mt-2">
                    This initiative has been sent back for improvements. Please address the feedback above and resubmit.
                  </p>
                )}
              </div>
            )}
          </div>
        </ScrollArea>

        <DialogFooter className="flex gap-2">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>

          {/* Action buttons based on initiative status and user permissions */}
          {/* Supervisor approves initiative in PENDING_APPROVAL */}
          {(initiative.status === 'PENDING_APPROVAL' || initiative.status === 'pending_approval') && canUserApprove(initiative) && (
            <Button onClick={() => {
              onApprove(initiative)
              onClose()
            }}>
              <Check className="mr-2 h-4 w-4" />
              Review & Approve
            </Button>
          )}

          {/* Assignee accepts ASSIGNED initiative */}
          {(initiative.status === 'ASSIGNED' || initiative.status === 'assigned') && canUserSubmit(initiative) && (
            <Button onClick={() => {
              onUpdateStatus(initiative, 'ACCEPT')
              onClose()
            }}>
              <Check className="mr-2 h-4 w-4" />
              Accept Initiative
            </Button>
          )}

          {/* Assignee starts PENDING initiative */}
          {(initiative.status === 'PENDING' || initiative.status === 'pending') && canUserSubmit(initiative) && (
            <Button onClick={() => {
              onUpdateStatus(initiative, 'START')
              onClose()
            }}>
              Start Initiative
            </Button>
          )}

          {/* Assignee submits ONGOING initiative */}
          {(initiative.status === 'ONGOING' || initiative.status === 'ongoing') && canUserSubmit(initiative) && (
            <Button onClick={() => {
              onSubmit(initiative)
              onClose()
            }}>
              <FileText className="mr-2 h-4 w-4" />
              Submit Initiative
            </Button>
          )}

          {/* Supervisor/Assigner reviews UNDER_REVIEW initiative */}
          {(initiative.status === 'UNDER_REVIEW' || initiative.status === 'under_review')   && (
            <Button onClick={() => {
              onReview(initiative)
              onClose()
            }}>
              <Star className="mr-2 h-4 w-4" />
              Review Initiative
            </Button>
          )}

          {/* Edit and Delete buttons - only for PENDING_APPROVAL or ASSIGNED status */}
          {canUserReview(initiative) && (initiative.status === 'PENDING_APPROVAL' || initiative.status === 'pending_approval' || initiative.status === 'ASSIGNED' || initiative.status === 'assigned') && (
            <>
              <Button variant="outline" onClick={() => {
                onEdit(initiative)
                onClose()
              }}>
                <Edit className="mr-2 h-4 w-4" />
                Edit
              </Button>
              <Button variant="destructive" onClick={() => {
                onDelete(initiative)
                onClose()
              }}>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function InitiativesPage() {
  const { user } = useAuth()
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [isSubmissionOpen, setIsSubmissionOpen] = useState(false)
  const [isReviewOpen, setIsReviewOpen] = useState(false)
  const [isApprovalOpen, setIsApprovalOpen] = useState(false)
  const [isInitiativeDetailOpen, setIsInitiativeDetailOpen] = useState(false)
  const [editingInitiative, setEditingInitiative] = useState(null)
  const [submittingInitiative, setSubmittingInitiative] = useState(null)
  const [reviewingInitiative, setReviewingInitiative] = useState(null)
  const [approvingInitiative, setApprovingInitiative] = useState(null)
  const [selectedInitiative, setSelectedInitiative] = useState(null)
  const [activeTab, setActiveTab] = useState("my-initiatives")
  const [searchTerm, setSearchTerm] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [urgencyFilter, setUrgencyFilter] = useState("")
  const [typeFilter, setTypeFilter] = useState("")
  const [currentPage, setCurrentPage] = useState(1)
  const [perPage] = useState(20)

  const { data: usersData, isLoading: isLoadingUsers } = useUsers()
  const users = usersData?.users || []

  // Check if user has supervisees
  const { data: superviseeCheck } = useHasSupervisees()
  const hasSupervisees = superviseeCheck?.has_supervisees || false
  const superviseeCount = superviseeCheck?.supervisee_count || 0

  // Get supervisees for supervisor view
  const supervisees = useMemo(() => {
    if (!user?.user_id || !users || users.length === 0) return []
    return users.filter(u => u.supervisor_id === user.user_id)
  }, [users, user?.user_id])

  // Build params with filters
  const buildParams = (isMyTasks) => {
    const params = {
      page: activeTab === (isMyTasks ? 'my-initiatives' : 'all-initiatives') ? currentPage : 1,
      per_page: perPage,
      assigned_to_me: isMyTasks
    }

    // Add filters only if they have values other than "all" or empty
    if (statusFilter && statusFilter !== 'all' && statusFilter !== '') {
      params.status_filter = [statusFilter]
    }
    if (typeFilter && typeFilter !== 'all' && typeFilter !== '') {
      params.task_type = typeFilter
    }
    if (urgencyFilter && urgencyFilter !== 'all' && urgencyFilter !== '') {
      params.urgency_filter = urgencyFilter
    }

    return params
  }

  // Fetch initiatives based on active tab
  const myInitiativesParams = buildParams(true)
  const allInitiativesParams = buildParams(false)

  const { data: myInitiativesData, isLoading: myInitiativesLoading } = useInitiatives(myInitiativesParams)
  const { data: allInitiativesData, isLoading: allInitiativesLoading } = useInitiatives(allInitiativesParams)
  const { data: superviseeInitiativesData = [], isLoading: superviseeInitiativesLoading, refetch: refetchSuperviseeInitiatives } = useSuperviseeInitiatives()

  // Refetch supervisee initiatives when switching to supervisee tab
  useEffect(() => {
    if (activeTab === "supervisee-initiatives") {
      refetchSuperviseeInitiatives()
    }
  }, [activeTab, refetchSuperviseeInitiatives])

  // Use data based on active tab
  const isLoading = activeTab === 'my-initiatives' ? myInitiativesLoading :
                     activeTab === 'supervisee-initiatives' ? superviseeInitiativesLoading :
                     allInitiativesLoading
  const initiativeData = activeTab === 'my-initiatives' ? myInitiativesData :
                         activeTab === 'supervisee-initiatives' ? { initiatives: superviseeInitiativesData, total: superviseeInitiativesData.length } :
                         allInitiativesData
  const initiatives = initiativeData?.initiatives || []
  const totalInitiatives = initiativeData?.total || 0
  const totalPages = Math.ceil(totalInitiatives / perPage)

  // Reset to page 1 when switching tabs or changing filters
  useEffect(() => {
    setCurrentPage(1)
  }, [activeTab, statusFilter, urgencyFilter, typeFilter])

  const createMutation = useCreateInitiative()
  const updateMutation = useUpdateInitiative()
  const updateStatusMutation = useUpdateInitiativeStatus()
  const submitMutation = useSubmitInitiative()
  const reviewMutation = useReviewInitiative()
  const approvalMutation = useApproveInitiative()
  const acceptMutation = useAcceptInitiative()
  const startMutation = useStartInitiative()
  const completeMutation = useCompleteInitiative()
  const deleteMutation = useDeleteInitiative()
  const handleCreate = (data) => {
    if (data.id) {
      // Editing existing initiative
      updateMutation.mutate(data)
    } else {
      // Creating new initiative
      createMutation.mutate(data)
    }
  }

  const handleUpdateStatus = (initiative, status) => {
    // Route to specific mutations based on status action
    if (status === 'ACCEPT') {
      acceptMutation.mutate(initiative.id)
    } else if (status === 'START') {
      startMutation.mutate(initiative.id)
    } else if (status === 'COMPLETE') {
      completeMutation.mutate(initiative.id)
    } else {
      updateStatusMutation.mutate({ id: initiative.id, status })
    }
  }

  const handleSubmit = (data) => {
    if (submittingInitiative) {
      submitMutation.mutate({ id: submittingInitiative.id, ...data })
    }
  }

  const handleReview = (data) => {
    if (reviewingInitiative) {
      reviewMutation.mutate({ id: reviewingInitiative.id, ...data })
    }
  }

  const handleApproval = (data) => {
    if (approvingInitiative) {
      approvalMutation.mutate({ id: approvingInitiative.id, ...data })
    }
  }

  const handleAccept = (initiativeId) => {
    acceptMutation.mutate(initiativeId)
  }

  const handleStart = (initiativeId) => {
    startMutation.mutate(initiativeId)
  }

  const handleComplete = (initiativeId) => {
    completeMutation.mutate(initiativeId)
  }

  const handleEdit = (initiative) => {
    setEditingInitiative(initiative)
    setIsFormOpen(true)
  }

  const handleDelete = (initiative) => {
    if (confirm(`Are you sure you want to delete "${initiative.title}"?`)) {
      deleteMutation.mutate(initiative.id)
    }
  }

  const handleCloseForm = () => {
    setIsFormOpen(false)
    setEditingInitiative(null)
    // Reset form will happen automatically when component unmounts/remounts
  }

  // Initiatives are already filtered, sorted, and paginated by the backend
  // Get the actual initiative lists from each query
  const myInitiativesRaw = myInitiativesData?.initiatives || []
  const allInitiativesRaw = allInitiativesData?.initiatives || []

  // Apply client-side search filter
  const filterBySearch = (initiatives) => {
    if (!searchTerm || searchTerm.trim() === '') return initiatives

    const searchLower = searchTerm.toLowerCase()
    return initiatives.filter(initiative => {
      // Search in title
      if (initiative.title?.toLowerCase().includes(searchLower)) return true
      // Search in description
      if (initiative.description?.toLowerCase().includes(searchLower)) return true
      // Search in assignee names
      if (initiative.assignments?.some(a => a.user_name?.toLowerCase().includes(searchLower))) return true
      return false
    })
  }

  const myInitiatives = filterBySearch(myInitiativesRaw)
  const allInitiatives = filterBySearch(allInitiativesRaw)

  const canUserSubmit = (initiative) => {
    const isAssigned = initiative.assignments?.some(assignment => assignment.user_id === user?.user_id)
    const isTeamHead = initiative.team_head_id === user?.user_id
    return isAssigned || isTeamHead
  }

  const canUserReview = (initiative) => {
    return initiative.created_by === user?.user_id
  }

  const canUserApprove = (initiative) => {
    // Check if user is the supervisor of the initiative creator
    // Find the creator in the users list to check their supervisor_id
    const creator = users.find(u => u.id === initiative.created_by)
    const isSupervisor = creator && creator.supervisor_id === user?.user_id

    // Also allow if user has special permission
    const hasPermission = user?.permissions?.includes('initiative_approve')

    return isSupervisor || hasPermission
  }


  function InitiativeTable({ initiatives, showActions = true }) {
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Initiative</TableHead>
            <TableHead>Priority</TableHead>
            <TableHead>Assignees</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Due Date</TableHead>
            <TableHead>Score</TableHead>
            {showActions && <TableHead className="text-right">Actions</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {initiatives.map((initiative) => (
            <TableRow
              key={initiative.id}
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => {
                setSelectedInitiative(initiative)
                setIsInitiativeDetailOpen(true)
              }}
            >
              <TableCell>
                <div>
                  <div className="font-medium">{initiative.title}</div>
                  <div className="text-sm text-muted-foreground line-clamp-2">
                    {initiative.description}
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <Badge className={urgencyColors[initiative.urgency || 'medium']}>
                  <div className="flex items-center gap-1">
                    <div className={`w-2 h-2 rounded-full ${
                      initiative.urgency === 'urgent' ? 'bg-red-500' :
                      initiative.urgency === 'high' ? 'bg-orange-500' :
                      initiative.urgency === 'low' ? 'bg-gray-500' : 'bg-yellow-500'
                    }`}></div>
                    {initiative.urgency ? initiative.urgency.charAt(0).toUpperCase() + initiative.urgency.slice(1) : 'Medium'}
                  </div>
                </Badge>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  {initiative.type === 'individual' ? (
                    <div className="flex items-center gap-2">
                      <Avatar className="h-7 w-7">
                        <AvatarFallback className="text-xs">
                          {initiative.assignments?.[0]?.user_name?.split(' ').map(n => n[0]).join('') || 'U'}
                        </AvatarFallback>
                      </Avatar>
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{initiative.assignments?.[0]?.user_name}</p>
                        <p className="text-xs text-muted-foreground truncate">{initiative.assignments?.[0]?.user_email}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <div className="flex -space-x-1">
                        {initiative.assignments?.slice(0, 3).map((assignment) => (
                          <Avatar key={assignment.user_id} className="h-6 w-6 border-2 border-background">
                            <AvatarFallback className="text-xs">
                              {assignment.user_name?.split(' ').map(n => n[0]).join('') || 'U'}
                            </AvatarFallback>
                          </Avatar>
                        ))}
                        {initiative.assignments && initiative.assignments.length > 3 && (
                          <div className="h-6 w-6 rounded-full bg-muted border-2 border-background flex items-center justify-center">
                            <span className="text-xs">+{initiative.assignments.length - 3}</span>
                          </div>
                        )}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium">{initiative.assignments?.length || 0} members</p>
                        <p className="text-xs text-muted-foreground truncate">
                          {initiative.team_head_name && `Head: ${initiative.team_head_name}`}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <Badge className={statusColors[initiative.status]}>
                  {initiative.status}
                </Badge>
              </TableCell>
              <TableCell className="text-sm">
                <div className={new Date(initiative.due_date) < new Date() && initiative.status !== 'approved' ? 'text-red-600' : ''}>
                  {new Date(initiative.due_date).toLocaleDateString()}
                </div>
              </TableCell>
              <TableCell>
                {initiative.score ? (
                  <div className="flex items-center gap-1">
                    <span>{initiative.score}/10</span>
                  </div>
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </TableCell>
              {showActions && (
                <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => {
                        setSelectedInitiative(initiative)
                        setIsInitiativeDetailOpen(true)
                      }}>
                        <Eye className="mr-2 h-4 w-4" />
                        View Details
                      </DropdownMenuItem>

                      {/* Accept ASSIGNED initiative */}
                      {(initiative.status === 'ASSIGNED' || initiative.status === 'assigned') && canUserSubmit(initiative) && (
                        <DropdownMenuItem onClick={() => handleUpdateStatus(initiative, 'ACCEPT')}>
                          <Check className="mr-2 h-4 w-4" />
                          Accept Initiative
                        </DropdownMenuItem>
                      )}

                      {/* Start PENDING initiative */}
                      {(initiative.status === 'PENDING' || initiative.status === 'pending') && canUserSubmit(initiative) && (
                        <DropdownMenuItem onClick={() => handleUpdateStatus(initiative, 'START')}>
                          Start Initiative
                        </DropdownMenuItem>
                      )}

                      {/* Submit ONGOING initiative */}
                      {(initiative.status === 'ONGOING' || initiative.status === 'ongoing') && canUserSubmit(initiative) && (
                        <DropdownMenuItem onClick={() => {
                          setSubmittingInitiative(initiative)
                          setIsSubmissionOpen(true)
                        }}>
                          <FileText className="mr-2 h-4 w-4" />
                          Submit Initiative
                        </DropdownMenuItem>
                      )}

                      {/* Review UNDER_REVIEW initiative */}
                      {(initiative.status === 'UNDER_REVIEW' || initiative.status === 'under_review') && canUserReview(initiative) && (
                        <DropdownMenuItem onClick={() => {
                          setReviewingInitiative(initiative)
                          setIsReviewOpen(true)
                        }}>
                          <Star className="mr-2 h-4 w-4" />
                          Review Initiative
                        </DropdownMenuItem>
                      )}

                      {/* Edit - only for PENDING_APPROVAL or ASSIGNED */}
                      {canUserReview(initiative) && (initiative.status === 'PENDING_APPROVAL' || initiative.status === 'pending_approval' || initiative.status === 'ASSIGNED' || initiative.status === 'assigned') && (
                        <DropdownMenuItem onClick={() => handleEdit(initiative)}>
                          <Edit className="mr-2 h-4 w-4" />
                          Edit
                        </DropdownMenuItem>
                      )}

                      {/* Delete - only for PENDING_APPROVAL or ASSIGNED */}
                      {canUserReview(initiative) && (initiative.status === 'PENDING_APPROVAL' || initiative.status === 'pending_approval' || initiative.status === 'ASSIGNED' || initiative.status === 'assigned') && (
                        <DropdownMenuItem
                          onClick={() => handleDelete(initiative)}
                          className="text-red-600"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Initiatives</h1>
            <p className="text-muted-foreground">
              Manage and track initiative assignments and progress
            </p>
          </div>
          <Button onClick={() => setIsFormOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create Initiative
          </Button>
        </div>

        {/* Search and Filters */}
        <Card className="p-4">
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-4">
              <div className="relative flex-1 max-w-sm">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search initiatives, assignees, or descriptions..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  setSearchTerm("")
                  setStatusFilter("all")
                  setUrgencyFilter("all")
                  setTypeFilter("all")
                }}
                className="whitespace-nowrap"
              >
                <X className="mr-2 h-4 w-4" />
                Clear Filters
              </Button>
            </div>

            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">Filters:</span>
              </div>

              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="PENDING_APPROVAL">Pending Approval</SelectItem>
                  <SelectItem value="ASSIGNED">Assigned</SelectItem>
                  <SelectItem value="PENDING">Pending</SelectItem>
                  <SelectItem value="ONGOING">Ongoing</SelectItem>
                  <SelectItem value="UNDER_REVIEW">Under Review</SelectItem>
                  <SelectItem value="APPROVED">Approved</SelectItem>
                  <SelectItem value="REJECTED">Rejected</SelectItem>
                  <SelectItem value="OVERDUE">Overdue</SelectItem>
                </SelectContent>
              </Select>

              <Select value={urgencyFilter} onValueChange={setUrgencyFilter}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Priority" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Priorities</SelectItem>
                  <SelectItem value="low">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-gray-400"></div>
                      Low
                    </div>
                  </SelectItem>
                  <SelectItem value="medium">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-yellow-400"></div>
                      Medium
                    </div>
                  </SelectItem>
                  <SelectItem value="high">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-orange-400"></div>
                      High
                    </div>
                  </SelectItem>
                  <SelectItem value="urgent">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-red-400"></div>
                      Urgent
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>

              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="individual">Individual</SelectItem>
                  <SelectItem value="group">Group</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </Card>
      </div>

      {/* Statistics */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">My Initiatives</CardTitle>
            <CheckSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{myInitiativesData?.total || 0}</div>
            <p className="text-xs text-muted-foreground">
              Assigned to me
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {myInitiativesRaw.filter(t => t.status === 'approved').length}
            </div>
            <p className="text-xs text-muted-foreground">
              Successfully completed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Overdue</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {myInitiativesRaw.filter(t => t.status === 'overdue').length}
            </div>
            <p className="text-xs text-muted-foreground">
              Past due date
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {myInitiativesRaw.filter(t => t.score).length > 0
                ? (myInitiativesRaw.reduce((sum, t) => sum + (t.score || 0), 0) / myInitiativesRaw.filter(t => t.score).length).toFixed(1)
                : 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground">
              Based on completed initiatives
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Initiative Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full max-w-2xl grid-cols-3">
          <TabsTrigger value="my-initiatives">
            <User className="h-4 w-4 mr-2" />
            My Initiatives ({myInitiativesData?.total || 0})
          </TabsTrigger>
          <TabsTrigger value="supervisee-initiatives">
            <Users className="h-4 w-4 mr-2" />
            Supervisee Initiatives ({superviseeInitiativesData?.length || 0})
          </TabsTrigger>
          <PermissionGuard permission="initiative_view_all">
            <TabsTrigger value="all-initiatives">
              <CheckSquare className="h-4 w-4 mr-2" />
              All Initiatives ({allInitiativesData?.total || 0})
            </TabsTrigger>
          </PermissionGuard>
        </TabsList>

        <TabsContent value="my-initiatives" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>My Initiatives</CardTitle>
              <CardDescription>Initiatives assigned to you</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-3">
                  {[...Array(5)].map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : myInitiatives.length > 0 ? (
                <>
                  <InitiativeTable initiatives={myInitiatives} />
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between mt-4 pt-4 border-t">
                      <div className="text-sm text-muted-foreground">
                        Showing {((currentPage - 1) * perPage) + 1} to {Math.min(currentPage * perPage, totalInitiatives)} of {totalInitiatives} initiatives
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                          disabled={currentPage === 1}
                        >
                          Previous
                        </Button>
                        <div className="text-sm">
                          Page {currentPage} of {totalPages}
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                          disabled={currentPage === totalPages}
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-12">
                  <CheckSquare className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-medium mb-2">No initiatives found</h3>
                  <p className="text-muted-foreground mb-4">
                    You don&rsquo;t have any initiatives yet.
                  </p>
                  <Button onClick={() => setIsFormOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Create Your First Initiative
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="supervisee-initiatives" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Supervisee Initiatives</CardTitle>
              <CardDescription>
                {hasSupervisees
                  ? `Initiatives created by or assigned to your ${superviseeCount} direct report${superviseeCount > 1 ? 's' : ''}`
                  : "You don't have any direct reports yet"
                }
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-3">
                  {[...Array(5)].map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : hasSupervisees && initiatives.length > 0 ? (
                  <div className="space-y-4">
                    {initiatives.map((initiative) => {
                      const isPendingApproval = initiative.status === 'PENDING_APPROVAL'

                      return (
                        <div key={initiative.id} className={cn(
                          "border rounded-lg p-4",
                          isPendingApproval && "border-yellow-300 bg-yellow-50"
                        )}>
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <h3 className="font-semibold">{initiative.title}</h3>
                                <Badge className={statusColors[initiative.status] || statusColors.ASSIGNED}>
                                  {initiative.status?.replace('_', ' ') || 'Unknown'}
                                </Badge>
                              </div>
                              <p className="text-sm text-muted-foreground mb-2">{initiative.description}</p>
                              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                <div className="flex items-center gap-1">
                                  <User className="h-4 w-4" />
                                  <span>{initiative.creator_name || 'Unknown'}</span>
                                </div>
                                <div className="flex items-center gap-1">
                                  <Calendar className="h-4 w-4" />
                                  <span>{new Date(initiative.due_date).toLocaleDateString()}</span>
                                </div>
                                <div className="flex items-center gap-1">
                                  <Users className="h-4 w-4" />
                                  <span>{initiative.assignee_count || 0} assignee(s)</span>
                                </div>
                              </div>
                            </div>
                            <div className="flex gap-2">
                              {isPendingApproval && (
                                <Button
                                  size="sm"
                                  variant="default"
                                  onClick={() => {
                                    setApprovingInitiative(initiative)
                                    setIsApprovalOpen(true)
                                  }}
                                  className="bg-green-600 hover:bg-green-700"
                                >
                                  <Check className="h-4 w-4 mr-1" />
                                  Approve
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  setSelectedInitiative(initiative)
                                  setIsInitiativeDetailOpen(true)
                                }}
                              >
                                <Eye className="h-4 w-4 mr-1" />
                                View
                              </Button>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Users className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <h3 className="text-lg font-medium mb-2">
                      {hasSupervisees ? "No supervisee initiatives" : "No direct reports"}
                    </h3>
                    <p className="text-muted-foreground">
                      {hasSupervisees
                        ? "Your direct reports haven't been assigned any initiatives yet."
                        : "You don't have any team members reporting to you."
                      }
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
        </TabsContent>

        <TabsContent value="all-initiatives" className="space-y-4">
          <PermissionGuard permission="initiative_view_all">
            <Card>
              <CardHeader>
                <CardTitle>All Initiatives</CardTitle>
                <CardDescription>All initiatives in the system (requires initiative_view_all permission)</CardDescription>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-3">
                    {[...Array(5)].map((_, i) => (
                      <Skeleton key={i} className="h-16 w-full" />
                    ))}
                  </div>
                ) : allInitiatives.length > 0 ? (
                  <>
                    <InitiativeTable initiatives={allInitiatives} showActions={false} />
                    {totalPages > 1 && (
                      <div className="flex items-center justify-between mt-4 pt-4 border-t">
                        <div className="text-sm text-muted-foreground">
                          Showing {((currentPage - 1) * perPage) + 1} to {Math.min(currentPage * perPage, totalInitiatives)} of {totalInitiatives} initiatives
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                            disabled={currentPage === 1}
                          >
                            Previous
                          </Button>
                          <div className="text-sm">
                            Page {currentPage} of {totalPages}
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                            disabled={currentPage === totalPages}
                          >
                            Next
                          </Button>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-12">
                    <CheckSquare className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <h3 className="text-lg font-medium mb-2">No initiatives found</h3>
                    <p className="text-muted-foreground">
                      No initiatives have been created in the system yet.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </PermissionGuard>
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      <InitiativeForm
        initiative={editingInitiative}
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        onSubmit={handleCreate}
      />

      <InitiativeDetailModal
        initiative={selectedInitiative}
        isOpen={isInitiativeDetailOpen}
        onClose={() => {
          setIsInitiativeDetailOpen(false)
          setSelectedInitiative(null)
        }}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onUpdateStatus={handleUpdateStatus}
        onSubmit={(initiative) => {
          setSubmittingInitiative(initiative)
          setIsSubmissionOpen(true)
        }}
        onReview={(initiative) => {
          setReviewingInitiative(initiative)
          setIsReviewOpen(true)
        }}
        onApprove={(initiative) => {
          setApprovingInitiative(initiative)
          setIsApprovalOpen(true)
        }}
        canUserSubmit={canUserSubmit}
        canUserReview={canUserReview}
        canUserApprove={canUserApprove}
      />

      <InitiativeSubmissionDialog
        initiative={submittingInitiative}
        isOpen={isSubmissionOpen}
        onClose={() => {
          setIsSubmissionOpen(false)
          setSubmittingInitiative(null)
        }}
        onSubmit={handleSubmit}
      />

      <InitiativeReviewDialog
        initiative={reviewingInitiative}
        isOpen={isReviewOpen}
        onClose={() => {
          setIsReviewOpen(false)
          setReviewingInitiative(null)
        }}
        onSubmit={handleReview}
      />

      <InitiativeApprovalDialog
        initiative={approvingInitiative}
        isOpen={isApprovalOpen}
        onClose={() => {
          setIsApprovalOpen(false)
          setApprovingInitiative(null)
        }}
        onSubmit={handleApproval}
      />
    </div>
  )
}