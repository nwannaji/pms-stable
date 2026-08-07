'use client'

import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { useWebSocket } from './useWebSocket'
import { useQueryClient } from '@tanstack/react-query'
import { notifications as notificationsApi } from './api'

const NotificationContext = createContext(undefined)

export function NotificationProvider({ children}) {
  const { isConnected, isPolling, lastMessage } = useWebSocket()
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const queryClient = useQueryClient()

  // Map notification types to query keys that should be invalidated
  const getQueryKeysToInvalidate = useCallback((notificationType) => {
    const typeToQueryKeys = {
      // Initiative notifications
      'INITIATIVE_ASSIGNED': ['initiatives'],
      'INITIATIVE_APPROVED': ['initiatives'],
      'INITIATIVE_REJECTED': ['initiatives'],
      'INITIATIVE_STATUS_CHANGED': ['initiatives'],
      'INITIATIVE_SUBMITTED': ['initiatives'],
      'INITIATIVE_REVIEWED': ['initiatives'],
      'INITIATIVE_DEADLINE_APPROACHING': ['initiatives'],

      // Goal notifications
      'GOAL_ASSIGNED': ['goals'],
      'GOAL_APPROVED': ['goals'],
      'GOAL_REJECTED': ['goals'],
      'GOAL_PROGRESS_UPDATED': ['goals'],
      'GOAL_SCORED': ['goals'],
      'GOAL_COMPLETED': ['goals'],
      'GOAL_STATUS_CHANGED': ['goals'],
      'GOAL_DEADLINE_APPROACHING': ['goals'],

      // Task notifications (if you have tasks)
      'TASK_ASSIGNED': ['tasks'],
      'TASK_SUBMITTED': ['tasks'],
      'TASK_REVIEWED': ['tasks'],
      'TASK_STATUS_CHANGED': ['tasks'],
      'TASK_DEADLINE_APPROACHING': ['tasks'],

      // User notifications
      'USER_ROLE_CHANGED': ['users'],
      'USER_STATUS_CHANGED': ['users'],
    }

    return typeToQueryKeys[notificationType] || []
  }, [])

  // Handle incoming messages (from both WebSocket and polling)
  useEffect(() => {
    if (!lastMessage) return

    if (lastMessage.type === 'new_notification') {
      const newNotification = lastMessage.notification

      // Add to local state
      setNotifications(prev => [newNotification, ...prev])
      setUnreadCount(prev => prev + 1)

      console.log('New notification:', newNotification.title)

      // Invalidate notifications query
      queryClient.invalidateQueries({ queryKey: ['notifications'] })

      // Invalidate related data queries based on notification type
      const relatedQueryKeys = getQueryKeysToInvalidate(newNotification.type)
      relatedQueryKeys.forEach(queryKey => {
        console.log(`Invalidating cache for: ${queryKey}`)
        queryClient.invalidateQueries({ queryKey: [queryKey] })
      })

      // Also invalidate supervisee goals query for any goal-related notification
      if (newNotification.type?.startsWith('GOAL_')) {
        queryClient.invalidateQueries({ queryKey: ['goals', 'supervisees'] })
      }
    } else if (lastMessage.type === 'new_notifications_batch') {
      // Batch of new notifications from polling
      const newNotifications = lastMessage.notifications || []
      if (newNotifications.length > 0) {
        setNotifications(prev => [...newNotifications, ...prev])
        setUnreadCount(prev => prev + newNotifications.length)

        // Invalidate notifications and related queries
        queryClient.invalidateQueries({ queryKey: ['notifications'] })
        newNotifications.forEach(n => {
          const relatedQueryKeys = getQueryKeysToInvalidate(n.type)
          relatedQueryKeys.forEach(queryKey => {
            queryClient.invalidateQueries({ queryKey: [queryKey] })
          })
        })
      }
    } else if (lastMessage.type === 'marked_read') {
      // Update local state when marked as read
      const notificationId = lastMessage.notification_id
      setNotifications(prev =>
        prev.map(n => n.id === notificationId ? { ...n, is_read: true } : n)
      )
      setUnreadCount(prev => Math.max(0, prev - 1))
    } else if (lastMessage.type === 'notification_stats') {
      // Update unread count from polling stats
      const stats = lastMessage.stats
      if (stats && typeof stats.unread_count === 'number') {
        setUnreadCount(stats.unread_count)
      }
    } else if (lastMessage.type === 'connection_established') {
      // WebSocket connected — invalidate to sync state
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    }
  }, [lastMessage, queryClient, getQueryKeysToInvalidate])

  const addNotification = useCallback((notification) => {
    setNotifications(prev => [notification, ...prev])
    if (!notification.is_read) {
      setUnreadCount(prev => prev + 1)
    }
  }, [])

  const markAsRead = useCallback(async (notificationId) => {
    // Optimistic local update
    setNotifications(prev =>
      prev.map(n => n.id === notificationId ? { ...n, is_read: true } : n)
    )
    setUnreadCount(prev => Math.max(0, prev - 1))

    // Persist via REST API (works with both WebSocket and polling)
    try {
      await notificationsApi.markAsRead(notificationId)
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications', 'stats'] })
    } catch (error) {
      console.error('Failed to mark notification as read:', error)
    }
  }, [queryClient])

  const markAllAsRead = useCallback(async () => {
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })))
    setUnreadCount(0)

    try {
      await notificationsApi.markAllAsRead()
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications', 'stats'] })
    } catch (error) {
      console.error('Failed to mark all notifications as read:', error)
    }
  }, [queryClient])

  const removeNotification = useCallback((notificationId) => {
    setNotifications(prev => {
      const notification = prev.find(n => n.id === notificationId)
      if (notification && !notification.is_read) {
        setUnreadCount(count => Math.max(0, count - 1))
      }
      return prev.filter(n => n.id !== notificationId)
    })
  }, [])

  const setInitialNotifications = useCallback((initialNotifications, initialUnreadCount) => {
    setNotifications(initialNotifications)
    setUnreadCount(initialUnreadCount)
  }, [])

  const value = {
    notifications,
    unreadCount,
    isConnected,
    isPolling,
    addNotification,
    markAsRead,
    markAllAsRead,
    removeNotification,
    setInitialNotifications
  }

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  )
}

export function useNotifications() {
  const context = useContext(NotificationContext)
  if (context === undefined) {
    throw new Error('useNotifications must be used within a NotificationProvider')
  }
  return context
}