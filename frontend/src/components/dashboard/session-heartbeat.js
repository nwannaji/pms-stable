'use client'

import { useEffect, useRef } from 'react'
import { auth } from '@/lib/api'

const PING_INTERVAL_MS = 120_000 // 2 min
const JITTER_MS = 15_000 // 0-15s, so many tabs don't ping in lockstep

/**
 * Session heartbeat — pings POST /api/auth/heartbeat every ~2 min while a
 * dashboard tab is visible so time-on-platform analytics work even when the
 * user never logs out. Completely silent: no toasts, no retry storm; if a
 * ping fails (network/token), the next one simply tries again.
 *
 * Renders nothing.
 */
export function SessionHeartbeat() {
  const pingRef = useRef(null)

  useEffect(() => {
    let timer = null

    const ping = (keepalive = false) => {
      // apiRequest can't be reused here when keepalive is needed; use the
      // auth client otherwise so 401 flows through the refresh-and-retry.
      pingRef.current = auth.heartbeat().catch(() => {})
    }

    const start = () => {
      if (timer) return
      const delay = PING_INTERVAL_MS + Math.random() * JITTER_MS
      timer = setInterval(ping, delay)
    }

    const stop = () => {
      if (timer) {
        clearInterval(timer)
        timer = null
      }
    }

    const onVisibilityChange = () => {
      if (document.hidden) {
        stop()
      } else {
        ping() // catch up immediately on return
        start()
      }
    }

    ping() // initial ping on mount
    start()
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [])

  return null
}