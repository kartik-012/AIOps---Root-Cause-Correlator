import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * Custom hook connecting to backend WebSocket /api/v1/ws/incidents.
 * Receives live telemetry anomalies, incident correlations, and blast radius updates.
 */
export function useIncidentSocket(onEvent) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState(null)
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/api/v1/ws/incidents`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        console.log('[WebSocket] Connected to incident streaming channel')
      }

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          setLastEvent(payload)
          if (onEvent) onEvent(payload)
        } catch (err) {
          console.error('[WebSocket] Failed to parse message:', err)
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        console.log('[WebSocket] Disconnected, attempting reconnect in 3s...')
        reconnectTimeoutRef.current = setTimeout(connect, 3000)
      }

      ws.onerror = (err) => {
        console.warn('[WebSocket] Connection error:', err)
        ws.close()
      }
    } catch (e) {
      console.warn('[WebSocket] Init error:', e)
      reconnectTimeoutRef.current = setTimeout(connect, 3000)
    }
  }, [onEvent])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])

  const send = useCallback((data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  return { isConnected, lastEvent, send }
}
