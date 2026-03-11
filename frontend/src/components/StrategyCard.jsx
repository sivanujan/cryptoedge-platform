import { useState, useEffect } from 'react'
import { Activity, Play, RefreshCw, BarChart2, Cpu, CheckCircle, AlertCircle, Trash2 } from 'lucide-react'
import { API } from '../lib/api'

export default function StrategyCard({ strategy, onClick, onRunBacktest, onRefresh }) {
    const [running, setRunning] = useState(false)
    const [done, setDone] = useState(false)
    const [converting, setConverting] = useState(false)
    const [convertDone, setConvertDone] = useState(false)
    const [convertError, setConvertError] = useState(null)
    const [summary, setSummary] = useState(null)
    const [deleting, setDeleting] = useState(false)

    const {
        id,
        name = 'Strategy',
        description = '',
        coin_count = 0,
        avg_win_rate = 0,
        parameters = {},
        has_pine_script = false,
        has_python_code = false,
    } = strategy || {}

    useEffect(() => {
        if (!String(id).startsWith('local_')) {
            API.getBacktestSummary?.(id).then(res => {
                if (res && res.total_coins_tested > 0) {
                    setSummary(res)
                }
            }).catch(e => console.error("Summary fetch error", e))
        }
    }, [id])

    const wr = summary ? summary.best_win_rate : (Number(avg_win_rate) || 0)
    let wrColor = 'var(--text-dim)'
    let wrText = '—'

    if (wr > 0) {
        if (wr >= 65) wrColor = 'var(--green)'
        else if (wr >= 50) wrColor = 'var(--yellow)'
        else wrColor = 'var(--red)'
        wrText = `${wr.toFixed(1)}%`
    }

    const hasRun = !!summary || (wr > 0 || coin_count > 0 || done)

    const handleRunClick = async (e) => {
        e.stopPropagation()
        if (running) return
        setRunning(true)
        try {
            if (onRunBacktest) {
                // Fire and don't await — the progress modal in StrategyLibrary takes over
                onRunBacktest(id)
            }
        } finally {
            // Reset the button quickly; the modal handles tracking from here
            setTimeout(() => setRunning(false), 800)
        }
    }

    const handleConvertClick = async (e) => {
        e.stopPropagation()
        if (converting) return
        setConverting(true)
        setConvertError(null)
        try {
            await API.convertPineScript(id)
            setConvertDone(true)
            if (onRefresh) onRefresh()
        } catch (err) {
            const msg = err.response?.data?.detail || 'Conversion failed'
            setConvertError(msg)
        } finally {
            setConverting(false)
        }
    }

    const handleDeleteClick = async (e) => {
        e.stopPropagation()
        if (window.confirm(`Are you sure you want to delete "${name}"?`)) {
            setDeleting(true)
            try {
                await API.deleteStrategy(id)
                if (onRefresh) onRefresh()
            } catch (err) {
                console.error("Delete failed", err)
                setDeleting(false)
            }
        }
    }

    const tfs = ['5m', '15m', '1h', '2h', '4h', '1d']

    return (
        <div
            className="card"
            onClick={onClick}
            style={{
                padding: 20, cursor: 'pointer',
                display: 'flex', flexDirection: 'column', gap: 14,
                transition: 'all 0.2s', position: 'relative', overflow: 'hidden',
                minHeight: 280, height: '100%'
            }}
            onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'var(--cyan-dim)'
                e.currentTarget.style.boxShadow = '0 4px 24px var(--cyan-glow)'
                e.currentTarget.style.transform = 'translateY(-2px)'
            }}
            onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'var(--border)'
                e.currentTarget.style.boxShadow = 'none'
                e.currentTarget.style.transform = 'none'
            }}
        >
            <div style={{ position: 'absolute', top: -20, right: -20, width: 80, height: 80, background: 'var(--cyan-glow)', borderRadius: '50%', filter: 'blur(20px)', pointerEvents: 'none' }} />

            {/* Top row: Icon + Win Rate */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(0,229,255,0.1)', border: '1px solid rgba(0,229,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Activity size={18} color="var(--cyan)" />
                    </div>
                    <div>
                        <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 16, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                            {name}
                            {!String(id).startsWith('local_') && (
                                <button
                                    onClick={handleDeleteClick}
                                    disabled={deleting}
                                    style={{
                                        background: 'transparent', border: 'none', color: 'var(--text-dim)', 
                                        cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center', 
                                        justifyContent: 'center', borderRadius: 4, opacity: 0.6,
                                        transition: 'all 0.2s'
                                    }}
                                    onMouseEnter={e => { e.currentTarget.style.color = 'var(--red)'; e.currentTarget.style.opacity = 1; e.currentTarget.style.background = 'rgba(239,68,68,0.1)' }}
                                    onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-dim)'; e.currentTarget.style.opacity = 0.6; e.currentTarget.style.background = 'transparent' }}
                                    title="Delete Strategy"
                                >
                                    {deleting ? <RefreshCw size={14} className="animate-spin" /> : <Trash2 size={14} />}
                                </button>
                            )}
                        </div>
                    </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 700, color: wr > 0 ? wrColor : 'var(--text-dim)' }}>
                        {wr > 0 ? wrText : 'No data'}
                    </div>
                    {wr > 0 && <div style={{ fontSize: 9, color: 'var(--text-dim)', letterSpacing: '0.06em', fontWeight: 600 }}>BEST WIN RATE</div>}
                </div>
            </div>

            {/* Name + Desc */}
            <div style={{ flex: 1 }}>
                {description ? (
                    <div style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 12, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        {description}
                    </div>
                ) : (
                    <div style={{ display: 'inline-block', marginBottom: 12, padding: '2px 8px', borderRadius: 12, background: 'var(--bg-secondary)', border: '1px solid var(--border)', fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                        Technical Indicator
                    </div>
                )}
            </div>

            <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />

            {/* Timeframe Timeline */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0' }}>
                {tfs.map(tf => {
                    const tfWr = summary?.avg_win_rate_by_timeframe?.[tf]
                    const isBest = summary?.best_timeframe_overall === tf

                    let color = 'var(--text-dim)'
                    if (tfWr) {
                        if (tfWr >= 65) color = 'var(--green)'
                        else if (tfWr >= 50) color = 'var(--yellow)'
                        else color = 'var(--red)'
                    }

                    return (
                        <div key={tf} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: isBest ? 'var(--cyan)' : 'var(--text-secondary)', fontWeight: isBest ? 700 : 400 }}>{tf}</div>
                            <div style={{
                                fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color,
                                background: isBest ? 'rgba(0,229,255,0.1)' : 'transparent',
                                padding: '2px 4px', borderRadius: 4,
                                border: isBest ? '1px solid var(--cyan-dim)' : '1px solid transparent'
                            }}>
                                {tfWr ? `${tfWr.toFixed(0)}%` : '—'}
                            </div>
                        </div>
                    )
                })}
            </div>

            <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />

            {/* Stats summary row */}
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)', textAlign: 'center' }}>
                {summary ? (
                    <span><strong style={{ color: 'var(--text-primary)' }}>{summary.total_coins_tested}</strong> coins tested · <strong style={{ color: 'var(--green)' }}>{summary.coins_above_65}</strong> above 65%</span>
                ) : hasRun ? (
                    <span><strong style={{ color: 'var(--text-primary)' }}>{coin_count}</strong> assigned coins</span>
                ) : (
                    <span style={{ color: 'var(--text-dim)' }}>Ready to backtest</span>
                )}
            </div>

            {/* Status bar */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, paddingTop: 4, marginTop: 'auto', flexWrap: 'wrap' }}>
                {/* AI Convert button — only for Pine Script strategies without Python code */}
                {has_pine_script && !has_python_code && !convertDone && (
                    <button
                        onClick={handleConvertClick}
                        disabled={converting}
                        className="btn-ghost"
                        style={{
                            padding: '6px 14px', fontSize: 12, minHeight: 32,
                            gap: 6, width: '100%', display: 'flex', justifyContent: 'center',
                            marginBottom: 6,
                            background: converting ? 'rgba(139,92,246,0.1)' : 'rgba(139,92,246,0.15)',
                            borderColor: 'rgba(139,92,246,0.4)',
                            color: '#a78bfa',
                        }}
                    >
                        {converting ? <RefreshCw size={13} className="animate-spin" /> : <Cpu size={13} />}
                        <span>{converting ? 'AI Converting (~30s)...' : '🤖 Convert Pine Script with AI'}</span>
                    </button>
                )}
                {convertDone && (
                    <div style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 6, color: 'var(--green)', fontSize: 12, fontFamily: 'var(--font-mono)', justifyContent: 'center', marginBottom: 6 }}>
                        <CheckCircle size={14} /> Strategy converted! Ready to backtest.
                    </div>
                )}
                {convertError && (
                    <div style={{ width: '100%', color: 'var(--red)', fontSize: 11, fontFamily: 'var(--font-mono)', marginBottom: 6, textAlign: 'center' }}>
                        <AlertCircle size={12} style={{ display: 'inline', marginRight: 4 }} />{convertError}
                    </div>
                )}

                <button
                    onClick={handleRunClick}
                    disabled={running || String(id).startsWith('local_')}
                    className={running ? "btn-ghost" : done ? "btn-ghost" : "btn-primary"}
                    style={{ padding: '6px 14px', fontSize: 12, minHeight: 32, gap: 6, flex: 1, display: 'flex', justifyContent: 'center', whiteSpace: 'nowrap' }}
                >
                    {running ? <RefreshCw size={14} className="animate-spin" /> : done ? null : <Play size={14} />}
                    <span style={{ whiteSpace: 'nowrap' }}>
                        {running ? 'Running...' : done ? 'Backtest Done ✓' : 'Run Full Backtest'}
                    </span>
                </button>

                <button
                    onClick={onClick}
                    className="btn-ghost"
                    style={{ padding: '6px 14px', fontSize: 12, minHeight: 32, gap: 6, flex: 1, display: 'flex', justifyContent: 'center', whiteSpace: 'nowrap' }}
                >
                    <BarChart2 size={14} />
                    View Table
                </button>
            </div>
        </div>
    )
}
