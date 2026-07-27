"use client"

import React, { useMemo, useState, useCallback, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  MapPin,
  Briefcase,
  Building2,
  Target,
  ListChecks,
  Award,
  TrendingUp,
  Clock,
  CheckCircle2,
  Edit,
  Send,
  Key,
  Trash2,
  MoreVertical,
  Ban,
  CalendarOff,
  Archive,
  UserCheck,
} from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
import { useUser, useGoals, useOrganizations, useRoles, useUpdateUser, useUpdateUserStatus } from "@/lib/react-query"
import { GET, POST, users as usersApi } from "@/lib/api"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { UserForm } from "@/components/dashboard/UserForm"
import { Label } from "@/components/ui/label"
import { SearchableSelect } from "@/components/ui/searchable-select"

const statusColors = {
  PENDING_ACTIVATION: "bg-blue-100 text-blue-800",
  ACTIVE: "bg-green-100 text-green-800",
  SUSPENDED: "bg-red-100 text-red-800",
  ON_LEAVE: "bg-yellow-100 text-yellow-800",
  ARCHIVED: "bg-gray-100 text-gray-800",
}

const statusLabels = {
  PENDING_ACTIVATION: "Pending Activation",
  ACTIVE: "Active",
  SUSPENDED: "Suspended",
  ON_LEAVE: "On Leave",
  ARCHIVED: "Archived",
}

const goalStatusColors = {
  PENDING_APPROVAL: "bg-yellow-100 text-yellow-800",
  ACTIVE: "bg-blue-100 text-blue-800",
  ACHIEVED: "bg-green-100 text-green-800",
  DISCARDED: "bg-gray-100 text-gray-800",
  REJECTED: "bg-red-100 text-red-800",
}

function GoalCard({ goal }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-2 flex-1">
            <CardTitle className="text-base font-semibold">{goal.title}</CardTitle>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge className={goalStatusColors[goal.status] || ""}>
                {goal.status?.replace(/_/g, ' ')}
              </Badge>
              {goal.quarter && goal.year && (
                <Badge variant="outline">{goal.quarter} {goal.year}</Badge>
              )}
              {goal.tags && goal.tags.length > 0 && goal.tags.map((tag) => (
                <Badge key={tag.id} variant="outline" className="text-xs">
                  {tag.name}
                </Badge>
              ))}
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {goal.description && (
          <div
            className="text-sm text-muted-foreground line-clamp-2 prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: goal.description }}
          />
        )}

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Progress</span>
            <span className="font-semibold">{goal.progress_percentage || 0}%</span>
          </div>
          <Progress value={goal.progress_percentage || 0} className="h-2" />
        </div>

        {(goal.start_date || goal.end_date) && (
          <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
            {goal.start_date && (
              <div className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {new Date(goal.start_date).toLocaleDateString()}
              </div>
            )}
            {goal.end_date && (
              <div>Due: {new Date(goal.end_date).toLocaleDateString()}</div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function InitiativeCard({ initiative }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-2 flex-1">
            <CardTitle className="text-base font-semibold">{initiative.title}</CardTitle>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="outline">
                {initiative.status?.replace(/_/g, ' ')}
              </Badge>
              {initiative.urgency && (
                <Badge variant="outline">{initiative.urgency}</Badge>
              )}
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {initiative.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">{initiative.description}</p>
        )}

        {initiative.score && (
          <div className="flex items-center gap-2">
            <Award className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Score: {initiative.score}/10</span>
          </div>
        )}

        {initiative.due_date && (
          <div className="flex items-center gap-1 text-xs text-muted-foreground pt-2 border-t">
            <Clock className="h-3.5 w-3.5" />
            Due: {new Date(initiative.due_date).toLocaleDateString()}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ConfirmDialog({ isOpen, onClose, onConfirm, title, description }) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => {
            onConfirm()
            onClose()
          }}>Confirm</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ChangeSupervisorDialog({ isOpen, onClose, user, onFetchSupervisors }) {
  const [supervisorId, setSupervisorId] = useState("")
  const [supervisors, setSupervisors] = useState([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!isOpen || !user?.organization_id) return
    setLoading(true)
    onFetchSupervisors(user.organization_id, user.level)
      .then(list => setSupervisors(list || []))
      .finally(() => setLoading(false))
    setSupervisorId(user.supervisor_id || "")
  }, [isOpen, user?.id])

  const handleSave = async () => {
    setSaving(true)
    try {
      await usersApi.assignSupervisor(user.id, supervisorId || null)
      queryClient.invalidateQueries({ queryKey: ['users', user.id] })
      toast.success("Supervisor updated successfully")
      onClose()
    } catch (err) {
      toast.error(err.message || "Failed to update supervisor")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>Change Supervisor</DialogTitle>
          <DialogDescription>Select a new supervisor for {user?.name}</DialogDescription>
        </DialogHeader>
        <div className="py-4 space-y-3">
          <Label className="text-sm font-medium">Supervisor</Label>
          {loading ? (
            <div className="text-sm text-muted-foreground">Loading eligible supervisors...</div>
          ) : (
            <SearchableSelect
              value={supervisorId}
              onValueChange={setSupervisorId}
              placeholder="Select supervisor (or leave empty to remove)"
              searchPlaceholder="Search by name..."
              options={supervisors.map(s => ({
                value: s.id,
                label: `${s.name}${s.level ? ` (Grade ${s.level})` : ''}${s.job_title ? ` — ${s.job_title}` : ''}`,
              }))}
            />
          )}
          {supervisorId && supervisors.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Selected: <span className="font-medium text-foreground">
                {supervisors.find(s => s.id === supervisorId)?.name}
              </span>
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving || loading}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function UserDetailPage() {
  const params = useParams()
  const router = useRouter()
  const userId = params.id

  const [confirmDialog, setConfirmDialog] = useState({ isOpen: false, title: '', description: '', onConfirm: () => {} })
  const [isEditFormOpen, setIsEditFormOpen] = useState(false)
  const [isSupervisorDialogOpen, setIsSupervisorDialogOpen] = useState(false)

  const { data: user, isLoading: isLoadingUser } = useUser(userId)
  const { data: userGoals = [], isLoading: isLoadingGoals } = useGoals({ owner_id: userId })
  const { data: organizations = [] } = useOrganizations()
  const { data: roles = [] } = useRoles()
  const updateMutation = useUpdateUser()
  const updateStatusMutation = useUpdateUserStatus()

  // Get user's organization
  const organization = user?.organization_name || user?.organization?.name || "Unknown"

  // Calculate statistics
  const stats = useMemo(() => {
    const totalGoals = userGoals.length
    const activeGoals = userGoals.filter(g => g.status === 'ACTIVE').length
    const achievedGoals = userGoals.filter(g => g.status === 'ACHIEVED').length
    const avgProgress = totalGoals > 0
      ? Math.round(userGoals.reduce((sum, g) => sum + (g.progress_percentage || 0), 0) / totalGoals)
      : 0

    return { totalGoals, activeGoals, achievedGoals, avgProgress }
  }, [userGoals])

  // Fetch eligible supervisors from backend
  const fetchEligibleSupervisors = useCallback(async (organizationId, userLevel) => {
    if (!organizationId) return []
    try {
      const supervisors = await GET(`/api/users/${userId}/potential-supervisors`)
      return (supervisors || []).map(u => ({
        id: u.id,
        name: u.name || [u.first_name, u.middle_name, u.last_name].filter(Boolean).join(' '),
        level: u.level,
        job_title: u.job_title,
      }))
    } catch {
      return []
    }
  }, [userId])

  // Action handlers
  const handleStatusChange = (newStatus) => {
    if (!user) return
    updateStatusMutation.mutate({ id: user.id, status: newStatus })
  }

  const handleEditUser = () => {
    setIsEditFormOpen(true)
  }

  const handleUpdate = (data) => {
    if (user) {
      updateMutation.mutate({ id: user.id, ...data })
    }
  }


  const handleResendInvite = () => {
    if (!user) return
    setConfirmDialog({
      isOpen: true,
      title: 'Resend Onboarding Invite',
      description: `Send a new onboarding invite to ${user.email}?`,
      onConfirm: () => {
        toast.promise(
          POST(`/api/users/${user.id}/resend-onboarding`, {}),
          {
            loading: `Sending onboarding email to ${user.email}...`,
            success: `Onboarding email sent to ${user.email}`,
            error: (err) => err.message || 'Failed to send onboarding email',
          }
        )
      }
    })
  }

  const handleSendPasswordReset = () => {
    if (!user) return
    setConfirmDialog({
      isOpen: true,
      title: 'Send Password Reset Link',
      description: `Send a password reset link to ${user.email}?`,
      onConfirm: () => {
        toast.promise(
          POST(`/api/users/${user.id}/send-password-reset`, {}),
          {
            loading: `Sending password reset email to ${user.email}...`,
            success: `Password reset email sent to ${user.email}`,
            error: (err) => err.message || 'Failed to send password reset email',
          }
        )
      }
    })
  }

  const handleDeleteUser = () => {
    if (!user) return
    setConfirmDialog({
      isOpen: true,
      title: 'Delete User Permanently',
      description: `Are you sure you want to permanently delete ${user.name} (${user.email})? This action cannot be undone and will remove all associated data.`,
      onConfirm: () => {
        toast.promise(
          import('@/lib/api').then(({ DELETE }) => DELETE(`/api/users/${user.id}`)).then(() => router.push('/dashboard/users')),
          {
            loading: `Deleting ${user.name}...`,
            success: `${user.name} has been permanently deleted`,
            error: (err) => err.message || 'Failed to delete user. They may have associated data that must be removed first.',
          }
        )
      }
    })
  }

  if (isLoadingUser || isLoadingGoals) {
    return (
      <div className="space-y-8">
        <Skeleton className="h-12 w-64" />
        <div className="grid gap-6 md:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-96" />
      </div>
    )
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center h-96">
        <User className="h-16 w-16 text-muted-foreground mb-4" />
        <h2 className="text-2xl font-bold mb-2">User Not Found</h2>
        <p className="text-muted-foreground mb-4">The user you&apos;re looking for doesn&apos;t exist.</p>
        <Button onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Go Back
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b pb-6">
        <Button
          variant="ghost"
          onClick={() => router.back()}
          className="mb-4"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>

        <div className="flex items-start gap-6">
          <Avatar className="h-24 w-24">
            <AvatarFallback className="text-2xl">
              {user.name.split(' ').map(n => n[0]).join('').toUpperCase()}
            </AvatarFallback>
          </Avatar>

          <div className="flex-1 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-3xl font-bold">{user.name}</h1>
                <p className="text-lg text-muted-foreground">{user.job_title || 'No title'}</p>
              </div>

              {/* Action Buttons */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onPointerDown={(e) => e.stopPropagation()}
                  >
                    <MoreVertical className="h-4 w-4 mr-2" />
                    Actions
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={handleEditUser}>
                    <Edit className="mr-2 h-4 w-4" />
                    Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setIsSupervisorDialogOpen(true)}>
                    <User className="mr-2 h-4 w-4" />
                    Change Supervisor
                  </DropdownMenuItem>

                  {/* Status Actions */}
                  {user.status === 'ACTIVE' ? (
                    <>
                      <DropdownMenuItem onClick={handleSendPasswordReset}>
                        <Key className="mr-2 h-4 w-4" />
                        Send Password Reset
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleStatusChange('SUSPENDED')}>
                        <Ban className="mr-2 h-4 w-4" />
                        Suspend
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleStatusChange('ON_LEAVE')}>
                        <CalendarOff className="mr-2 h-4 w-4" />
                        Mark as On Leave
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleStatusChange('ARCHIVED')}>
                        <Archive className="mr-2 h-4 w-4" />
                        Archive
                      </DropdownMenuItem>
                    </>
                  ) : user.status === 'PENDING_ACTIVATION' ? (
                    <>
                      <DropdownMenuItem onClick={handleResendInvite}>
                        <Send className="mr-2 h-4 w-4" />
                        Resend Invite Link
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleStatusChange('ARCHIVED')}>
                        <Archive className="mr-2 h-4 w-4" />
                        Archive
                      </DropdownMenuItem>
                    </>
                  ) : (
                    <>
                      <DropdownMenuItem onClick={() => handleStatusChange('ACTIVE')}>
                        <UserCheck className="mr-2 h-4 w-4" />
                        Reactivate
                      </DropdownMenuItem>
                      {user.status !== 'ARCHIVED' && (
                        <DropdownMenuItem onClick={() => handleStatusChange('ARCHIVED')}>
                          <Archive className="mr-2 h-4 w-4" />
                          Archive
                        </DropdownMenuItem>
                      )}
                    </>
                  )}

                  {/* Delete Option */}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={handleDeleteUser}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete Permanently
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {user.email && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Mail className="h-4 w-4" />
                  <span>{user.email}</span>
                </div>
              )}
              {user.phone && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Phone className="h-4 w-4" />
                  <span>{user.phone}</span>
                </div>
              )}
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Building2 className="h-4 w-4" />
                <span>{organization}</span>
              </div>
              {user.supervisor_name && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <User className="h-4 w-4" />
                  <span>Reports to: {user.supervisor_name}</span>
                </div>
              )}
              {user.level && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Briefcase className="h-4 w-4" />
                  <span>Level: {user.level}</span>
                </div>
              )}
              <div className="flex items-center gap-2 text-sm">
                <Badge className={statusColors[user.status] || ""}>
                  {statusLabels[user.status] || user.status}
                </Badge>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Goals</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalGoals}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Active Goals</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.activeGoals}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Achieved Goals</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.achievedGoals}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Avg Progress</CardTitle>
            <Award className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.avgProgress}%</div>
          </CardContent>
        </Card>
      </div>

      {/* Account Information */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Account Information</CardTitle>
          <CardDescription>Organization and role details</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-muted-foreground text-xs">Email</Label>
              <p className="font-medium text-sm mt-0.5">{user.email}</p>
            </div>
            <div>
              <Label className="text-muted-foreground text-xs">Job Title</Label>
              <p className="font-medium text-sm mt-0.5">{user.job_title || 'Not set'}</p>
            </div>
            <div>
              <Label className="text-muted-foreground text-xs">Organization</Label>
              <p className="font-medium text-sm mt-0.5">{user.organization_name || organization}</p>
            </div>
            <div>
              <Label className="text-muted-foreground text-xs">Role</Label>
              <p className="font-medium text-sm mt-0.5">{user.role_name || 'Not set'}</p>
            </div>
            <div>
              <Label className="text-muted-foreground text-xs">Grade Level</Label>
              <p className="font-medium text-sm mt-0.5">{user.level || 'Not set'}</p>
            </div>
            <div>
              <Label className="text-muted-foreground text-xs">Status</Label>
              <p className="font-medium text-sm mt-0.5 capitalize">{user.status?.replace(/_/g, ' ')}</p>
            </div>
            <div className="md:col-span-2">
              <div className="flex items-center justify-between">
                <Label className="text-muted-foreground text-xs">Supervisor</Label>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs px-2"
                  onClick={() => setIsSupervisorDialogOpen(true)}
                >
                  <Edit className="h-3 w-3 mr-1" />
                  Change
                </Button>
              </div>
              <p className="font-medium text-sm mt-0.5">
                {user.supervisor_name || <span className="text-muted-foreground italic">No supervisor assigned</span>}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Additional Info */}
      {(user.skillset || user.address) && (
        <Card>
          <CardHeader>
            <CardTitle>Additional Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {user.skillset && (
              <div>
                <h3 className="font-semibold text-sm mb-2">Skillset</h3>
                <p className="text-sm text-muted-foreground">{user.skillset}</p>
              </div>
            )}
            {user.address && (
              <div>
                <h3 className="font-semibold text-sm mb-2 flex items-center gap-2">
                  <MapPin className="h-4 w-4" />
                  Address
                </h3>
                <p className="text-sm text-muted-foreground">{user.address}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tabs for Goals and Initiatives */}
      <Tabs defaultValue="goals" className="space-y-6">
        <TabsList>
          <TabsTrigger value="goals" className="flex items-center gap-2">
            <Target className="h-4 w-4" />
            Goals ({userGoals.length})
          </TabsTrigger>
          <TabsTrigger value="initiatives" className="flex items-center gap-2">
            <ListChecks className="h-4 w-4" />
            Initiatives
          </TabsTrigger>
        </TabsList>

        <TabsContent value="goals" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Goals</CardTitle>
              <CardDescription>
                All goals assigned to or created by this user
              </CardDescription>
            </CardHeader>
            <CardContent>
              {userGoals.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {userGoals.map((goal) => (
                    <GoalCard key={goal.id} goal={goal} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Target className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No goals yet</h3>
                  <p className="text-muted-foreground">This user hasn&apos;t created any goals yet.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="initiatives" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Initiatives</CardTitle>
              <CardDescription>
                All initiatives assigned to this user
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-12">
                <ListChecks className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">Coming soon</h3>
                <p className="text-muted-foreground">Initiative tracking will be available here.</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit User Form Dialog */}
      <UserForm
        user={user}
        isOpen={isEditFormOpen}
        onClose={() => setIsEditFormOpen(false)}
        onSubmit={handleUpdate}
        organizations={organizations}
        roles={roles}
        onFetchSupervisors={fetchEligibleSupervisors}
      />

      {/* Change Supervisor Dialog */}
      <ChangeSupervisorDialog
        isOpen={isSupervisorDialogOpen}
        onClose={() => setIsSupervisorDialogOpen(false)}
        user={user}
        onFetchSupervisors={fetchEligibleSupervisors}
      />

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        onClose={() => setConfirmDialog(prev => ({ ...prev, isOpen: false }))}
        onConfirm={confirmDialog.onConfirm}
        title={confirmDialog.title}
        description={confirmDialog.description}
      />
    </div>
  )
}
