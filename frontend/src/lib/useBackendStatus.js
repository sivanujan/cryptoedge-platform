import { useState, useEffect, useRef, useCallback } from 'react'
import toast from 'react-hot-toast'

const CHECK_INTERVAL = 10_000  // poll every 10s
const FAIL_THRESHOLD = 3       // require 3 consecutive failures before showing DISCONNECTED
const REQUEST_TIMEOUT = 6_000  // 6s per health check (backtest can make backend slow)

export function useBackendStatus() {
    const [online, setOnline] = useState(null) // null = checking
    const prevRef = useRef(null)
    const failCount = useRef(0)
    const timerRef = useRef(null)

    const check = useCallback(async () => {
        try {
            const res = await fetch('/health', {
                signal: AbortSignal.timeout(REQUEST_TIMEOUT),
            })

            if (res.ok) {
                failCount.current = 0
                setOnline(true)
                if (prevRef.current === false) {
                    toast.success('Backend connected ✓', { id: 'backend-status' })
                }
                prevRef.current = true
            } else {
                // Non-2xx response counts as a soft failure
                failCount.current += 1
                if (failCount.current >= FAIL_THRESHOLD) {
                    setOnline(false)
                    if (prevRef.current === true) {
                        toast.error('Backend disconnected', { id: 'backend-status' })
                    }
                    prevRef.current = false
                }
            }
        } catch {
            // Network error or timeout
            failCount.current += 1
            if (failCount.current >= FAIL_THRESHOLD) {
                setOnline(false)
                if (prevRef.current === true || prevRef.current === null) {
                    toast.error('Backend disconnected', { id: 'backend-status' })
                }
                prevRef.current = false
            }
        }
    }, [])

    useEffect(() => {
        check()
        timerRef.current = setInterval(check, CHECK_INTERVAL)
        return () => clearInterval(timerRef.current)
    }, [check])

    return online
}
