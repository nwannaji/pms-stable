'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { auth, tokenUtils } from './api'
import { toast } from 'sonner'

/**
 * Authentication context for managing user state and authentication flow
 */
const AuthContext = createContext({
  user: null,
  loading: true,
  loggingOut: false,
  login: async () => {},
  logout: async () => {},
  refreshUser: async () => {}
})

/**
 * Hook to use authentication context
 * @returns {Object} Authentication context value
 */
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

/**
 * Authentication provider component
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - Child components
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loggingOut, setLoggingOut] = useState(false)
  const router = useRouter()

  /**
   * Fetch current user data from API
   */
  const fetchUser = async () => {
    try {
      if (!tokenUtils.isAuthenticated()) {
        setUser(null)
        setLoading(false)
        return
      }

      // Check if token is expired
      if (tokenUtils.isTokenExpired()) {
        tokenUtils.removeToken()
        localStorage.removeItem('user_data')
        setUser(null)
        setLoading(false)

        // Show toast and redirect to login
        toast.error('Your session has expired. Please log in again.')
        router.replace('/login')
        return
      }

      const userData = await auth.me()
      setUser(userData)
    } catch (error) {
      console.error('Error fetching user:', error)
      // If API call fails (401 will be handled by API interceptor)
      // Just remove invalid token and reset user for other errors
      if (error.status !== 401) {
        tokenUtils.removeToken()
        localStorage.removeItem('user_data')
        setUser(null)
      }
    } finally {
      setLoading(false)
    }
  }

  /**
   * Login user with credentials
   * @param {Object} credentials - Login credentials
   * @param {string} credentials.username - Username or email
   * @param {string} credentials.password - Password
   * @returns {Promise<Object>} Login response
   */
  const login = async (credentials) => {
    setLoading(true)
    try {
      const response = await auth.login(credentials)

      // The API client automatically sets the token in cookies
      // Store user data from login response
      if (response.user) {
        // Store token data from login response, then fetch full profile from /me
        // (login response doesn't include all fields like supervisor_name)
        const tokenData = {
          permissions: response.permissions || [],
          scope: response.scope || 'none'
        }
        localStorage.setItem('user_data', JSON.stringify({ ...response.user, ...tokenData }))
        // Always fetch full profile so supervisor_name and other fields are included
        await fetchUser()
      } else {
        // If user data is not in login response, fetch it
        await fetchUser()
      }

      return response
    } catch (error) {
      setLoading(false)
      throw error
    } finally {
      setLoading(false)
    }
  }

  /**
   * Logout user and redirect to login page
   */
  const logout = async () => {
    try {
      // Set logging out state to prevent auth guard from showing
      setLoggingOut(true)

      // Remove token and session data first
      tokenUtils.removeToken()
      tokenUtils.clearSessionData()
      localStorage.removeItem('user_data')

      // Clear user state
      setUser(null)

      // Redirect to login immediately (use replace to avoid history)
      router.replace('/login')

      // Call logout API in background (best effort — token may already be expired)
      auth.logout().catch(() => {})
    } catch (error) {
      console.error('Logout error:', error)
      // Ensure cleanup even on error
      setUser(null)
      tokenUtils.removeToken()
      tokenUtils.clearSessionData()
      router.replace('/login')
    } finally {
      // Reset logging out state after a brief delay
      setTimeout(() => setLoggingOut(false), 500)
    }
  }

  /**
   * Refresh current user data
   */
  const refreshUser = async () => {
    if (tokenUtils.isAuthenticated() && !tokenUtils.isTokenExpired()) {
      await fetchUser()
    }
  }

  // Initialize authentication state on mount
  useEffect(() => {
    fetchUser()
  }, [])

  const value = {
    user,
    loading,
    loggingOut,
    login,
    logout,
    refreshUser
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Higher-order component to protect routes that require authentication
 * @param {React.Component} WrappedComponent - Component to protect
 * @returns {React.Component} Protected component
 */
export function withAuth(WrappedComponent) {
  return function ProtectedComponent(props) {
    const { user, loading } = useAuth()
    const router = useRouter()

    useEffect(() => {
      if (!loading && !user) {
        router.push('/login')
      }
    }, [user, loading, router])

    // Show loading spinner while checking authentication
    if (loading) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-background">
          <div className="text-center">
            <div className="loading-skeleton w-8 h-8 rounded mx-auto mb-4"></div>
            <p className="text-body text-secondary">Loading...</p>
          </div>
        </div>
      )
    }

    // Redirect to login if not authenticated
    if (!user) {
      return null
    }

    // Render the protected component
    return <WrappedComponent {...props} />
  }
}

/**
 * Component to handle authentication-based routing
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - Child components for authenticated users
 * @param {React.ReactNode} props.fallback - Fallback component for unauthenticated users
 */
export function AuthGuard({ children, fallback = null }) {
  const { user, loading, loggingOut } = useAuth()
  const router = useRouter()

  // Redirect to login if not authenticated (in useEffect to avoid setState during render)
  useEffect(() => {
    if (!loading && !loggingOut && !user) {
      router.replace('/login')
    }
  }, [user, loading, loggingOut, router])

  // Show loading during initial load or logout
  if (loading || loggingOut) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <div className="loading-skeleton w-8 h-8 rounded mx-auto mb-4"></div>
          <p className="text-body text-secondary">{loggingOut ? 'Logging out...' : 'Loading...'}</p>
        </div>
      </div>
    )
  }

  // Don't render children until we confirm authentication
  if (!user) {
    return null
  }

  return children
}

/**
 * Hook to check user permissions
 * @param {string} permission - Permission to check
 * @returns {boolean} Whether user has the permission
 */
export function usePermission(permission) {
  const { user } = useAuth()

  if (!user) return false

  // Check if user has system_admin permission (equivalent to superuser)
  if (user.permissions && user.permissions.includes('system_admin')) return true

  // Check if user has the specific permission
  if (user.permissions && user.permissions.includes(permission)) {
    return true
  }

  return false
}

/**
 * Hook to check if user is superuser
 * @returns {boolean} Whether user is superuser
 */
export function useIsSuperuser() {
  const { user } = useAuth()
  return user?.permissions?.includes('system_admin') || false
}

/**
 * Hook to get user's role information
 * @returns {string|null} User's role name or null
 */
export function useUserRole() {
  const { user } = useAuth()
  return user?.role_name || null
}

/**
 * Hook to get user's organization information
 * @returns {string|null} User's organization name or null
 */
export function useUserOrganization() {
  const { user } = useAuth()
  return user?.organization_name || null
}

/**
 * Component to conditionally render content based on permissions
 * @param {Object} props - Component props
 * @param {string} props.permission - Required permission
 * @param {React.ReactNode} props.children - Content to render if permission is granted
 * @param {React.ReactNode} props.fallback - Content to render if permission is denied
 */
export function PermissionGuard({ permission, children, fallback = null }) {
  const hasPermission = usePermission(permission)

  if (!hasPermission) {
    return fallback
  }

  return children
}

/**
 * Component to conditionally render content for superusers only
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - Content to render for superusers
 * @param {React.ReactNode} props.fallback - Content to render for non-superusers
 */
export function SuperuserGuard({ children, fallback = null }) {
  const isSuperuser = useIsSuperuser()

  if (!isSuperuser) {
    return fallback
  }

  return children
}