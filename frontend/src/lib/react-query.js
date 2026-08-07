'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { toast } from 'sonner'
import { tokenUtils } from './api'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 10, // 10 minutes (was cacheTime)
      retry: (failureCount, error) => {
        // Don't retry on authentication errors
        if (error?.status === 401 || error?.status === 403) {
          // Handle authentication errors for queries
          handleAuthError(error)
          return false
        }
        return failureCount < 2
      },
      refetchOnWindowFocus: false,
      onError: (error) => {
        // Handle authentication errors globally for queries
        if (error?.status === 401) {
          handleAuthError(error)
        }
      },
    },
    mutations: {
      onError: (error) => {
        // Handle authentication errors globally
        if (error?.status === 401) {
          handleAuthError(error)
          return
        }

        // Show error toast for other errors
        let message = 'An error occurred'

        if (typeof error === 'string') {
          message = error
        } else if (error?.message) {
          message = error.message
        } else if (error?.data?.detail) {
          message = error.data.detail
        } else if (error?.data?.message) {
          message = error.data.message
        } else if (error?.detail) {
          message = error.detail
        }

        console.error('Mutation error:', error)
        toast.error(message)
      },
    },
  },
})

// Helper function to handle authentication errors
function handleAuthError(error) {
  console.log('🔐 Authentication error detected, logging out user')

  // Clear all authentication data
  tokenUtils.removeToken()
  tokenUtils.clearSessionData()

  // Clear React Query cache to prevent stale data
  queryClient.clear()

  // Show user-friendly message
  toast.error('Your session has expired. Please log in again.')

  // Redirect to login page
  window.location.href = '/login'
}

export function ReactQueryProvider({ children }) {
  // Make query client globally accessible for logout cleanup
  if (typeof window !== 'undefined') {
    window.__REACT_QUERY_CLIENT__ = queryClient
  }

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}

export { queryClient }

// Custom hooks for API calls
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { auth, users, organizations, roles, goals, goalTags, initiatives, tasks, notifications } from './api'

// Query keys
export const QUERY_KEYS = {
  // Auth
  ME: ['me'],

  // Users
  USERS: ['users'],
  USER: (id) => ['users', id],
  USER_HISTORY: (id) => ['users', id, 'history'],

  // Organizations
  ORGANIZATIONS: ['organizations'],
  ORGANIZATION: (id) => ['organizations', id],
  ORGANIZATION_CHILDREN: (id) => ['organizations', id, 'children'],

  // Roles
  ROLES: ['roles'],
  ROLE: (id) => ['roles', id],
  PERMISSIONS: ['permissions'],

  // Goals
  GOALS: ['goals'],
  GOAL: (id) => ['goals', id],
  GOAL_CHILDREN: (id) => ['goals', id, 'children'],

  // Initiatives (formerly tasks)
  INITIATIVES: ['initiatives'],
  INITIATIVE: (id) => ['initiatives', id],
  INITIATIVE_SUBMISSIONS: (id) => ['initiatives', id, 'submissions'],
  INITIATIVE_SUBTASKS: (id) => ['initiatives', id, 'subtasks'],

  // Notifications
  NOTIFICATIONS: ['notifications'],
  NOTIFICATION_STATS: ['notifications', 'stats'],

  // Backward compatibility aliases
  TASKS: ['initiatives'],
  TASK: (id) => ['initiatives', id],
  TASK_SUBMISSIONS: (id) => ['initiatives', id, 'submissions'],
}

// Auth hooks
export function useMe() {
  return useQuery({
    queryKey: QUERY_KEYS.ME,
    queryFn: auth.me,
    enabled: tokenUtils.isAuthenticated(),
  })
}

// User hooks
export function useUsers(params = {}) {
  return useQuery({
    queryKey: [...QUERY_KEYS.USERS, params],
    queryFn: () => users.list(params),
  })
}

export function useMySupervisees(options = {}) {
  return useQuery({
    queryKey: ['users', 'supervisees', 'me'],
    queryFn: users.getMySupervisees,
    ...options,
  })
}

export function useUser(id) {
  return useQuery({
    queryKey: QUERY_KEYS.USER(id),
    queryFn: () => users.get(id),
    enabled: !!id,
  })
}

export function useUserHistory(id) {
  return useQuery({
    queryKey: QUERY_KEYS.USER_HISTORY(id),
    queryFn: () => users.getHistory(id),
    enabled: !!id,
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: users.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USERS })
      toast.success('User created successfully')
    },
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => users.update(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USERS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USER(variables.id) })
      toast.success('User updated successfully')
    },
  })
}

export function useUpdateUserStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, status }) => users.updateStatus(id, status),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USERS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.USER(variables.id) })
      toast.success('User status updated successfully')
    },
  })
}

// Organization hooks
export function useOrganizations(params = {}) {
  return useQuery({
    queryKey: [...QUERY_KEYS.ORGANIZATIONS, params],
    queryFn: () => organizations.list(params),
    select: (data) => Array.isArray(data) ? data : (data?.organizations || []),
  })
}

// Flat list pre-grouped by level — single fetch, client-side derived
export function useOrganizationsByLevel() {
  return useQuery({
    queryKey: QUERY_KEYS.ORGANIZATIONS,
    queryFn: () => organizations.list(),
    select: (data) => {
      const all = Array.isArray(data) ? data : (data?.organizations || [])
      return {
        all,
        directorates: all.filter(o => o.level?.toUpperCase() === 'DIRECTORATE'),
        departments:  all.filter(o => o.level?.toUpperCase() === 'DEPARTMENT'),
        divisions:    all.filter(o => o.level?.toUpperCase() === 'DIVISION'),
        units:        all.filter(o => o.level?.toUpperCase() === 'UNIT'),
      }
    },
  })
}

export function useOrganizationTree() {
  return useQuery({
    queryKey: ['organization', 'tree'],
    queryFn: organizations.getTree,
  })
}

export function useOrganization(id) {
  const { data: organizationsList } = useOrganizations()

  return useQuery({
    queryKey: QUERY_KEYS.ORGANIZATION(id),
    queryFn: () => {
      // Find the organization from the list since there's no individual GET endpoint
      const organization = organizationsList?.find(org => org.id === id)
      if (!organization) {
        throw new Error('Organization not found')
      }
      return organization
    },
    enabled: !!id && !!organizationsList,
  })
}

export function useOrganizationChildren(id) {
  return useQuery({
    queryKey: QUERY_KEYS.ORGANIZATION_CHILDREN(id),
    queryFn: () => organizations.getChildren(id),
    enabled: !!id,
  })
}

export function useOrganizationStats() {
  return useQuery({
    queryKey: ['organization', 'stats'],
    queryFn: organizations.getStats,
  })
}

export function useCreateOrganization() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: organizations.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ORGANIZATIONS })
      toast.success('Organization created successfully')
    },
  })
}

export function useUpdateOrganization() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => organizations.update(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ORGANIZATIONS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ORGANIZATION(variables.id) })
      toast.success('Organization updated successfully')
    },
  })
}

export function useDeleteOrganization() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: organizations.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ORGANIZATIONS })
      toast.success('Organization deleted successfully')
    },
  })
}

// Role hooks
export function useRoles() {
  return useQuery({
    queryKey: QUERY_KEYS.ROLES,
    queryFn: roles.list,
  })
}

export function useRole(id) {
  return useQuery({
    queryKey: QUERY_KEYS.ROLE(id),
    queryFn: () => roles.get(id),
    enabled: !!id,
  })
}

export function usePermissions() {
  return useQuery({
    queryKey: QUERY_KEYS.PERMISSIONS,
    queryFn: roles.getPermissions,
  })
}

export function useCreateRole() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: roles.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ROLES })
      toast.success('Role created successfully')
    },
  })
}

export function useUpdateRole() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => roles.update(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ROLES })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ROLE(variables.id) })
      toast.success('Role updated successfully')
    },
  })
}

export function useDeleteRole() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: roles.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ROLES })
      toast.success('Role deleted successfully')
    },
  })
}

// Goal hooks
// Returns flat array of goals (backward compat)
export function useGoals(params = {}) {
  return useQuery({
    queryKey: [...QUERY_KEYS.GOALS, params],
    queryFn: () => goals.list(params),
    select: (data) => data?.goals || [],
  })
}

// Returns full paginated response: { goals, total, page, per_page, total_pages }
export function useGoalsPaginated(params = {}) {
  return useQuery({
    queryKey: [...QUERY_KEYS.GOALS, params],
    queryFn: () => goals.list(params),
  })
}

export function useGoalStats() {
  return useQuery({
    queryKey: ['goals', 'stats'],
    queryFn: () => goals.stats(),
  })
}

export function useGoal(id) {
  return useQuery({
    queryKey: QUERY_KEYS.GOAL(id),
    queryFn: () => goals.get(id),
    enabled: !!id,
  })
}

export function useGoalChildren(id) {
  return useQuery({
    queryKey: QUERY_KEYS.GOAL_CHILDREN(id),
    queryFn: () => goals.getChildren(id),
    enabled: !!id,
  })
}

export function useCreateGoal() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: goals.create,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      await queryClient.refetchQueries({ queryKey: QUERY_KEYS.GOALS })
      toast.success('Goal created successfully')
    },
  })
}

export function useUpdateGoal() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => goals.update(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOAL(variables.id) })
      toast.success('Goal updated successfully')
    },
  })
}

export function useUpdateGoalProgress() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => goals.updateProgress(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOAL(variables.id) })
      toast.success('Goal progress updated successfully')
    },
  })
}

export function useUpdateGoalStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => goals.updateStatus(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOAL(variables.id) })
      toast.success('Goal status updated successfully')
    },
  })
}

export function useDeleteGoal() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: goals.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      toast.success('Goal deleted successfully')
    },
  })
}

export function useAssessGoal() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => goals.assess(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOAL(variables.id) })
      toast.success('Goal assessment submitted')
    },
  })
}

export function useSupervisorScore() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => goals.supervisorScore(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOAL(variables.id) })
      toast.success('Goal scored successfully')
    },
  })
}

export function useApproveGoal() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => goals.approve(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOAL(variables.id) })
      toast.success(variables.approved ? 'Goal approved successfully' : 'Goal rejected')
    },
  })
}

export function useFreezeGoalsQuarter() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: goals.freezeQuarter,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      toast.success(data.message || 'Goals frozen successfully')
    },
  })
}

export function useUnfreezeGoalsQuarter() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: goals.unfreezeQuarter,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      toast.success(data.message || 'Goals unfrozen successfully')
    },
  })
}

export function useGoalFreezeLogs() {
  return useQuery({
    queryKey: ['goals', 'freeze-logs'],
    queryFn: goals.getFreezeLogs,
  })
}

export function useSuperviseeGoals(options = {}) {
  return useQuery({
    queryKey: ['goals', 'supervisees'],
    queryFn: goals.getSuperviseeGoals,
    ...options,
  })
}

export function useCreateGoalForSupervisee() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: goals.createForSupervisee,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      await queryClient.invalidateQueries({ queryKey: ['goals', 'supervisees'] })
      await queryClient.refetchQueries({ queryKey: QUERY_KEYS.GOALS })
      await queryClient.refetchQueries({ queryKey: ['goals', 'supervisees'] })
      toast.success('Goal created for team member successfully')
    },
  })
}

export function useRespondToGoal() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => goals.respond(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOAL(variables.id) })
      toast.success(variables.accepted ? 'Goal accepted successfully' : 'Goal declined')
    },
  })
}

export function useRequestGoalChange() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, changeRequest }) => goals.requestChange(id, changeRequest),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOAL(variables.id) })
      toast.success('Change request submitted successfully')
    },
  })
}

export function useFreezeGoal() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, reason }) => goals.freezeGoal(id, reason),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOAL(variables.id) })
      toast.success('Goal frozen successfully')
    },
  })
}

export function useUnfreezeGoal() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, reason }) => goals.unfreezeGoal(id, reason),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOAL(variables.id) })
      toast.success('Goal unfrozen successfully')
    },
  })
}

// Goal Tags hooks
export function useGoalTags() {
  return useQuery({
    queryKey: ['goal-tags'],
    queryFn: goalTags.list,
  })
}

export function useCreateGoalTag() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: goalTags.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal-tags'] })
      toast.success('Tag created successfully')
    },
  })
}

export function useUpdateGoalTag() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...tag }) => goalTags.update(id, tag),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal-tags'] })
      toast.success('Tag updated successfully')
    },
  })
}

export function useDeleteGoalTag() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: goalTags.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal-tags'] })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.GOALS })
      toast.success('Tag deleted successfully')
    },
  })
}

// Initiative hooks (formerly tasks)
export function useInitiatives(params = {}) {
  return useQuery({
    queryKey: [...QUERY_KEYS.INITIATIVES, params],
    queryFn: () => initiatives.list(params),
  })
}

export function useSuperviseeInitiatives() {
  return useQuery({
    queryKey: ['initiatives', 'supervisees'],
    queryFn: initiatives.getSuperviseeInitiatives,
    staleTime: 0, // Always fetch fresh data
  })
}

export function useAssignableUsers() {
  return useQuery({
    queryKey: ['initiatives', 'assignable-users'],
    queryFn: initiatives.getAssignableUsers,
    staleTime: 1000 * 60 * 2, // Cache for 2 minutes
  })
}

export function useHasSupervisees() {
  return useQuery({
    queryKey: ['initiatives', 'has-supervisees'],
    queryFn: initiatives.hasSupervisees,
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
  })
}

export function useInitiativeStats() {
  return useQuery({
    queryKey: ['initiatives', 'stats'],
    queryFn: () => initiatives.stats(),
  })
}

export function useInitiative(id) {
  return useQuery({
    queryKey: QUERY_KEYS.INITIATIVE(id),
    queryFn: () => initiatives.get(id),
    enabled: !!id,
  })
}

export function useInitiativeSubmissions(id) {
  return useQuery({
    queryKey: QUERY_KEYS.INITIATIVE_SUBMISSIONS(id),
    queryFn: () => initiatives.getSubmissions(id),
    enabled: !!id,
  })
}

export function useCreateInitiative() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: initiatives.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVES })
      toast.success('Initiative created successfully')
    },
  })
}

export function useUpdateInitiative() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => initiatives.update(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVES })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(variables.id) })
      toast.success('Initiative updated successfully')
    },
  })
}

export function useApproveInitiative() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => initiatives.approve(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVES })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(variables.id) })
      queryClient.invalidateQueries({ queryKey: ['initiatives', 'supervisees'] })
      toast.success('Initiative approval processed successfully')
    },
  })
}

export function useAcceptInitiative() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id) => initiatives.accept(id),
    onSuccess: (data, id) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVES })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(id) })
      toast.success('Initiative accepted successfully')
    },
  })
}

export function useStartInitiative() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id) => initiatives.start(id),
    onSuccess: (data, id) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVES })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(id) })
      toast.success('Initiative started successfully')
    },
  })
}

export function useCompleteInitiative() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id) => initiatives.complete(id),
    onSuccess: (data, id) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVES })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(id) })
      queryClient.invalidateQueries({ queryKey: ['initiatives', 'supervisees'] })
      toast.success('Initiative completed and sent for review')
    },
  })
}

export function useUpdateInitiativeStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, status }) => initiatives.updateStatus(id, status),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVES })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(variables.id) })
      toast.success('Initiative status updated successfully')
    },
  })
}

export function useSubmitInitiative() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => initiatives.submit(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVES })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(variables.id) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE_SUBMISSIONS(variables.id) })
      toast.success('Initiative submitted successfully')
    },
  })
}

export function useReviewInitiative() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => initiatives.review(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVES })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(variables.id) })
      toast.success('Initiative reviewed successfully')
    },
  })
}

export function useRequestInitiativeExtension() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, ...data }) => initiatives.requestExtension(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(variables.id) })
      toast.success('Extension request submitted successfully')
    },
  })
}

export function useHandleInitiativeExtension() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, extensionId, ...data }) => initiatives.handleExtension(id, extensionId, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(variables.id) })
      toast.success('Extension request handled successfully')
    },
  })
}

export function useDeleteInitiative() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: initiatives.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVES })
      toast.success('Initiative deleted successfully')
    },
  })
}

// Backward compatibility aliases
export const useTasks = useInitiatives
export const useTaskStats = useInitiativeStats
export const useTask = useInitiative
export const useTaskSubmissions = useInitiativeSubmissions
export const useCreateTask = useCreateInitiative
export const useUpdateTaskStatus = useUpdateInitiativeStatus
export const useSubmitTask = useSubmitInitiative
export const useReviewTask = useReviewInitiative
export const useRequestTaskExtension = useRequestInitiativeExtension
export const useHandleTaskExtension = useHandleInitiativeExtension
export const useDeleteTask = useDeleteInitiative

// ============================================
// INITIATIVE SUB-TASKS
// ============================================

export function useInitiativeSubTasks(initiativeId) {
  return useQuery({
    queryKey: QUERY_KEYS.INITIATIVE_SUBTASKS(initiativeId),
    queryFn: () => initiatives.getSubTasks(initiativeId),
    enabled: !!initiativeId,
  })
}

export function useCreateSubTask() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ initiativeId, subTask }) => initiatives.createSubTask(initiativeId, subTask),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE_SUBTASKS(variables.initiativeId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(variables.initiativeId) })
      toast.success('Sub-task created successfully')
    },
  })
}

export function useUpdateSubTask() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ initiativeId, subTaskId, subTask }) =>
      initiatives.updateSubTask(initiativeId, subTaskId, subTask),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE_SUBTASKS(variables.initiativeId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(variables.initiativeId) })
      toast.success('Sub-task updated successfully')
    },
  })
}

export function useDeleteSubTask() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ initiativeId, subTaskId }) => initiatives.deleteSubTask(initiativeId, subTaskId),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE_SUBTASKS(variables.initiativeId) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE(variables.initiativeId) })
      toast.success('Sub-task deleted successfully')
    },
  })
}

export function useReorderSubTasks() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ initiativeId, subTaskIds }) => initiatives.reorderSubTasks(initiativeId, subTaskIds),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INITIATIVE_SUBTASKS(variables.initiativeId) })
      toast.success('Sub-tasks reordered successfully')
    },
  })
}

// ============================================
// NOTIFICATIONS
// ============================================

export function useNotificationsQuery(params = {}) {
  return useQuery({
    queryKey: [...QUERY_KEYS.NOTIFICATIONS, params],
    queryFn: () => notifications.getAll(params),
  })
}

// Alias for useNotificationsQuery
export const useNotifications = useNotificationsQuery

export function useNotificationStats() {
  return useQuery({
    queryKey: QUERY_KEYS.NOTIFICATION_STATS,
    queryFn: notifications.getStats,
    refetchInterval: 30000, // Refresh every 30 seconds — keeps badge in sync
  })
}

export function useMarkNotificationAsRead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: notifications.markAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.NOTIFICATIONS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.NOTIFICATION_STATS })
    },
  })
}

export function useMarkAllNotificationsAsRead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: notifications.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.NOTIFICATIONS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.NOTIFICATION_STATS })
      toast.success('All notifications marked as read')
    },
  })
}

export function useDeleteNotification() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: notifications.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.NOTIFICATIONS })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.NOTIFICATION_STATS })
      toast.success('Notification deleted')
    },
  })
}