'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuth } from './auth-context'
import { tokenUtils } from './api'

// Clean up the WebSocket URL by removing any trailing paths
const getWebSocketURL = () => {
  const baseUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'
  // Remove any trailing /ws, /api, or other paths to ensure clean base URL
  return baseUrl.replace(/\/(ws|api).*$/, '')
}

const WEBSOCKET_URL = getWebSocketURL()

// Reconnection config — exponential backoff with jitter
const INITIAL_RECONNECT_DELAY = 1000   // 1 second initial delay
const MAX_RECONNECT_DELAY = 30000      // 30 seconds max delay
const BACKOFF_MULTIPLIER = 1.5
const MAX_RECONNECT_ATTEMPTS = 50      // Much higher limit — effectively keeps trying

export function useWebSocket() {
  const { user } = useAuth()
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState(null)
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)
  const intentionalCloseRef = useRef(false)

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
      console.log('Connecting to WebSocket:', wsUrl)
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        reconnectAttemptsRef.current = 0

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

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      ws.onclose = (event) => {
        console.log('WebSocket disconnected', event.code, event.reason)
        setIsConnected(false)

        // Clear ping interval
        if (ws.pingInterval) {
          clearInterval(ws.pingInterval)
        }

        // Don't reconnect if we intentionally closed or user logged out
        if (intentionalCloseRef.current) {
          return
        }

        // Don't reconnect on policy violations (auth failed) or normal closures
        // that indicate the server rejected us
        if (event.code === 1008) {
          console.warn('WebSocket closed with policy violation (auth failed), not reconnecting')
          return
        }

        // Attempt to reconnect with exponential backoff
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = getReconnectDelay()
          reconnectAttemptsRef.current += 1
          console.log(`Attempting to reconnect (${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS}) in ${Math.round(delay)}ms...`)

          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, delay)
        } else {
          console.log('Max reconnection attempts reached. Will retry on next user action or page refresh.')
        }
      }

    } catch (error) {
      console.error('Error establishing WebSocket connection:', error)
    }
  }, [user, getReconnectDelay])

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
    sendMessage(`mark_read:${notificationId}`)
  }, [sendMessage])

  return {
    isConnected,
    lastMessage,
    sendMessage,
    markAsRead,
    reconnect: connect
  }
}