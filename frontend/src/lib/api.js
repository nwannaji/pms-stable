import Cookies from 'js-cookie'

/**
 * API configuration and base settings
 */
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? ''
const TOKEN_COOKIE_NAME = 'auth_token'
const REFRESH_TOKEN_COOKIE_NAME = 'refresh_token'
const TOKEN_EXPIRY_DAYS = 1  // Access token cookie expiry (1 day)
const REFRESH_TOKEN_EXPIRY_DAYS = 7  // Refresh token cookie expiry (7 days)

/**
 * Custom API Error class for handling API-specific errors
 */
class ApiError extends Error {
  constructor(message, status, data = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

/**
 * Detect if the current page is served over HTTPS.
 * Accounts for reverse proxies that terminate SSL (checks X-Forwarded-Proto).
 */
const isSecureContext = typeof window !== 'undefined' &&
  (window.location.protocol === 'https:' ||
   window.location.hostname === 'localhost' ||
   window.location.hostname === '127.0.0.1')

const COOKIE_OPTIONS = {
  secure: isSecureContext,
  sameSite: 'lax'
}

/**
 * Fallback storage key when cookies fail (e.g. large JWT exceeding 4KB limit)
 */
const AUTH_TOKEN_LS_KEY = 'auth_token_fallback'
const REFRESH_TOKEN_LS_KEY = 'refresh_token_fallback'

/**
 * Get authentication token — checks cookie first, then localStorage fallback
 * @returns {string|null} JWT token or null if not found
 */
function getAuthToken() {
  return Cookies.get(TOKEN_COOKIE_NAME) || localStorage.getItem(AUTH_TOKEN_LS_KEY) || null
}

/**
 * Set authentication token in cookies with localStorage fallback
 * @param {string} token - JWT token to store
 */
function setAuthToken(token) {
  Cookies.set(TOKEN_COOKIE_NAME, token, {
    expires: TOKEN_EXPIRY_DAYS,
    ...COOKIE_OPTIONS
  })

  // Verify cookie was actually set — browsers silently reject cookies that
  // exceed ~4KB or that fail the secure flag (e.g. behind SSL-terminating proxies)
  if (!Cookies.get(TOKEN_COOKIE_NAME)) {
    localStorage.setItem(AUTH_TOKEN_LS_KEY, token)
  } else {
    // Cookie worked — clear any stale localStorage fallback
    localStorage.removeItem(AUTH_TOKEN_LS_KEY)
  }
}

/**
 * Remove authentication token from cookies and localStorage fallback
 */
function removeAuthToken() {
  Cookies.remove(TOKEN_COOKIE_NAME, COOKIE_OPTIONS)
  localStorage.removeItem(AUTH_TOKEN_LS_KEY)
}

/**
 * Get refresh token — checks cookie first, then localStorage fallback
 * @returns {string|null} Refresh token or null if not found
 */
function getRefreshToken() {
  return Cookies.get(REFRESH_TOKEN_COOKIE_NAME) || localStorage.getItem(REFRESH_TOKEN_LS_KEY) || null
}

/**
 * Set refresh token in cookies with localStorage fallback
 * @param {string} token - Refresh token to store
 */
function setRefreshToken(token) {
  Cookies.set(REFRESH_TOKEN_COOKIE_NAME, token, {
    expires: REFRESH_TOKEN_EXPIRY_DAYS,
    ...COOKIE_OPTIONS
  })

  if (!Cookies.get(REFRESH_TOKEN_COOKIE_NAME)) {
    localStorage.setItem(REFRESH_TOKEN_LS_KEY, token)
  } else {
    localStorage.removeItem(REFRESH_TOKEN_LS_KEY)
  }
}

/**
 * Remove refresh token from cookies and localStorage fallback
 */
function removeRefreshToken() {
  Cookies.remove(REFRESH_TOKEN_COOKIE_NAME, COOKIE_OPTIONS)
  localStorage.removeItem(REFRESH_TOKEN_LS_KEY)
}

/**
 * Flag to prevent multiple simultaneous refresh attempts
 */
let isRefreshing = false
let refreshPromise = null

/**
 * Create headers for API requests
 * @param {boolean} includeAuth - Whether to include authentication header
 * @returns {Object} Headers object
 */
function createHeaders(includeAuth = true) {
  const headers = {
    'Content-Type': 'application/json'
  }

  if (includeAuth) {
    const token = getAuthToken()
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
  }

  return headers
}

/**
 * Try to refresh the access token using the refresh token
 * @returns {Promise<boolean>} True if refresh was successful
 */
async function tryRefreshToken() {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    return false
  }

  // Prevent multiple simultaneous refresh attempts
  if (isRefreshing) {
    return refreshPromise
  }

  isRefreshing = true
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ refresh_token: refreshToken })
      })

      if (response.ok) {
        const data = await response.json()
        if (data.access_token) {
          setAuthToken(data.access_token)
        }
        if (data.refresh_token) {
          setRefreshToken(data.refresh_token)
        }
        // Update session data with new permissions if provided
        if (data.permissions) {
          const sessionData = tokenUtils.getSessionData()
          if (sessionData) {
            sessionData.permissions = data.permissions
            sessionData.scope = data.scope
            tokenUtils.setSessionData(sessionData)
          }
        }
        return true
      }
      return false
    } catch (error) {
      console.error('Token refresh failed:', error)
      return false
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()

  return refreshPromise
}

/**
 * Handle API response and errors
 * @param {Response} response - Fetch response object
 * @param {Object} options - Original request options for retry
 * @param {string} endpoint - Original endpoint for retry
 * @returns {Promise<Object>} Parsed response data
 * @throws {ApiError} Throws ApiError for non-successful responses
 */
async function handleResponse(response, options = {}, endpoint = '') {
  const contentType = response.headers.get('content-type')
  const isJson = contentType && contentType.includes('application/json')

  let data = null
  if (isJson) {
    data = await response.json()
  } else {
    data = await response.text()
  }

  if (!response.ok) {
    // Handle 401 Unauthorized - try refresh token first
    // Skip for auth endpoints (login, onboard, reset-password) - those should just throw the error
    const isAuthEndpoint = endpoint.includes('/auth/login') || endpoint.includes('/auth/onboard') || endpoint.includes('/auth/reset-password')

    if (response.status === 401 && !options._retried && !isAuthEndpoint) {
      // Don't try to refresh if this was already a refresh request
      if (!endpoint.includes('/auth/refresh')) {
        const refreshSuccess = await tryRefreshToken()
        if (refreshSuccess) {
          // Retry the original request with new token
          const retryOptions = {
            ...options,
            _retried: true,
            headers: createHeaders(options.includeAuth !== false)
          }
          const retryUrl = `${API_BASE_URL}${endpoint}`
          const retryResponse = await fetch(retryUrl, retryOptions)
          return handleResponse(retryResponse, { ...retryOptions, _retried: true }, endpoint)
        }
      }

      // If refresh failed or wasn't possible, redirect to login
      import('sonner').then(({ toast }) => {
        toast.error('Your session has expired. Please log in again.')
      })

      // Clear auth data
      removeAuthToken()
      removeRefreshToken()
      localStorage.removeItem('user_data')
      localStorage.removeItem('user_session')

      // Redirect to login
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
    }

    const message = data?.detail || data?.message || `HTTP ${response.status}: ${response.statusText}`
    throw new ApiError(message, response.status, data)
  }

  return data
}

/**
 * Make API request with standardized error handling
 * @param {string} endpoint - API endpoint path
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} API response data
 */
async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`

  const config = {
    headers: createHeaders(options.includeAuth !== false),
    ...options
  }

  try {
    const response = await fetch(url, config)
    return await handleResponse(response, config, endpoint)
  } catch (error) {
    if (error instanceof ApiError) {
      // Re-throw API errors as-is
      throw error
    } else {
      // Handle network errors, timeouts, etc.
      throw new ApiError(
        'Network error: Please check your connection and try again',
        0,
        null
      )
    }
  }
}

/**
 * GET request helper
 * @param {string} endpoint - API endpoint
 * @param {Object} params - Query parameters
 * @returns {Promise<Object>} API response
 */
async function GET(endpoint, params = {}) {
  const searchParams = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      searchParams.append(key, value.toString())
    }
  })

  const queryString = searchParams.toString()
  const url = queryString ? `${endpoint}?${queryString}` : endpoint

  return apiRequest(url, { method: 'GET' })
}

/**
 * POST request helper
 * @param {string} endpoint - API endpoint
 * @param {Object} data - Request body data
 * @returns {Promise<Object>} API response
 */
async function POST(endpoint, data = {}) {
  return apiRequest(endpoint, {
    method: 'POST',
    body: JSON.stringify(data)
  })
}

/**
 * PUT request helper
 * @param {string} endpoint - API endpoint
 * @param {Object} data - Request body data
 * @returns {Promise<Object>} API response
 */
async function PUT(endpoint, data = {}) {
  return apiRequest(endpoint, {
    method: 'PUT',
    body: JSON.stringify(data)
  })
}

/**
 * DELETE request helper
 * @param {string} endpoint - API endpoint
 * @returns {Promise<Object>} API response
 */
async function DELETE(endpoint) {
  return apiRequest(endpoint, { method: 'DELETE' })
}

// Authentication API endpoints
export const auth = {
  /**
   * User login
   * @param {Object} credentials - Login credentials
   * @param {string} credentials.username - Username or email
   * @param {string} credentials.password - Password
   * @returns {Promise<Object>} Login response with token and user data
   */
  async login(credentials) {
    // Convert username to email for backend compatibility
    const loginData = {
      email: credentials.username || credentials.email,
      password: credentials.password
    }
    const response = await POST('/api/auth/login', loginData)
    if (response.access_token) {
      setAuthToken(response.access_token)

      if (response.refresh_token) {
        setRefreshToken(response.refresh_token)
      }

      // Store complete session data in localStorage with role version
      const sessionData = {
        ...response.user,
        permissions: response.permissions || [],
        scope: response.scope || 'none'
      }
      tokenUtils.setSessionData(sessionData)
    }
    return response
  },

  /**
   * User logout
   * @param {boolean} logoutAllDevices - If true, logs out from all devices
   * @returns {Promise<Object>} Logout response
   */
  async logout(logoutAllDevices = false) {
    try {
      const refreshToken = getRefreshToken()
      await POST('/api/auth/logout', {
        refresh_token: refreshToken,
        logout_all_devices: logoutAllDevices
      })
    } finally {
      removeAuthToken()
      removeRefreshToken()
      tokenUtils.clearSessionData()
    }
  },

  /**
   * User onboarding with token
   * @param {Object} data - Onboarding data
   * @returns {Promise<Object>} Onboarding response
   */
  async onboard(data) {
    const response = await POST('/api/auth/onboard', data)
    if (response.access_token) {
      setAuthToken(response.access_token)
      if (response.user) {
        const sessionData = {
          ...response.user,
          permissions: response.permissions || [],
          scope: response.scope || 'none'
        }
        tokenUtils.setSessionData(sessionData)
      }
    }
    return response
  },

  /**
   * Refresh access token using refresh token
   * @returns {Promise<Object>} New token response with both tokens
   */
  async refresh() {
    const refreshToken = getRefreshToken()
    if (!refreshToken) {
      throw new ApiError('No refresh token available', 401)
    }
    const response = await POST('/api/auth/refresh', { refresh_token: refreshToken })
    if (response.access_token) {
      setAuthToken(response.access_token)
    }
    if (response.refresh_token) {
      setRefreshToken(response.refresh_token)
    }
    return response
  },

  /**
   * Reset password
   * @param {Object} data - Reset password data
   * @returns {Promise<Object>} Reset response
   */
  async resetPassword(data) {
    return POST('/api/auth/reset-password', data)
  },

  /**
   * Get current user information
   * @returns {Promise<Object>} Current user data
   */
  async me() {
    return await GET('/api/auth/me')
  },

  /**
   * Get complete session data with permissions
   * @returns {Promise<Object>} Complete session data
   */
  async session() {
    return await GET('/api/auth/session')
  },

  /**
   * Change user password
   * @param {Object} passwords - Password change data
   * @param {string} passwords.current_password - Current password
   * @param {string} passwords.new_password - New password
   * @returns {Promise<Object>} Change password response
   */
  async changePassword(passwords) {
    return POST('/api/auth/change-password', passwords)
  },

  /**
   * Request password reset
   * @param {string} email - User email address
   * @returns {Promise<Object>} Password reset response
   */
  async forgotPassword(email) {
    return POST('/api/auth/reset-password', { email })
  },

  /**
   * Reset password with token
   * @param {string} token - Password reset token
   * @param {string} password - New password
   * @returns {Promise<Object>} Password reset response
   */
  async resetPassword(token, password) {
    return POST('/api/auth/reset-password', { token, password })
  }
}

// User management API endpoints
export const users = {
  /**
   * List users with optional filtering
   * @param {Object} params - Query parameters
   * @param {number} params.skip - Pagination offset
   * @param {number} params.limit - Results per page
   * @param {string} params.search - Search term
   * @param {string} params.status_filter - Filter by user status
   * @param {string} params.organization_id - Filter by organization
   * @returns {Promise<Array>} List of users
   */
  async list(params = {}) {
    const response = await GET('/api/users', params)
    return {
      users: response.users || [],
      total: response.total || 0,
      page: response.page || 1,
      per_page: response.per_page || 50
    }
  },


  /**
   * Update current user profile
   * @param {Object} user - Updated user data
   * @returns {Promise<Object>} Updated user data
   */
  async updateMe(user) {
    return PUT('/api/users/me', user)
  },

  /**
   * Get current user's supervisees
   * @returns {Promise<Array>} List of supervisees
   */
  async getMySupervisees() {
    return GET('/api/users/me/supervisees')
  },

  /**
   * Assign or remove a supervisor for a user
   * @param {string} userId - User ID to update
   * @param {string|null} supervisorId - New supervisor ID, or null to remove
   * @returns {Promise<Object>} Updated user data
   */
  async assignSupervisor(userId, supervisorId) {
    return PUT(`/api/users/${userId}/supervisor`, { supervisor_id: supervisorId })
  },

  /**
   * Get specific user by ID
   * @param {string} id - User ID
   * @returns {Promise<Object>} User data
   */
  async get(id) {
    return GET(`/api/users/${id}`)
  },

  /**
   * Create new user
   * @param {Object} user - User data
   * @returns {Promise<Object>} Created user data
   */
  async create(user) {
    return POST('/api/users', user)
  },

  /**
   * Update user
   * @param {string} id - User ID
   * @param {Object} user - Updated user data
   * @returns {Promise<Object>} Updated user data
   */
  async update(id, user) {
    return PUT(`/api/users/${id}`, user)
  },

  /**
   * Update user status
   * @param {string} id - User ID
   * @param {string} status - New user status
   * @returns {Promise<Object>} Updated user data
   */
  async updateStatus(id, status) {
    return PUT(`/api/users/${id}/status`, { status })
  },

  /**
   * Get user history
   * @param {string} id - User ID
   * @returns {Promise<Object>} User history data
   */
  async getHistory(id) {
    return GET(`/api/users/${id}/history`)
  },

  /**
   * Resend onboarding email to a user who hasn't activated yet
   * @param {string} id - User ID
   * @returns {Promise<Object>} Resend response with token expiration
   */
  async resendOnboarding(id) {
    return POST(`/api/users/${id}/resend-onboarding`)
  },

  /**
   * Send password reset link to an onboarded user
   * @param {string} id - User ID
   * @returns {Promise<Object>} Reset link response with token expiration
   */
  async sendPasswordReset(id) {
    return POST(`/api/users/${id}/send-password-reset`)
  }
}

// Initiative management API endpoints (formerly tasks)
export const initiatives = {
  /**
   * List initiatives with optional filtering
   * @param {Object} params - Query parameters
   * @param {number} params.skip - Pagination offset
   * @param {number} params.limit - Results per page
   * @param {string} params.search - Search term
   * @param {string} params.status_filter - Filter by initiative status
   * @param {string} params.initiative_type - Filter by initiative type
   * @param {string} params.urgency_filter - Filter by urgency
   * @param {boolean} params.assigned_to_me - Filter by initiatives assigned to current user
   * @returns {Promise<Object>} Initiatives list with pagination
   */
  async list(params = {}) {
    const response = await GET('/api/initiatives', params)
    // Return full response with pagination data if available
    if (response.initiatives) {
      return {
        initiatives: response.initiatives || [],
        total: response.total || 0,
        page: response.page || 1,
        per_page: response.per_page || 20
      }
    }
    // Fallback for backward compatibility
    return { initiatives: response || [], total: 0, page: 1, per_page: 20 }
  },

  /**
   * Get specific initiative by ID
   * @param {string} id - Initiative ID
   * @returns {Promise<Object>} Initiative data
   */
  async get(id) {
    return GET(`/api/initiatives/${id}`)
  },

  /**
   * Create new initiative
   * @param {Object} initiative - Initiative data
   * @returns {Promise<Object>} Created initiative data
   */
  async create(initiative) {
    console.log(initiative)
    return POST('/api/initiatives', initiative)
  },

  /**
   * Update initiative details
   * @param {string} id - Initiative ID
   * @param {Object} data - Updated initiative data
   * @returns {Promise<Object>} Updated initiative data
   */
  async update(id, data) {
    return PUT(`/api/initiatives/${id}`, data)
  },

  /**
   * Get initiatives for supervisees (team members)
   * @returns {Promise<Array>} List of supervisee initiatives
   */
  async getSuperviseeInitiatives() {
    return GET('/api/initiatives/supervisees')
  },

  /**
   * Get list of users that can be assigned to initiatives
   * @returns {Promise<Array>} List of assignable users
   */
  async getAssignableUsers() {
    return GET('/api/initiatives/assignable-users')
  },

  /**
   * Check if current user has supervisees
   * @returns {Promise<Object>} {has_supervisees: boolean, supervisee_count: number}
   */
  async hasSupervisees() {
    return GET('/api/initiatives/has-supervisees')
  },

  /**
   * Approve or reject initiative (for supervisors)
   * @param {string} id - Initiative ID
   * @param {Object} approval - Approval data {approved: boolean, rejection_reason?: string}
   * @returns {Promise<Object>} Updated initiative data
   */
  async approve(id, approval) {
    return PUT(`/api/initiatives/${id}/approve`, approval)
  },

  /**
   * Accept an ASSIGNED initiative
   * @param {string} id - Initiative ID
   * @returns {Promise<Object>} Updated initiative data
   */
  async accept(id) {
    return PUT(`/api/initiatives/${id}/accept`)
  },

  /**
   * Start a PENDING initiative
   * @param {string} id - Initiative ID
   * @returns {Promise<Object>} Updated initiative data
   */
  async start(id) {
    return PUT(`/api/initiatives/${id}/start`)
  },

  /**
   * Mark ONGOING initiative as complete
   * @param {string} id - Initiative ID
   * @returns {Promise<Object>} Updated initiative data
   */
  async complete(id) {
    return PUT(`/api/initiatives/${id}/complete`)
  },

  /**
   * Update initiative status
   * @param {string} id - Initiative ID
   * @param {string} status - New initiative status
   * @returns {Promise<Object>} Updated initiative data
   */
  async updateStatus(id, status) {
    return PUT(`/api/initiatives/${id}/status`, { status })
  },

  /**
   * Submit initiative with report and documents
   * @param {string} id - Initiative ID
   * @param {Object} submission - Submission data with report and files
   * @returns {Promise<Object>} Submission response
   */
  async submit(id, submission) {
    return POST(`/api/initiatives/${id}/submit`, submission)
  },

  /**
   * Review and score completed initiative
   * @param {string} id - Initiative ID
   * @param {Object} review - Review data with score and feedback
   * @returns {Promise<Object>} Review response
   */
  async review(id, review) {
    return POST(`/api/initiatives/${id}/review`, review)
  },

  /**
   * Request deadline extension
   * @param {string} id - Initiative ID
   * @param {Object} extension - Extension request data
   * @returns {Promise<Object>} Extension request response
   */
  async requestExtension(id, extension) {
    return POST(`/api/initiatives/${id}/extension-request`, extension)
  },

  /**
   * Approve or deny extension request
   * @param {string} id - Initiative ID
   * @param {string} extensionId - Extension ID
   * @param {Object} decision - Approval decision
   * @returns {Promise<Object>} Decision response
   */
  async handleExtension(id, extensionId, decision) {
    return PUT(`/api/initiatives/${id}/extension/${extensionId}`, decision)
  },

  /**
   * Get initiative submissions
   * @param {string} id - Initiative ID
   * @returns {Promise<Object>} Initiative submission data
   */
  async getSubmissions(id) {
    return GET(`/api/initiatives/${id}/submissions`)
  },

  /**
   * Delete initiative
   * @param {string} id - Initiative ID
   * @returns {Promise<Object>} Deletion response
   */
  async delete(id) {
    return DELETE(`/api/initiatives/${id}`)
  },

  /**
   * Get initiative statistics
   * @returns {Promise<Object>} Initiative statistics
   */
  async stats() {
    return GET('/api/initiatives/stats')
  },

  /**
   * Upload document for initiative
   * @param {File} file - File to upload
   * @returns {Promise<Object>} Uploaded document data
   */
  async uploadDocument(file) {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${API_BASE_URL}/api/initiatives/upload-document`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`
      },
      body: formData
    })

    return await handleResponse(response)
  },

  // ============================================
  // SUB-TASKS
  // ============================================

  /**
   * Get all sub-tasks for an initiative
   * @param {string} initiativeId - Initiative ID
   * @returns {Promise<Array>} List of sub-tasks
   */
  async getSubTasks(initiativeId) {
    return GET(`/api/initiatives/${initiativeId}/subtasks`)
  },

  /**
   * Create a new sub-task for an initiative
   * @param {string} initiativeId - Initiative ID
   * @param {Object} subTask - Sub-task data {title, description}
   * @returns {Promise<Object>} Created sub-task
   */
  async createSubTask(initiativeId, subTask) {
    return POST(`/api/initiatives/${initiativeId}/subtasks`, subTask)
  },

  /**
   * Update a sub-task
   * @param {string} initiativeId - Initiative ID
   * @param {string} subTaskId - Sub-task ID
   * @param {Object} subTask - Updated sub-task data {title?, description?, status?}
   * @returns {Promise<Object>} Updated sub-task
   */
  async updateSubTask(initiativeId, subTaskId, subTask) {
    return PUT(`/api/initiatives/${initiativeId}/subtasks/${subTaskId}`, subTask)
  },

  /**
   * Delete a sub-task
   * @param {string} initiativeId - Initiative ID
   * @param {string} subTaskId - Sub-task ID
   * @returns {Promise<Object>} Deletion response
   */
  async deleteSubTask(initiativeId, subTaskId) {
    return DELETE(`/api/initiatives/${initiativeId}/subtasks/${subTaskId}`)
  },

  /**
   * Reorder sub-tasks
   * @param {string} initiativeId - Initiative ID
   * @param {Array<string>} subTaskIds - Array of sub-task IDs in new order
   * @returns {Promise<Array>} Reordered sub-tasks
   */
  async reorderSubTasks(initiativeId, subTaskIds) {
    return POST(`/api/initiatives/${initiativeId}/subtasks/reorder`, { subtask_ids: subTaskIds })
  }
}

// Keep backward compatibility alias for now
export const tasks = initiatives

// Role management API endpoints
export const roles = {
  /**
   * List all roles
   * @returns {Promise<Array>} List of roles
   */
  async list() {
    return GET('/api/roles')
  },

  /**
   * Get specific role by ID
   * @param {string} id - Role ID
   * @returns {Promise<Object>} Role data
   */
  async get(id) {
    return GET(`/api/roles/${id}`)
  },

  /**
   * Create new role
   * @param {Object} role - Role data
   * @returns {Promise<Object>} Created role data
   */
  async create(role) {
    return POST('/api/roles', role)
  },

  /**
   * Update role
   * @param {string} id - Role ID
   * @param {Object} role - Updated role data
   * @returns {Promise<Object>} Updated role data
   */
  async update(id, role) {
    return PUT(`/api/roles/${id}`, role)
  },

  /**
   * Delete role
   * @param {string} id - Role ID
   * @returns {Promise<Object>} Deletion response
   */
  async delete(id) {
    return DELETE(`/api/roles/${id}`)
  },

  /**
   * Get all available permissions
   * @returns {Promise<Object>} Available permissions
   */
  async getPermissions() {
    return GET('/api/roles/permissions')
  }
}

// Goal management API endpoints
export const goals = {
  /**
   * List goals with optional filtering
   * @param {Object} params - Query parameters
   * @returns {Promise<Array>} List of goals
   */
  async list(params = {}) {
    return GET('/api/goals', params)
  },

  /**
   * Get specific goal by ID
   * @param {string} id - Goal ID
   * @returns {Promise<Object>} Goal data
   */
  async get(id) {
    return GET(`/api/goals/${id}`)
  },

  /**
   * Create new goal
   * @param {Object} goal - Goal data
   * @returns {Promise<Object>} Created goal data
   */
  async create(goal) {
    return POST('/api/goals', goal)
  },

  /**
   * Update goal
   * @param {string} id - Goal ID
   * @param {Object} goal - Updated goal data
   * @returns {Promise<Object>} Updated goal data
   */
  async update(id, goal) {
    return PUT(`/api/goals/${id}`, goal)
  },

  /**
   * Update goal progress
   * @param {string} id - Goal ID
   * @param {Object} progress - Progress data with report
   * @returns {Promise<Object>} Updated goal data
   */
  async updateProgress(id, progress) {
    return PUT(`/api/goals/${id}/progress`, progress)
  },

  /**
   * Update goal status (achieve/discard)
   * @param {string} id - Goal ID
   * @param {Object} status - Status data
   * @returns {Promise<Object>} Updated goal data
   */
  async updateStatus(id, status) {
    return PUT(`/api/goals/${id}/status`, status)
  },

  /**
   * Get goal children
   * @param {string} id - Goal ID
   * @returns {Promise<Array>} List of child goals
   */
  async getChildren(id) {
    return GET(`/api/goals/${id}/children`)
  },

  /**
   * Add progress report to goal
   * @param {string} id - Goal ID
   * @param {Object} report - Progress report data
   * @returns {Promise<Object>} Report response
   */
  async addProgressReport(id, report) {
    return POST(`/api/goals/${id}/progress-report`, report)
  },

  /**
   * Delete goal
   * @param {string} id - Goal ID
   * @returns {Promise<Object>} Deletion response
   */
  async delete(id) {
    return DELETE(`/api/goals/${id}`)
  },

  /**
   * Get goal statistics
   * @returns {Promise<Object>} Goal statistics
   */
  async stats() {
    return GET('/api/goals/stats')
  },

  /**
   * Approve or reject an individual goal
   * @param {string} id - Goal ID
   * @param {Object} approval - Approval data {approved: boolean, rejection_reason?: string}
   * @returns {Promise<Object>} Updated goal data
   */
  async approve(id, approval) {
    return PUT(`/api/goals/${id}/approve`, approval)
  },

  /**
   * Freeze all goals for a specific quarter
   * @param {Object} freezeData - Freeze data {quarter: string, year: number}
   * @returns {Promise<Object>} Freeze operation result
   */
  async freezeQuarter(freezeData) {
    return POST('/api/goals/freeze-quarter', freezeData)
  },

  /**
   * Unfreeze all goals for a specific quarter
   * @param {Object} unfreezeData - Unfreeze data {quarter: string, year: number, is_emergency_override?: boolean, emergency_reason?: string}
   * @returns {Promise<Object>} Unfreeze operation result
   */
  async unfreezeQuarter(unfreezeData) {
    return POST('/api/goals/unfreeze-quarter', unfreezeData)
  },

  /**
   * Get freeze/unfreeze logs
   * @returns {Promise<Array>} List of freeze logs
   */
  async getFreezeLogs() {
    return GET('/api/goals/freeze-logs')
  },

  /**
   * Get all goals for current user's supervisees
   * @returns {Promise<Array>} List of supervisee goals
   */
  async getSuperviseeGoals() {
    return GET('/api/goals/supervisees')
  },

  /**
   * Create a goal for a supervisee (supervisor only)
   * @param {Object} goalData - Goal data with supervisee_id
   * @returns {Promise<Object>} Created goal data
   */
  async createForSupervisee(goalData) {
    const { supervisee_id, ...goal } = goalData
    return POST(`/api/goals/create-for-supervisee?supervisee_id=${supervisee_id}`, goal)
  },

  /**
   * Respond to an assigned goal (accept or decline)
   * @param {string} id - Goal ID
   * @param {Object} response - Response data {accepted: boolean, response_message?: string}
   * @returns {Promise<Object>} Updated goal data
   */
  async respond(id, response) {
    const params = new URLSearchParams()
    params.append('accepted', response.accepted.toString())
    if (response.response_message) {
      params.append('response_message', response.response_message)
    }
    return PUT(`/api/goals/${id}/respond?${params.toString()}`)
  },

  /**
   * Request a change to a goal
   * @param {string} id - Goal ID
   * @param {string} changeRequest - Change request message
   * @returns {Promise<Object>} Updated goal data
   */
  async requestChange(id, changeRequest) {
    return PUT(`/api/goals/${id}/request-change`, { change_request: changeRequest })
  },

  /**
   * Freeze an individual goal
   * @param {string} id - Goal ID
   * @param {string} reason - Reason for freezing (optional)
   * @returns {Promise<Object>} Freeze operation result
   */
  async freezeGoal(id, reason = null) {
    return POST(`/api/goals/${id}/freeze`, { reason })
  },

  /**
   * Unfreeze an individual goal
   * @param {string} id - Goal ID
   * @param {string} reason - Reason for unfreezing (optional)
   * @returns {Promise<Object>} Unfreeze operation result
   */
  async unfreezeGoal(id, reason = null) {
    return POST(`/api/goals/${id}/unfreeze`, { reason })
  },

  /**
   * Submit KPI actuals for a goal (supervisor assessment)
   * @param {string} id - Goal ID
   * @param {Object} assessment - { kpi_assessments: [{id, actual_value, achieved}] }
   * @returns {Promise<Object>} Updated goal data
   */
  async assess(id, assessment) {
    return PUT(`/api/goals/${id}/assess`, assessment)
  },

  async supervisorScore(id, data) {
    return PUT(`/api/goals/${id}/supervisor-score`, data)
  }
}

// Goal Tags/Labels API endpoints
export const goalTags = {
  /**
   * Get all goal tags
   * @returns {Promise<Array>} List of tags
   */
  async list() {
    return GET('/api/goal-tags')
  },

  /**
   * Create a new goal tag
   * @param {Object} tag - Tag data {name, color, description}
   * @returns {Promise<Object>} Created tag data
   */
  async create(tag) {
    return POST('/api/goal-tags', tag)
  },

  /**
   * Update a goal tag
   * @param {string} id - Tag ID
   * @param {Object} tag - Updated tag data
   * @returns {Promise<Object>} Updated tag data
   */
  async update(id, tag) {
    return PUT(`/api/goal-tags/${id}`, tag)
  },

  /**
   * Delete a goal tag
   * @param {string} id - Tag ID
   * @returns {Promise<Object>} Deletion response
   */
  async delete(id) {
    return DELETE(`/api/goal-tags/${id}`)
  }
}

// Review management API endpoints
export const reviews = {
  /**
   * List review cycles
   * @param {Object} params - Query parameters
   * @returns {Promise<Array>} List of review cycles
   */
  async listCycles(params = {}) {
    return GET('/api/reviews/cycles', params)
  },

  /**
   * Get specific review cycle
   * @param {string} id - Review cycle ID
   * @returns {Promise<Object>} Review cycle data
   */
  async getCycle(id) {
    return GET(`/api/reviews/cycles/${id}`)
  },

  /**
   * Create enhanced review cycle
   * @param {Object} cycle - Review cycle data
   * @returns {Promise<Object>} Created review cycle
   */
  async createEnhancedCycle(cycle) {
    return POST('/api/reviews/cycles/enhanced', cycle)
  },

  /**
   * Update review cycle
   * @param {string} id - Review cycle ID
   * @param {Object} cycle - Updated cycle data
   * @returns {Promise<Object>} Updated review cycle
   */
  async updateCycle(id, cycle) {
    return PUT(`/api/reviews/cycles/${id}`, cycle)
  },

  /**
   * List review traits
   * @returns {Promise<Array>} List of review traits
   */
  async listTraits() {
    return GET('/api/reviews/traits')
  },

  /**
   * Create review trait
   * @param {Object} trait - Trait data
   * @returns {Promise<Object>} Created trait
   */
  async createTrait(trait) {
    return POST('/api/reviews/traits', trait)
  },

  /**
   * Get questions for a trait
   * @param {string} traitId - Trait ID
   * @returns {Promise<Array>} List of questions
   */
  async getTraitQuestions(traitId) {
    return GET(`/api/reviews/traits/${traitId}/questions`)
  },

  /**
   * Create question for a trait
   * @param {string} traitId - Trait ID
   * @param {Object} question - Question data
   * @returns {Promise<Object>} Created question
   */
  async createQuestion(traitId, question) {
    return POST(`/api/reviews/traits/${traitId}/questions`, question)
  },

  /**
   * Delete a question
   * @param {string} questionId - Question ID
   * @returns {Promise<Object>} Deletion response
   */
  async deleteQuestion(questionId) {
    return DELETE(`/api/reviews/questions/${questionId}`)
  },

  /**
   * Get user's review assignments
   * @returns {Promise<Array>} List of review assignments
   */
  async getMyAssignments() {
    return GET('/api/reviews/my-assignments')
  },

  /**
   * Get specific review
   * @param {string} id - Review ID
   * @returns {Promise<Object>} Review data
   */
  async getReview(id) {
    return GET(`/api/reviews/${id}`)
  },

  /**
   * Update review
   * @param {string} id - Review ID
   * @param {Object} review - Updated review data
   * @returns {Promise<Object>} Updated review
   */
  async updateReview(id, review) {
    return PUT(`/api/reviews/${id}`, review)
  },

  /**
   * Submit review
   * @param {string} id - Review ID
   * @returns {Promise<Object>} Submission response
   */
  async submitReview(id) {
    return POST(`/api/reviews/${id}/submit`)
  },

  /**
   * Get review analytics
   * @param {Object} params - Query parameters
   * @returns {Promise<Object>} Review analytics
   */
  async analytics(params = {}) {
    return GET('/api/reviews/analytics', params)
  }
}

// Organization management API endpoints
export const organization = {
  /**
   * List all organizations in the hierarchy
   * @returns {Promise<Array>} List of all organizations
   */
  async list() {
    return GET('/api/organization/')
  },

  /**
   * Get organization tree structure
   * @returns {Promise<Object>} Hierarchical organization tree
   */
  async tree() {
    return GET('/api/organization/tree')
  },

  /**
   * Create new organization unit
   * @param {Object} org - Organization data
   * @returns {Promise<Object>} Created organization data
   */
  async create(org) {
    return POST('/api/organization/', org)
  },

  /**
   * Update organization unit
   * @param {string} id - Organization ID
   * @param {Object} org - Updated organization data
   * @returns {Promise<Object>} Updated organization data
   */
  async update(id, org) {
    return PUT(`/api/organization/${id}`, org)
  },

  /**
   * Delete organization unit
   * @param {string} id - Organization ID
   * @returns {Promise<Object>} Deletion response
   */
  async delete(id) {
    return DELETE(`/api/organization/${id}`)
  },

  /**
   * Get specific organization by ID
   * @param {string} id - Organization ID
   * @returns {Promise<Object>} Organization data
   */
  async get(id) {
    return GET(`/api/organization/${id}`)
  }
}

// Utility functions for token management
export const tokenUtils = {
  getToken: getAuthToken,
  setToken: setAuthToken,
  removeToken: removeAuthToken,
  getRefreshToken: getRefreshToken,
  setRefreshToken: setRefreshToken,
  removeRefreshToken: removeRefreshToken,

  /**
   * Check if user is authenticated (has valid access token or refresh token)
   * @returns {boolean} Authentication status
   */
  isAuthenticated() {
    return !!getAuthToken() || !!getRefreshToken()
  },

  /**
   * Check if user has a valid (non-expired) access token
   * @returns {boolean} Whether the access token is still valid
   */
  hasValidAccessToken() {
    const token = getAuthToken()
    if (!token) return false
    return !this.isTokenExpired(token)
  },

  /**
   * Check if user has a refresh token (can potentially restore session)
   * @returns {boolean} Whether a refresh token exists
   */
  hasRefreshToken() {
    return !!getRefreshToken()
  },

  /**
   * Decode JWT token (basic parsing, not validation)
   * @param {string} token - JWT token
   * @returns {Object|null} Decoded token payload
   */
  decodeToken(token = null) {
    const tokenToUse = token || getAuthToken()
    if (!tokenToUse) return null

    try {
      const payload = tokenToUse.split('.')[1]
      const decoded = JSON.parse(atob(payload))
      return decoded
    } catch (error) {
      console.error('Error decoding token:', error)
      return null
    }
  },

  /**
   * Check if token is expired
   * @param {string} token - JWT token
   * @returns {boolean} Expiration status
   */
  isTokenExpired(token = null) {
    const decoded = this.decodeToken(token)
    if (!decoded || !decoded.exp) return true

    const currentTime = Math.floor(Date.now() / 1000)
    return decoded.exp < currentTime
  },

  /**
   * Get role version from token for cache validation
   * @param {string} token - JWT token
   * @returns {number|null} Role version
   */
  getRoleVersion(token = null) {
    const decoded = this.decodeToken(token)
    return decoded?.role_version || null
  },

  /**
   * Check if session data needs refresh based on role version
   * @returns {boolean} Whether session data should be refreshed
   */
  shouldRefreshSession() {
    const sessionData = this.getSessionData()
    if (!sessionData) return true

    const tokenRoleVersion = this.getRoleVersion()
    const sessionRoleVersion = sessionData.role_version

    // If role versions don't match, refresh is needed
    return tokenRoleVersion !== sessionRoleVersion
  },

  /**
   * Get session data from localStorage
   * @returns {Object|null} Session data
   */
  getSessionData() {
    try {
      const data = localStorage.getItem('user_session')
      return data ? JSON.parse(data) : null
    } catch (error) {
      console.error('Error parsing session data:', error)
      return null
    }
  },

  /**
   * Store session data in localStorage with role version
   * @param {Object} sessionData - Session data to store
   */
  setSessionData(sessionData) {
    const tokenRoleVersion = this.getRoleVersion()
    const dataWithVersion = {
      ...sessionData,
      role_version: tokenRoleVersion
    }
    localStorage.setItem('user_session', JSON.stringify(dataWithVersion))
  },

  /**
   * Clear session data from localStorage
   */
  clearSessionData() {
    localStorage.removeItem('user_session')
  }
}

// Organization management API endpoints
export const organizations = {
  /**
   * List all organizations accessible to current user
   * @returns {Promise<Array>} List of organizations
   */
  async list(params = {}) {
    return GET('/api/organization', params)
  },

  /**
   * Get complete organizational hierarchy tree
   * @returns {Promise<Object>} Organization tree structure
   */
  async getTree() {
    return GET('/api/organization/tree')
  },

  /**
   * Create new organization
   * @param {Object} organization - Organization data
   * @param {string} organization.name - Organization name
   * @param {string} organization.description - Organization description
   * @param {string} organization.level - Organization level (global, directorate, department, unit)
   * @param {string} organization.parent_id - Parent organization ID (null for global)
   * @returns {Promise<Object>} Created organization data
   */
  async create(organization) {
    return POST('/api/organization', organization)
  },

  /**
   * Update organization
   * @param {string} id - Organization ID
   * @param {Object} organization - Updated organization data
   * @param {string} organization.name - Updated organization name
   * @param {string} organization.description - Updated organization description
   * @returns {Promise<Object>} Updated organization data
   */
  async update(id, organization) {
    return PUT(`/api/organization/${id}`, organization)
  },

  /**
   * Delete organization
   * @param {string} id - Organization ID
   * @returns {Promise<Object>} Deletion response
   */
  async delete(id) {
    return DELETE(`/api/organization/${id}`)
  },

  /**
   * Get children of organization
   * @param {string} id - Organization ID
   * @returns {Promise<Array>} List of child organizations
   */
  async getChildren(id) {
    return GET(`/api/organization/${id}/children`)
  },

  /**
   * Get organization statistics
   * @returns {Promise<Object>} Organization statistics
   */
  async getStats() {
    return GET('/api/organization/stats')
  }
}

/**
 * Notifications API
 */
export const notifications = {
  /**
   * Get user notifications with pagination and filtering
   * @param {Object} params - Query parameters
   * @param {number} params.skip - Number of items to skip
   * @param {number} params.limit - Number of items to return
   * @param {boolean} params.unread_only - Filter for unread notifications only
   * @param {string} params.notification_type - Filter by notification type
   * @param {string} params.priority - Filter by priority
   * @returns {Promise<Object>} Notification list response
   */
  async getAll(params = {}) {
    const queryParams = new URLSearchParams()
    if (params.skip !== undefined) queryParams.append('skip', params.skip)
    if (params.limit !== undefined) queryParams.append('limit', params.limit)
    if (params.unread_only) queryParams.append('unread_only', 'true')
    if (params.notification_type) queryParams.append('notification_type', params.notification_type)
    if (params.priority) queryParams.append('priority', params.priority)

    return GET(`/api/notifications?${queryParams.toString()}`)
  },

  /**
   * Get notification statistics
   * @returns {Promise<Object>} Notification stats
   */
  async getStats() {
    return GET('/api/notifications/stats')
  },

  /**
   * Mark a notification as read
   * @param {string} id - Notification ID
   * @returns {Promise<Object>} Updated notification
   */
  async markAsRead(id) {
    return PUT(`/api/notifications/${id}/read`)
  },

  /**
   * Mark all notifications as read
   * @returns {Promise<Object>} Response message
   */
  async markAllAsRead() {
    return PUT('/api/notifications/mark-all-read')
  },

  /**
   * Delete a notification
   * @param {string} id - Notification ID
   * @returns {Promise<Object>} Deletion response
   */
  async delete(id) {
    return DELETE(`/api/notifications/${id}`)
  },

  /**
   * Get WebSocket connection stats (for debugging)
   * @returns {Promise<Object>} Connection statistics
   */
  async getConnectionStats() {
    return GET('/api/notifications/connection-stats')
  }
}

// Export HTTP method helpers
export { GET, POST, PUT, DELETE }

// Export API error class
export { ApiError }