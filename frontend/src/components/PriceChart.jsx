import { useEffect, useRef, Component, useState, useCallback } from 'react'
import {
    createChart,
    ColorType,
    CrosshairMode,
    CandlestickSeries,
} from 'lightweight-charts'
import { RefreshCw } from 'lucide-react'

// ─── Constants ──────────────────────────────
const TIMEFRAMES = [
    { label: '1m', interval: '1m' },
    { label: '5m', interval: '5m' },
    { label: '15m', interval: '15m' },
    { label: '1h', interval: '1h' },
    { label: '4h', interval: '4h' },
    { label: '1d', interval: '1d' },
]

const COINS = [
    { label: 'BTC', symbol: 'BTCUSDT' },
    { label: 'ETH', symbol: 'ETHUSDT' },
    { label: 'BNB', symbol: 'BNBUSDT' },
    { label: 'SOL', symbol: 'SOLUSDT' },
    { label: 'XRP', symbol: 'XRPUSDT' },
    { label: 'ADA', symbol: 'ADAUSDT' },
    { label: 'DOGE', symbol: 'DOGEUSDT' },
    { label: 'AVAX', symbol: 'AVAXUSDT' },
    { label: 'MATIC', symbol: 'MATICUSDT' },
    { label: 'DOT', symbol: 'DOTUSDT' },
]

// ─── Binance klines fetch ──────────────────
async function fetchBinanceKlines(symbol, interval, limit = 200) {
    const url = `https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`
    const res = await fetch(url, { signal: AbortSignal.timeout(8000) })
    if (!res.ok) throw new Error(`Binance API error: ${res.status}`)
    const raw = await res.json()
    // [openTime, open, high, low, close, volume, ...]
    return raw.map(k => ({
        time: Math.floor(k[0] / 1000),
        open: parseFloat(k[1]),
        high: parseFloat(k[2]),
        low: parseFloat(k[3]),
        close: parseFloat(k[4]),
    }))
}

// ─── Error boundary ───────────────────────
class ChartErrorBoundary extends Component {
    constructor(props) { super(props); this.state = { hasError: false } }
    static getDerivedStateFromError() { return { hasError: true } }
    render() {
        if (this.state.hasError) return (
            <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 8, background: '#111827' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-dim)' }}>Chart error</div>
            </div>
        )
        return this.props.children
    }
}

// ─── Inner chart component ────────────────
function PriceChartInner({ data }) {
    const containerRef = useRef(null)
    const chartRef = useRef(null)
    const seriesRef = useRef(null)

    useEffect(() => {
        if (!containerRef.current) return
        if (chartRef.current) { try { chartRef.current.remove() } catch { } }

        const chart = createChart(containerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#111827' },
                textColor: '#8899bb',
                fontFamily: "'Space Mono', monospace",
                fontSize: 11,
            },
            grid: {
                vertLines: { color: '#1e2d4a', style: 1 },
                horzLines: { color: '#1e2d4a', style: 1 },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: { color: '#00e5ff', labelBackgroundColor: '#090e1a' },
                horzLine: { color: '#00e5ff', labelBackgroundColor: '#090e1a' },
            },
            rightPriceScale: { borderColor: '#1e2d4a', textColor: '#8899bb' },
            timeScale: { borderColor: '#1e2d4a', textColor: '#8899bb', timeVisible: true, secondsVisible: false },
            handleScroll: true,
            handleScale: true,
            width: containerRef.current.clientWidth || 600,
            height: containerRef.current.clientHeight || 300,
        })

        const series = chart.addSeries(CandlestickSeries, {
            upColor: '#00e676', downColor: '#ff1744',
            borderUpColor: '#00e676', borderDownColor: '#ff1744',
            wickUpColor: '#00e676', wickDownColor: '#ff1744',
        })

        chartRef.current = chart
        seriesRef.current = series

        if (data?.length) {
            try { series.setData(data); chart.timeScale().fitContent() } catch { }
        }

        const ro = new ResizeObserver(() => {
            if (containerRef.current && chartRef.current) {
                try { chartRef.current.applyOptions({ width: containerRef.current.clientWidth, height: containerRef.current.clientHeight }) } catch { }
            }
        })
        ro.observe(containerRef.current)
        return () => { ro.disconnect(); try { chart.remove() } catch { } }
    }, []) // eslint-disable-line

    useEffect(() => {
        if (!seriesRef.current || !data?.length) return
        try { seriesRef.current.setData(data); chartRef.current?.timeScale().fitContent() } catch { }
    }, [data])

    return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
}

// ─── Main exported component ───────────────
export default function PriceChart() {
    const [selectedCoin, setSelectedCoin] = useState(COINS[0])
    const [selectedTf, setSelectedTf] = useState(TIMEFRAMES[3]) // 1h default
    const [candles, setCandles] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchCandles = useCallback(async (coin, tf) => {
        setLoading(true)
        setError(null)
        try {
            const data = await fetchBinanceKlines(coin.symbol, tf.interval)
            setCandles(data)
        } catch (e) {
            setError('Failed to load chart data. Check your connection.')
            console.warn('Binance klines fetch failed:', e)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchCandles(selectedCoin, selectedTf)
    }, [selectedCoin, selectedTf, fetchCandles])

    return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* ── Toolbar ── */}
            <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 12px',
                borderBottom: '1px solid var(--border)',
                flexShrink: 0,
                flexWrap: 'wrap',
            }}>
                {/* Coin selector */}
                <select
                    value={selectedCoin.symbol}
                    onChange={e => setSelectedCoin(COINS.find(c => c.symbol === e.target.value))}
                    style={{
                        background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                        borderRadius: 6, color: 'var(--cyan)', fontFamily: 'var(--font-mono)',
                        fontSize: 12, padding: '4px 8px', cursor: 'pointer', outline: 'none',
                    }}
                >
                    {COINS.map(c => (
                        <option key={c.symbol} value={c.symbol}>{c.label}/USDT</option>
                    ))}
                </select>

                {/* Divider */}
                <div style={{ width: 1, height: 18, background: 'var(--border)' }} />

                {/* Timeframe buttons */}
                {TIMEFRAMES.map(tf => (
                    <button
                        key={tf.interval}
                        onClick={() => setSelectedTf(tf)}
                        style={{
                            fontFamily: 'var(--font-mono)', fontSize: 11,
                            padding: '3px 10px', borderRadius: 5, border: 'none', cursor: 'pointer',
                            transition: 'all 0.15s',
                            background: selectedTf.interval === tf.interval
                                ? 'rgba(0,229,255,0.18)'
                                : 'var(--bg-secondary)',
                            color: selectedTf.interval === tf.interval
                                ? 'var(--cyan)'
                                : 'var(--text-dim)',
                            boxShadow: selectedTf.interval === tf.interval
                                ? '0 0 8px rgba(0,229,255,0.2)'
                                : 'none',
                            fontWeight: selectedTf.interval === tf.interval ? 700 : 400,
                        }}
                    >
                        {tf.label}
                    </button>
                ))}

                {/* Spacer */}
                <div style={{ flex: 1 }} />

                {/* Refresh button */}
                <button
                    onClick={() => fetchCandles(selectedCoin, selectedTf)}
                    disabled={loading}
                    title="Refresh chart"
                    style={{
                        background: 'none', border: '1px solid var(--border)', borderRadius: 5,
                        padding: '3px 8px', cursor: 'pointer', color: 'var(--text-dim)',
                        display: 'flex', alignItems: 'center', gap: 4,
                    }}
                >
                    <RefreshCw size={11} style={{ animation: loading ? 'spin 0.8s linear infinite' : 'none' }} />
                </button>

                {/* Coin + TF label */}
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                    {selectedCoin.label}/USDT · {selectedTf.label} · Binance
                </span>
            </div>

            {/* ── Chart area ── */}
            <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
                {loading && (
                    <div style={{
                        position: 'absolute', inset: 0, background: '#111827',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        zIndex: 5,
                    }}>
                        <div style={{
                            width: 28, height: 28,
                            border: '2px solid var(--border)',
                            borderTop: '2px solid var(--cyan)',
                            borderRadius: '50%',
                            animation: 'spin 0.8s linear infinite',
                        }} />
                    </div>
                )}
                {error && !loading && (
                    <div style={{
                        position: 'absolute', inset: 0, background: '#111827',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexDirection: 'column', gap: 6, zIndex: 5,
                    }}>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--red)' }}>{error}</div>
                        <button className="btn-ghost" style={{ fontSize: 11 }} onClick={() => fetchCandles(selectedCoin, selectedTf)}>
                            Retry
                        </button>
                    </div>
                )}
                <ChartErrorBoundary>
                    {candles.length > 0 && <PriceChartInner data={candles} />}
                </ChartErrorBoundary>
            </div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    )
}
