import { useEffect, useRef, useState, useCallback } from 'react'

// Use relative path via Vite proxy so WS goes through the same host/port
function getWsUrl(path) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}${path}`
}

function createReconnectingWs(path, onMessage, onOpen, onClose) {
    let ws = null
    let retryTimeout = null
    let destroyed = false

    function connect() {
        if (destroyed) return
        try {
            ws = new WebSocket(getWsUrl(path))
            ws.onopen = () => !destroyed && onOpen && onOpen()
            ws.onclose = () => {
                if (!destroyed) {
                    onClose && onClose()
                    retryTimeout = setTimeout(connect, 3000)
                }
            }
            ws.onerror = () => { /* handled by onclose */ }
            ws.onmessage = (e) => {
                if (!destroyed) {
                    try { onMessage(JSON.parse(e.data)) } catch { }
                }
            }
        } catch {
            if (!destroyed) retryTimeout = setTimeout(connect, 3000)
        }
    }

    connect()

    return {
        destroy() {
            destroyed = true
            clearTimeout(retryTimeout)
            if (ws) {
                ws.onclose = null
                ws.close()
            }
        }
    }
}

// Price WebSocket hook
export function usePriceSocket() {
    const [prices, setPrices] = useState({})
    const [connected, setConnected] = useState(false)
    const wsRef = useRef(null)

    useEffect(() => {
        wsRef.current = createReconnectingWs(
            '/ws/prices',
            (data) => {
                if (data.type === 'prices' && data.data) {
                    setPrices((prev) => ({ ...prev, ...data.data }))
                }
            },
            () => setConnected(true),
            () => setConnected(false),
        )
        return () => wsRef.current?.destroy()
    }, [])

    return { prices, connected }
}

// Signal WebSocket hook
export function useSignalSocket(onSignal) {
    const [connected, setConnected] = useState(false)
    const wsRef = useRef(null)
    const cbRef = useRef(onSignal)
    cbRef.current = onSignal

    useEffect(() => {
        wsRef.current = createReconnectingWs(
            '/ws/signals',
            (data) => {
                if (data.type !== 'ping' && cbRef.current) cbRef.current(data)
            },
            () => setConnected(true),
            () => setConnected(false),
        )
        return () => wsRef.current?.destroy()
    }, [])

    return { connected }
}
