'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuth } from './auth-context'
import { tokenUtils } from './api'

// Build WebSocket URL from env var — code appends /api/notifications/ws automatically
const getWebSocketURL = () => {
  const baseUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'
  // Strip any trailing slashes so concatenation is safe
  return baseUrl.replace(/\/+$/, '')
}

// API base URL for polling fallback
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || ''

const WEBSOCKET_URL = getWebSocketURL()

// Reconnection config — exponential backoff with jitter
const INITIAL_RECONNECT_DELAY = 1000   // 1 second initial delay
const MAX_RECONNECT_DELAY = 30000      // 30 seconds max delay
const BACKOFF_MULTIPLIER = 1.5
const MAX_RECONNECT_ATTEMPTS = 10      // Try 10 times, then fall back to polling

// Polling config — used as fallback when WebSocket is unavailable
const POLL_INTERVAL = 15000  // Poll every 15 seconds

export function useWebSocket() {
  const { user } = useAuth()
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState(null)
  const [isPolling, setIsPolling] = useState(false)
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)
  const intentionalCloseRef = useRef(false)
  const pollingIntervalRef = useRef(null)
  const lastPollTimestampRef = useRef(null)

  const getReconnectDelay = useCallback(() => {
    const attempt = reconnectAttemptsRef.current
    // Exponential backoff: 1s, 1.5s, 2.25s, 3.4s, ... up to 30s
    const delay = Math.min(
      INITIAL_RECONNECT_DELAY * Math.pow(BACKOFF_MULTIPLIER, attempt),
      MAX_RECONNECT_DELAY
    )
    // Add jitter (±25%) to avoid thundering herd
    const jitter = delay * 0.25 * (Math.random() * 2 - 1)
    return Math.max(500, delay + jitter)
  }, [])

  // Start polling as fallback when WebSocket is unavailable
  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current) return // Already polling

    console.log('WebSocket unavailable — switching to polling fallback')
    setIsPolling(true)

    const poll = async () => {
      const token = tokenUtils.getToken()
      if (!token) return

      try {
        // Fetch stats (unread count) — this is the most important for the bell badge
        const statsResponse = await fetch(`${API_BASE_URL}/api/notifications/stats`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })

        if (statsResponse.ok) {
          const stats = await statsResponse.json()
          setLastMessage({
            type: 'notification_stats',
            stats
          })
        }

        // Also fetch recent unread notifications
        const response = await fetch(`${API_BASE_URL}/api/notifications?limit=20&unread_only=true`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })

        if (!response.ok) return

        const data = await response.json()

        // Check for new notifications since last poll
        if (data.notifications && data.notifications.length > 0) {
          const lastTimestamp = lastPollTimestampRef.current
          const newNotifications = lastTimestamp
            ? data.notifications.filter(n => {
                const notifTime = new Date(n.created_at).getTime()
                return notifTime > lastTimestamp
              })
            : [] // First poll: don't re-emit existing notifications

          lastPollTimestampRef.current = Date.now()

          // Emit a single batch message with all new notifications
          if (newNotifications.length > 0) {
            setLastMessage({
              type: 'new_notifications_batch',
              notifications: newNotifications
            })
          }
        }
      } catch {
        // Silently ignore polling errors — will retry next interval
      }
    }

    // Poll immediately, then at regular intervals
    poll()
    pollingIntervalRef.current = setInterval(poll, POLL_INTERVAL)
  }, [])

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }
    setIsPolling(false)
  }, [])

  const connect = useCallback(() => {
    // Get token from cookies using tokenUtils
    const token = tokenUtils.getToken()

    if (!token || !user) {
      console.log('No token or user, skipping WebSocket connection')
      return
    }

    // Don't reconnect if we already have an open connection
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return
    }

    // Don't reconnect if a connection is currently being established
    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) {
      return
    }

    intentionalCloseRef.current = false

    try {
      // Close existing connection if any
      if (wsRef.current) {
        wsRef.current.close()
      }

      const wsUrl = `${WEBSOCKET_URL}/api/notifications/ws?token=${token}`
      console.log('Connecting to WebSocket...')
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        setIsPolling(false)
        reconnectAttemptsRef.current = 0

        // Stop polling if we were using it as fallback
        stopPolling()

        // Start ping interval to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, 30000) // Ping every 30 seconds

        // Store ping interval for cleanup
        ws.pingInterval = pingInterval
      }

      ws.onmessage = (event) => {
        try {
          // Handle plain text "pong" responses to our pings
          if (event.data === 'pong') {
            return
          }
          const data = JSON.parse(event.data)
          setLastMessage(data)
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      ws.onerror = () => {
        // WebSocket error events don't carry useful messages — the onclose
        // handler below is where we decide whether to retry
        console.warn('WebSocket connection error')
      }

      ws.onclose = (event) => {
        console.log('WebSocket disconnected, code:', event.code, event.reason)
        setIsConnected(false)

        // Clear ping interval
        if (ws.pingInterval) {
          clearInterval(ws.pingInterval)
        }

        // Don't reconnect if we intentionally closed or user logged out
        if (intentionalCloseRef.current) {
          return
        }

        // Start polling immediately so the badge updates right away.
        // If WebSocket reconnects later, onopen will stop polling.
        startPolling()

        // Don't reconnect on policy violations (auth failed)
        if (event.code === 1008) {
          console.warn('WebSocket closed with policy violation (auth failed) — polling mode')
          return
        }

        // Attempt to reconnect with exponential backoff in the background.
        // If it succeeds, onopen will stop the polling fallback.
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = getReconnectDelay()
          reconnectAttemptsRef.current += 1
          console.log(`Attempting to reconnect (${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS}) in ${Math.round(delay)}ms...`)

          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, delay)
        } else {
          console.log('Max reconnection attempts reached — staying in polling mode')
        }
      }

    } catch (error) {
      console.error('Error establishing WebSocket connection:', error)
      startPolling()
    }
  }, [user, getReconnectDelay, startPolling, stopPolling])

  // Connect on mount and when user changes
  useEffect(() => {
    if (user) {
      connect()
    }

    // Cleanup on unmount
    return () => {
      intentionalCloseRef.current = true
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
      }
      if (wsRef.current) {
        if (wsRef.current.pingInterval) {
          clearInterval(wsRef.current.pingInterval)
        }
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, user])

  const sendMessage = useCallback((message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(message)
    } else {
      console.warn('WebSocket is not connected')
    }
  }, [])

  const markAsRead = useCallback((notificationId) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // Use WebSocket for immediate feedback
      sendMessage(`mark_read:${notificationId}`)
    }
    // Always also call the REST API to ensure the change is persisted
    // (handled by the notification context / react-query mutations)
  }, [sendMessage])

  return {
    isConnected,
    isPolling,
    lastMessage,
    sendMessage,
    markAsRead,
    reconnect: connect
  }
}