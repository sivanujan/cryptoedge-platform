import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, X, Trash2, LayoutGrid, Search, Filter, ChevronDown, ChevronUp, Download, Play, Activity, Settings, RefreshCw, BarChart2 } from 'lucide-react'
import { API } from '../lib/api'
import StrategyCard from '../components/StrategyCard'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'

const TF_OPTIONS = ['1m', '5m', '15m', '1h', '4h', '1d']
const LOCAL_KEY = 'cryptoedge_local_strategies'

// Load locally saved strategies (offline fallback)
function loadLocalStrategies() {
    try { return JSON.parse(localStorage.getItem(LOCAL_KEY) || '[]') } catch { return [] }
}
function saveLocalStrategy(s) {
    const existing = loadLocalStrategies()
    const updated = [{ ...s, id: `local_${Date.now()}`, coin_count: 0, avg_win_rate: 0 }, ...existing]
    localStorage.setItem(LOCAL_KEY, JSON.stringify(updated))
    return updated
}
function deleteLocalStrategy(id) {
    const existing = loadLocalStrategies()
    const updated = existing.filter(s => s.id !== id)
    localStorage.setItem(LOCAL_KEY, JSON.stringify(updated))
    return updated
}

// ─── Admin Debug Panel ───────────────────────────────────────────
function DebugPanel({ onClose }) {
    const [allStrategies, setAllStrategies] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')

    useEffect(() => {
        API.getAllStrategies()
            .then(data => setAllStrategies(data.strategies || []))
            .catch(err => setError(err?.response?.data?.detail || 'Failed to load'))
            .finally(() => setLoading(false))
    }, [])

    const handleReactivate = async (id) => {
        try {
            await API.reactivateStrategy(id)
            const data = await API.getAllStrategies()
            setAllStrategies(data.strategies || [])
            toast.success('Strategy reactivated!')
        } catch (err) {
            toast.error('Failed to reactivate')
        }
    }

    const handleDelete = async (id) => {
        if (!window.confirm('Delete this strategy permanently?')) return
        try {
            await API.deleteStrategy(id)
            setAllStrategies(prev => prev.filter(s => s.id !== id))
            toast.success('Strategy deleted!')
        } catch (err) {
            toast.error('Failed to delete')
        }
    }

    return (
        <div style={{
            position: 'fixed', inset: 0, zIndex: 200,
            background: 'rgba(9,14,26,0.92)', backdropFilter: 'blur(6px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
            <div className="card" style={{ width: 600, maxHeight: '80vh', overflow: 'auto', padding: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                    <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>All Strategies (Debug)</h3>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)' }}><X size={18} /></button>
                </div>
                {loading ? <LoadingSpinner text="Loading..." /> : error ? <div style={{ color: 'var(--red)' }}>{error}</div> : (
                    <div>
                        {allStrategies.length === 0 ? <div style={{ color: 'var(--text-dim)' }}>No strategies found</div> : (
                            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                <thead>
                                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                        <th style={{ textAlign: 'left', padding: '8px', color: 'var(--text-dim)', fontSize: 11 }}>ID</th>
                                        <th style={{ textAlign: 'left', padding: '8px', color: 'var(--text-dim)', fontSize: 11 }}>Name</th>
                                        <th style={{ textAlign: 'left', padding: '8px', color: 'var(--text-dim)', fontSize: 11 }}>Status</th>
                                        <th style={{ textAlign: 'left', padding: '8px', color: 'var(--text-dim)', fontSize: 11 }}>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {allStrategies.map(s => (
                                        <tr key={s.id} style={{ borderBottom: '1px solid var(--border)', background: s.is_active ? 'transparent' : 'rgba(255,51,102,0.1)' }}>
                                            <td style={{ padding: '8px', fontFamily: 'var(--font-mono)', fontSize: 12 }}>{s.id}</td>
                                            <td style={{ padding: '8px' }}>{s.name}</td>
                                            <td style={{ padding: '8px' }}>
                                                <span style={{ padding: '2px 8px', borderRadius: 4, background: s.is_active ? 'rgba(0,255,170,0.2)' : 'rgba(255,51,102,0.2)', color: s.is_active ? 'var(--green)' : 'var(--red)', fontSize: 11 }}>
                                                    {s.is_active ? 'Active' : 'Inactive'}
                                                </span>
                                            </td>
                                            <td style={{ padding: '8px' }}>
                                                {!s.is_active && (
                                                    <button onClick={() => handleReactivate(s.id)} style={{ marginRight: 8, padding: '4px 10px', fontSize: 11 }} className="btn-primary">Reactivate</button>
                                                )}
                                                <button onClick={() => handleDelete(s.id)} style={{ padding: '4px 10px', fontSize: 11 }} className="btn-ghost">Delete</button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}

// ─── Add Strategy Modal ────────────────────────────────────────
function AddStrategyModal({ onClose, onSave, isOffline }) {
    const [form, setForm] = useState({
        name: '',
        description: '',
        timeframes: ['1h'],
        pine_script: '',
    })
    const [params, setParams] = useState([{ key: '', value: '' }])
    const [saving, setSaving] = useState(false)

    const toggleTf = (tf) => {
        setForm(f => ({
            ...f,
            timeframes: f.timeframes.includes(tf)
                ? f.timeframes.filter(t => t !== tf)
                : [...f.timeframes, tf],
        }))
    }

    const addParam = () => setParams(p => [...p, { key: '', value: '' }])
    const removeParam = (i) => setParams(p => p.filter((_, idx) => idx !== i))
    const setParam = (i, field, val) => setParams(p => p.map((row, idx) => idx === i ? { ...row, [field]: val } : row))

    const handleSubmit = async (e) => {
        e.preventDefault()
        if (!form.name.trim()) { toast.error('Strategy name is required'); return }

        const parameters = {}
        params.filter(p => p.key.trim()).forEach(p => { parameters[p.key.trim()] = p.value })

        // Only send fields expected by the backend API
        const payload = {
            name: form.name.trim(),
            description: form.description.trim() || null,
            pine_script: form.pine_script.trim() || null,
            parameters: Object.keys(parameters).length > 0 ? parameters : null,
        }
        setSaving(true)
        try {
            await onSave(payload)
            onClose()
        } catch {
            // Handled by onSave
        } finally {
            setSaving(false)
        }
    }

    return (
        <div style={{
            position: 'fixed', inset: 0, zIndex: 100,
            background: 'rgba(9,14,26,0.88)', backdropFilter: 'blur(6px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={e => e.target === e.currentTarget && onClose()}>
            <div className="card" style={{ width: 580, maxHeight: '88vh', overflowY: 'auto', padding: 28, position: 'relative' }}>
                <button onClick={onClose} style={{ position: 'absolute', top: 14, right: 14, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)' }}>
                    <X size={18} />
                </button>
                <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 18, marginBottom: 20, color: 'var(--text-primary)' }}>
                    Add New Strategy
                </div>

                {isOffline && (
                    <div style={{
                        marginBottom: 16, padding: '8px 12px', borderRadius: 6,
                        background: 'rgba(255,214,0,0.08)', border: '1px solid rgba(255,214,0,0.2)',
                        fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--yellow)',
                    }}>
                        ⚡ Backend offline — strategy will be saved locally and synced when online
                    </div>
                )}

                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <div>
                        <label style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.07em', display: 'block', marginBottom: 5 }}>STRATEGY NAME *</label>
                        <input className="cyber-input" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. RSI Divergence" required />
                    </div>
                    <div>
                        <label style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.07em', display: 'block', marginBottom: 5 }}>DESCRIPTION</label>
                        <textarea className="cyber-input" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Describe the strategy logic..." rows={2} style={{ resize: 'vertical' }} />
                    </div>
                    <div>
                        <label style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.07em', display: 'block', marginBottom: 8 }}>TIMEFRAMES</label>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                            {TF_OPTIONS.map(tf => (
                                <button
                                    key={tf} type="button"
                                    onClick={() => toggleTf(tf)}
                                    style={{
                                        fontFamily: 'var(--font-mono)', fontSize: 11, padding: '4px 12px',
                                        borderRadius: 5, border: '1px solid', cursor: 'pointer', transition: 'all 0.15s',
                                        background: form.timeframes.includes(tf) ? 'rgba(0,229,255,0.18)' : 'var(--bg-secondary)',
                                        color: form.timeframes.includes(tf) ? 'var(--cyan)' : 'var(--text-dim)',
                                        borderColor: form.timeframes.includes(tf) ? 'rgba(0,229,255,0.4)' : 'var(--border)',
                                        fontWeight: form.timeframes.includes(tf) ? 700 : 400,
                                    }}
                                >
                                    {tf}
                                </button>
                            ))}
                        </div>
                    </div>
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                            <label style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.07em' }}>PARAMETERS</label>
                            <button type="button" onClick={addParam} style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', color: 'var(--cyan)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                                + Add Row
                            </button>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {params.map((row, i) => (
                                <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                                    <input className="cyber-input" placeholder="key" value={row.key} onChange={e => setParam(i, 'key', e.target.value)} style={{ flex: 1 }} />
                                    <input className="cyber-input" placeholder="value" value={row.value} onChange={e => setParam(i, 'value', e.target.value)} style={{ flex: 1 }} />
                                    <button type="button" onClick={() => removeParam(i)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--red)', padding: 4 }}>
                                        <Trash2 size={12} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div>
                        <label style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.07em', display: 'block', marginBottom: 5 }}>PINE SCRIPT (optional)</label>
                        <textarea className="cyber-input" value={form.pine_script} onChange={e => setForm(f => ({ ...f, pine_script: e.target.value }))} placeholder={`//@version=5\nstrategy("My Strategy", overlay=true)\n// Paste your Pine Script here...`} rows={7} style={{ resize: 'vertical', fontFamily: 'var(--font-mono)', fontSize: 11 }} />
                    </div>
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
                        <button type="submit" className="btn-primary" disabled={saving}>
                            {saving ? 'Saving...' : isOffline ? 'Save Locally' : 'Save Strategy'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

// ─── Progress Modal ─────────────────────────────────────────────
function BacktestProgressModal({ strategyName, jobId, onClose, onComplete }) {
    const [progress, setProgress] = useState(null)
    const [failed, setFailed] = useState(false)
    const [failMsg, setFailMsg] = useState('')
    const [elapsed, setElapsed] = useState(0)

    // Track elapsed seconds while initializing
    useEffect(() => {
        const timer = setInterval(() => setElapsed(s => s + 1), 1000)
        return () => clearInterval(timer)
    }, [])

    useEffect(() => {
        let interval = setInterval(async () => {
            try {
                const data = await API.getBacktestProgress(jobId)
                setProgress(data)
                if (data.status === 'complete') {
                    clearInterval(interval)
                    setTimeout(() => onComplete(), 1500)
                } else if (data.status === 'error') {
                    clearInterval(interval)
                    setFailed(true)
                    setFailMsg(data.message || 'Unknown error')
                }
            } catch (err) {
                // If job not found (404), show error
                if (err?.response?.status === 404) {
                    setFailMsg('Job not found — the backend may have restarted. Please click Run Backtest again.')
                    setFailed(true)
                    clearInterval(interval)
                }
                // For timeouts/network errors just skip
            }
        }, 2000)
        return () => clearInterval(interval)
    }, [jobId, onComplete])

    const totalTests = progress?.total_tests || 0
    const completed = progress?.completed || 0
    const pct = totalTests > 0 ? Math.min((completed / totalTests) * 100, 100) : 0
    const eta = totalTests > 0 ? Math.ceil(((totalTests - completed) * 0.15) / 60) : 0

    return (
        <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(9,14,26,0.85)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div className="card" style={{ width: 440, padding: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                    <div className="pulse-dot" style={{ background: failed ? 'var(--red)' : progress?.status === 'complete' ? 'var(--green)' : 'var(--cyan)' }}></div>
                    <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 16 }}>
                        {failed ? 'Backtest Failed' : progress?.status === 'complete' ? 'Backtest Complete' : `Running Backtest — ${strategyName}`}
                    </div>
                </div>

                {failed ? (
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--red)', textAlign: 'center', padding: 16 }}>
                        {failMsg}<br/>
                        <button className="btn-ghost" onClick={onClose} style={{ marginTop: 12, padding: '6px 20px' }}>Close</button>
                    </div>
                ) : progress ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                        <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', marginBottom: 6 }}>
                                <span>Progress: {completed} / {totalTests || '...'} tests</span>
                                <span>{totalTests > 0 ? `${pct.toFixed(1)}%` : 'Initializing...'}</span>
                            </div>
                            <div style={{ height: 6, background: 'var(--bg-secondary)', borderRadius: 3, overflow: 'hidden' }}>
                                <div style={{ height: '100%', width: `${pct}%`, background: 'var(--cyan)', transition: 'width 0.5s linear' }}></div>
                            </div>
                        </div>

                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>
                            Current: <strong>{progress.current_coin}</strong> on <strong>{progress.current_tf}</strong>...
                        </div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', padding: 12, background: 'var(--bg-secondary)', borderRadius: 6 }}>
                            <div style={{ color: 'var(--cyan)' }}>{progress.message}</div>
                            {progress.best_coin && <div style={{ marginTop: 4 }}>Best coin found: {progress.best_coin}</div>}
                            <div style={{ marginTop: 4 }}>Coins above 65%: {progress.coins_above_65} so far</div>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)' }}>
                                {progress.status === 'running' ? `Estimated: ~${eta} min remaining` : ''}
                            </span>
                            <button className="btn-ghost" onClick={onClose} style={{ padding: '4px 12px', fontSize: 12 }}>
                                {progress.status === 'complete' || failed ? 'Close' : 'Cancel UI'}
                            </button>
                        </div>
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 20, gap: 10 }}>
                        <LoadingSpinner text="Initializing backtest..." />
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)' }}>
                            Waiting for first data... ({elapsed}s)
                        </div>
                        {elapsed > 20 && (
                            <button className="btn-ghost" onClick={onClose} style={{ padding: '4px 12px', fontSize: 11 }}>Cancel</button>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}

// ─── Results Table ──────────────────────────────────────────────
function StrategyResultsTable({ strategyId }) {
    const qc = useQueryClient()
    const { data: tableData, isLoading, isRefetching } = useQuery({
        queryKey: ['backtestTable', strategyId],
        queryFn: () => API.getBacktestTable(strategyId),
        enabled: !!strategyId && !String(strategyId).startsWith('local_'),
    })

    const [search, setSearch] = useState('')
    const [minWr, setMinWr] = useState(0)
    const [tfFilter, setTfFilter] = useState('ALL')
    const [sortCol, setSortCol] = useState('BEST WIN%')
    const [sortAsc, setSortAsc] = useState(false)
    const [page, setPage] = useState(1)
    const ROWS_PER_PAGE = 50

    const handleSort = (col) => {
        if (sortCol === col) setSortAsc(!sortAsc)
        else { setSortCol(col); setSortAsc(false) }
    }

    const exportCsv = () => {
        if (!tableData) return
        const header = "COIN,STRATEGY,5m,15m,1h,2h,4h,1d,BEST_TF,BEST_WIN,TRADES,RETURN,DRAWDOWN\n"
        const csv = tableData.map(r => {
            const bestRes = r.results[r.best_timeframe] || {}
            return `${r.coin},${r.strategy},${r.results['5m']?.win_rate || ''},${r.results['15m']?.win_rate || ''},${r.results['1h']?.win_rate || ''},${r.results['2h']?.win_rate || ''},${r.results['4h']?.win_rate || ''},${r.results['1d']?.win_rate || ''},${r.best_timeframe},${r.best_win_rate},${bestRes.trades || ''},${bestRes.return_pct || ''},${bestRes.drawdown || ''}`
        }).join("\n")
        const blob = new Blob([header + csv], { type: 'text/csv' })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `backtest_results_${strategyId}.csv`
        a.click()
    }

    const filtered = useMemo(() => {
        if (!tableData || !Array.isArray(tableData)) return []
        return tableData.filter(row => {
            const coinMatch = !search || row.coin.toLowerCase().includes(search.toLowerCase())
            const wrMatch = (row.best_win_rate || 0) >= minWr
            const tfMatch = tfFilter === 'ALL' || row.best_timeframe === tfFilter
            return coinMatch && wrMatch && tfMatch
        }).sort((a, b) => {
            let va, vb;
            if (sortCol === 'COIN') { va = a.coin; vb = b.coin; }
            else if (sortCol.includes('m') || sortCol.includes('h') || sortCol.includes('d')) {
                va = a.results[sortCol]?.win_rate || 0; vb = b.results[sortCol]?.win_rate || 0;
            }
            else if (sortCol === 'BEST TF') { va = a.best_timeframe || ''; vb = b.best_timeframe || ''; }
            else if (sortCol === 'BEST WIN%') { va = a.best_win_rate || 0; vb = b.best_win_rate || 0; }
            else if (sortCol === 'TRADES (BEST)') { va = a.results[a.best_timeframe]?.trades || 0; vb = b.results[b.best_timeframe]?.trades || 0; }
            else if (sortCol === 'RETURN%') { va = a.results[a.best_timeframe]?.return_pct || 0; vb = b.results[b.best_timeframe]?.return_pct || 0; }
            else if (sortCol === 'DRAWDOWN') { va = a.results[a.best_timeframe]?.drawdown || 0; vb = b.results[b.best_timeframe]?.drawdown || 0; }

            if (va < vb) return sortAsc ? -1 : 1
            if (va > vb) return sortAsc ? 1 : -1
            return 0
        })
    }, [tableData, search, minWr, tfFilter, sortCol, sortAsc])

    const totalPages = Math.ceil(filtered.length / ROWS_PER_PAGE)
    const pageData = filtered.slice((page - 1) * ROWS_PER_PAGE, page * ROWS_PER_PAGE)

    const thStyle = { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', padding: '12px 16px', textAlign: 'left', cursor: 'pointer', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)' }
    const tdStyle = { fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--text-primary)', padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.02)', whiteSpace: 'nowrap' }

    const renderCell = (wr, trades) => {
        if (wr === undefined || wr === null) return <span style={{ color: 'var(--text-dim)' }}>—</span>
        let bg = 'transparent', color = 'var(--text-primary)'
        if (wr >= 65) { bg = 'rgba(0,255,170,0.15)'; color = 'var(--green)'; }
        else if (wr >= 50) { bg = 'rgba(255,214,0,0.15)'; color = 'var(--yellow)'; }
        else { bg = 'rgba(255,51,102,0.15)'; color = 'var(--red)'; }
        return (
            <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 4, background: bg, color, fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 12 }}>
                {wr.toFixed(1)}% {trades !== undefined && trades !== null ? <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 2 }}>({trades})</span> : ''}
            </span>
        )
    }

    if (isLoading) return (
        <div className="card" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <LoadingSpinner text="Loading backtest matrix..." />
        </div>
    )

    if (!tableData || tableData.length === 0) return (
        <div className="card" style={{ flex: 1, textAlign: 'center', padding: '40px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 15 }}>
            <BarChart2 size={48} opacity={0.2} />
            <div>No backtest data found for this strategy.</div>
            <button className="btn-ghost" onClick={() => qc.invalidateQueries(['backtestTable', strategyId])}>Check Again</button>
        </div>
    )

    return (
        <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'rgba(0,0,0,0.2)' }}>
            {/* Toolbar */}
            <div style={{ display: 'flex', gap: 16, padding: '12px 16px', borderBottom: '1px solid var(--border)', flexWrap: 'wrap', alignItems: 'center', background: 'rgba(255,255,255,0.01)' }}>
                <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-secondary)', borderRadius: 8, padding: '0 12px', flex: '1 1 200px', border: '1px solid var(--border)' }}>
                    <Search size={14} color="var(--text-dim)" />
                    <input value={search} onChange={e => { setSearch(e.target.value); setPage(1) }} placeholder="Filter by coin..." style={{ border: 'none', background: 'transparent', color: 'white', padding: '8px 10px', fontSize: 13, outline: 'none', width: '100%' }} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'var(--bg-secondary)', padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border)' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)' }}>MIN WIN%</span>
                    <input type="range" min="0" max="80" step="5" value={minWr} onChange={e => { setMinWr(Number(e.target.value)); setPage(1) }} style={{ width: 80 }} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, width: 30, color: 'var(--cyan)' }}>{minWr}%</span>
                </div>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <select className="cyber-input" value={tfFilter} onChange={e => { setTfFilter(e.target.value); setPage(1) }} style={{ width: 80, padding: '6px 8px', height: 'auto' }}>
                        <option value="ALL">ALL TF</option>
                        {TF_OPTIONS.map(tf => <option key={tf} value={tf}>{tf}</option>)}
                    </select>
                </div>
                <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
                    <button className="btn-ghost" onClick={() => qc.invalidateQueries(['backtestTable', strategyId])} style={{ padding: '6px 12px', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <RefreshCw size={14} className={isRefetching ? "animate-spin" : ""} />
                    </button>
                    <button className="btn-ghost" onClick={exportCsv} style={{ padding: '6px 12px', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Download size={14} /> Export
                    </button>
                </div>
            </div>

            {/* Table wrapper */}
            <div style={{ flex: 1, overflow: 'auto' }} className="custom-scrollbar">
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead style={{ position: 'sticky', top: 0, zIndex: 10 }}>
                        <tr>
                            {['COIN', 'STRATEGY', '5m', '15m', '1h', '2h', '4h', '1d', 'BEST TF', 'BEST WIN%', 'TRADES (BEST)', 'RETURN%', 'DRAWDOWN'].map(col => (
                                <th key={col} style={thStyle} onClick={() => handleSort(col)}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                        {col}
                                        {sortCol === col && (sortAsc ? <ChevronUp size={12} /> : <ChevronDown size={12} />)}
                                    </div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {pageData.length === 0 ? (
                            <tr>
                                <td colSpan={13} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                                    No results match your filters.
                                </td>
                            </tr>
                        ) : pageData.map((row, i) => {
                            const isBest = row.best_win_rate >= 65;
                            const isWorst = row.best_win_rate < 40;
                            const borderLeft = isBest ? '3px solid var(--green)' : isWorst ? '3px solid var(--red)' : '3px solid transparent';
                            const bestRes = row.results[row.best_timeframe] || {};

                            return (
                                <tr key={`${row.coin}-${row.strategy_id}`} style={{ background: i % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent', borderLeft }}>
                                    <td style={{ ...tdStyle, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>{row.coin}</td>
                                    <td style={{ ...tdStyle, color: 'var(--text-secondary)', fontSize: 11 }}>{row.strategy}</td>
                                    <td style={tdStyle}>{renderCell(row.results['5m']?.win_rate, row.results['5m']?.trades)}</td>
                                    <td style={tdStyle}>{renderCell(row.results['15m']?.win_rate, row.results['15m']?.trades)}</td>
                                    <td style={tdStyle}>{renderCell(row.results['1h']?.win_rate, row.results['1h']?.trades)}</td>
                                    <td style={tdStyle}>{renderCell(row.results['2h']?.win_rate, row.results['2h']?.trades)}</td>
                                    <td style={tdStyle}>{renderCell(row.results['4h']?.win_rate, row.results['4h']?.trades)}</td>
                                    <td style={tdStyle}>{renderCell(row.results['1d']?.win_rate, row.results['1d']?.trades)}</td>
                                    <td style={{ ...tdStyle, color: 'var(--cyan)', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{row.best_timeframe || '—'}</td>
                                    <td style={tdStyle}>{renderCell(row.best_win_rate)}</td>
                                    <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{bestRes.trades || 0} ({row.best_timeframe})</td>
                                    <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', color: bestRes.return_pct > 0 ? 'var(--green)' : bestRes.return_pct < 0 ? 'var(--red)' : 'var(--text-dim)' }}>
                                        {bestRes.return_pct ? `${bestRes.return_pct > 0 ? '+' : ''}${bestRes.return_pct.toFixed(2)}%` : '—'}
                                    </td>
                                    <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', color: 'var(--red-dim)' }}>{bestRes.drawdown ? `-${bestRes.drawdown.toFixed(2)}%` : '—'}</td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div>

            {/* Pagination & Footer */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 20px', borderTop: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                    {filtered.length > 0 ? `Showing ${Math.min(filtered.length, (page - 1) * ROWS_PER_PAGE + 1)} - ${Math.min(filtered.length, page * ROWS_PER_PAGE)} of ${filtered.length} matches` : '0 matches'}
                </div>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <button className="btn-ghost" disabled={page === 1} onClick={() => setPage(page - 1)} style={{ padding: '4px 12px', fontSize: 12 }}>Prev</button>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)', fontWeight: 700 }}>{page} / {totalPages || 1}</span>
                    <button className="btn-ghost" disabled={page === totalPages || totalPages === 0} onClick={() => setPage(page + 1)} style={{ padding: '4px 12px', fontSize: 12 }}>Next</button>
                </div>
            </div>
        </div>
    )
}


// ─── Strategy Table Modal (New Window) ──────────────────────────
function StrategyTableModal({ strategy, onClose }) {
    if (!strategy) return null
    return (
        <div style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(9,14,26,0.98)', backdropFilter: 'blur(10px)',
            display: 'flex', flexDirection: 'column', padding: '20px'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 40, height: 40, borderRadius: 12, background: 'rgba(0,229,255,0.1)', border: '1px solid var(--cyan-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <BarChart2 size={24} color="var(--cyan)" />
                    </div>
                    <div>
                        <h2 style={{ margin: 0, fontSize: 22, color: 'var(--text-primary)' }}>{strategy.name} — Performance Matrix</h2>
                        <div style={{ fontSize: 12, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>DETAILED MULTI-TIMEFRAME BACKTEST RESULTS</div>
                    </div>
                </div>
                <button onClick={onClose} className="btn-ghost" style={{ padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
                    <X size={20} /> Close Results
                </button>
            </div>
            <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <StrategyResultsTable strategyId={strategy.id} />
            </div>
        </div>
    )
}


function SelectCoinsModal({ onClose, onConfirm, coins }) {
    const [selectedIds, setSelectedIds] = useState([])
    const [selectAll, setSelectAll] = useState(false)

    useEffect(() => {
        if (selectAll) {
            setSelectedIds(coins.map(c => c.id))
        } else {
            setSelectedIds([])
        }
    }, [selectAll, coins])

    const handleToggle = (id) => {
        setSelectedIds(prev => 
            prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
        )
    }

    const handleSubmit = (e) => {
        e.preventDefault()
        if (selectedIds.length === 0) {
            toast.error('Please select at least one coin')
            return
        }
        onConfirm(selectedIds)
    }

    return (
        <div style={{
            position: 'fixed', inset: 0, zIndex: 100,
            background: 'rgba(9,14,26,0.88)', backdropFilter: 'blur(6px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={e => e.target === e.currentTarget && onClose()}>
            <div className="card" style={{ width: 480, maxHeight: '80vh', overflowY: 'auto', padding: 28, position: 'relative' }}>
                <button onClick={onClose} style={{ position: 'absolute', top: 14, right: 14, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)' }}>
                    <X size={18} />
                </button>
                <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 18, marginBottom: 20, color: 'var(--text-primary)' }}>
                    Select Coins for Backtest
                </div>
                
                <div style={{ marginBottom: 16 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                        <input type="checkbox" checked={selectAll} onChange={e => setSelectAll(e.target.checked)} />
                        <span style={{ color: 'var(--text-primary)', fontSize: 14, fontWeight: 600 }}>Select All Coins</span>
                    </label>
                </div>

                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, maxHeight: '40vh', overflowY: 'auto', padding: '10px 5px' }} className="custom-scrollbar">
                        {coins.map(coin => (
                            <label key={coin.id} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, border: selectedIds.includes(coin.id) ? '1px solid var(--cyan)' : '1px solid var(--border)', transition: 'all 0.2s' }}>
                                <input type="checkbox" checked={selectedIds.includes(coin.id)} onChange={() => handleToggle(coin.id)} />
                                <span style={{ color: selectedIds.includes(coin.id) ? 'var(--cyan)' : 'var(--text-primary)', fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{coin.symbol}</span>
                            </label>
                        ))}
                    </div>

                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
                        <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
                        <button type="submit" className="btn-primary" style={{ minWidth: 120 }}>Run Backtest</button>
                    </div>
                </form>
            </div>
        </div>
    )
}

// ─── Main page ─────────────────────────────
export default function StrategyLibrary() {
        const [showModal, setShowModal] = useState(false)
    const [showDebugPanel, setShowDebugPanel] = useState(false)
    const [selectedStrategy, setSelectedStrategy] = useState(null)
    const [showTableModal, setShowTableModal] = useState(false)
    const [localStrategies, setLocalStrategies] = useState(loadLocalStrategies)
    const [jobProgress, setJobProgress] = useState(null)
    const [showCoinSelect, setShowCoinSelect] = useState(false)
    const [targetStrategyId, setTargetStrategyId] = useState(null)

    const qc = useQueryClient()

    const { data: serverStrategiesData, isLoading, isError } = useQuery({
        queryKey: ['strategies'],
        queryFn: API.getStrategies,
        retry: 1,
    })

    const { data: coinsData } = useQuery({
        queryKey: ['coins'],
        queryFn: API.getCoins,
    })

    const { mutateAsync: createStrategy } = useMutation({
        mutationFn: API.createStrategy,
        onSuccess: () => {
            qc.invalidateQueries(['strategies'])
            toast.success('Strategy created!')
        },
    })

    const isOffline = isError

    const handleSave = async (payload) => {
        if (isOffline) {
            const updated = saveLocalStrategy(payload)
            setLocalStrategies(updated)
            toast.success('Saved locally — will sync when backend is online', { icon: '💾' })
        } else {
            try {
                await createStrategy(payload)
            } catch (err) {
                // Our Flask backend returns {status, message}. FastAPI uses {detail}.
                const data = err?.response?.data || {}
                const errorMsg = data.message || data.detail || err.message || 'Backend error'
                const statusCode = err?.response?.status

                console.error('Strategy creation failed:', errorMsg)

                if (statusCode === 400) {
                    // Validation error (e.g. duplicate name) — don't save locally, just show the error
                    toast.error(errorMsg, { icon: '❌' })
                    throw err // Re-throw so modal stays open
                } else {
                    // Unexpected server error — save locally as fallback
                    const updated = saveLocalStrategy(payload)
                    setLocalStrategies(updated)
                    toast.error(`Saved locally — ${errorMsg}`, { icon: '⚠️' })
                }
            }
        }
    }

    const handleDelete = async (id) => {
        if (!window.confirm('Delete this strategy?')) return
        
        if (String(id).startsWith('local_')) {
            const updated = deleteLocalStrategy(id)
            setLocalStrategies(updated)
            if (selectedStrategy?.id === id) setSelectedStrategy(null)
            toast.success('Local strategy deleted')
        } else {
            try {
                await API.deleteStrategy(id)
                qc.invalidateQueries(['strategies'])
                if (selectedStrategy?.id === id) setSelectedStrategy(null)
                toast.success('Strategy deleted')
            } catch (err) {
                toast.error('Failed to delete strategy')
            }
        }
    }

    const handleRunBacktest = async (id) => {
        setTargetStrategyId(id)
        setShowCoinSelect(true)
    }

    const handleConfirmBacktest = async (coinIds) => {
        setShowCoinSelect(false)
        try {
            const res = await API.runStrategyBacktest(targetStrategyId, { coin_ids: coinIds })
            if (res?.job_id) {
                const strat = [...(serverStrategiesData?.strategies || []), ...localStrategies].find(s => s.id === targetStrategyId)
                setJobProgress({ id: res.job_id, name: strat?.name || 'Strategy', strategy: strat || { id: targetStrategyId } })
            } else {
                toast.success('Backtest started')
            }
        } catch (err) {
            toast.error(err?.response?.data?.detail || 'Failed to start backtest')
            console.error(err)
        }
    }

    const serverStrategies = serverStrategiesData?.strategies || []
    const allStrategies = [...serverStrategies, ...localStrategies]

    return (
        <div style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            height: 'calc(100vh - 120px)', 
            gap: 20, 
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
                <div>
                    <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 20, color: 'var(--text-primary)' }}>Strategy Library & Results</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                        {allStrategies.length} strategies {localStrategies.length > 0 && <span style={{ color: 'var(--yellow)', marginLeft: 6 }}>· {localStrategies.length} local</span>}
                    </div>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                    <button className="btn-ghost" onClick={() => qc.invalidateQueries(['strategies'])} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                        <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} /> Sync
                    </button>
                    <button className="btn-primary" onClick={() => setShowModal(true)} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Plus size={14} />Add Strategy
                    </button>
                </div>
            </div>

            {isLoading ? (
                <LoadingSpinner text="Loading..." />
            ) : (
                <div style={{ 
                    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 20, 
                    overflowY: 'auto', paddingRight: 10
                }} className="custom-scrollbar">
                    {allStrategies.map((s, idx) => (
                        <div key={s.id || idx}>
                            <StrategyCard
                                strategy={{
                                    ...s,
                                    name: String(s.id).startsWith('local_') ? `${s.name} ⚡` : s.name,
                                }}
                                onClick={() => setSelectedStrategy(s)}
                                onViewTable={() => {
                                    setSelectedStrategy(s)
                                    setShowTableModal(true)
                                }}
                                onRunBacktest={handleRunBacktest}
                                onDelete={handleDelete}
                            />
                        </div>
                    ))}
                    {allStrategies.length === 0 && (
                        <div style={{
                            width: '100%', textAlign: 'center', padding: '40px 20px',
                            display: 'flex', flexDirection: 'column', alignItems: 'center',
                            border: '1px dashed var(--border)', borderRadius: 12,
                            background: 'rgba(255,255,255,0.01)'
                        }}>
                            <div style={{ fontFamily: 'var(--font-sans)', fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
                                No strategies yet
                            </div>
                            <button className="btn-primary" onClick={() => setShowModal(true)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 24px', fontSize: 14 }}>
                                <Plus size={16} />Add Strategy
                            </button>
                        </div>
                    )}
                </div>
            )}

            {showTableModal && <StrategyTableModal strategy={selectedStrategy} onClose={() => setShowTableModal(false)} />}

            {showModal && <AddStrategyModal onClose={() => setShowModal(false)} onSave={handleSave} isOffline={isOffline} />}

            {showCoinSelect && (
                <SelectCoinsModal 
                    onClose={() => setShowCoinSelect(false)} 
                    onConfirm={handleConfirmBacktest} 
                    coins={coinsData || []} 
                />
            )}

            {jobProgress && (
                <BacktestProgressModal
                    strategyName={jobProgress.name}
                    jobId={jobProgress.id}
                    onClose={() => setJobProgress(null)}
                    onComplete={() => {
                        const strategyToSelect = jobProgress?.strategy
                        setJobProgress(null)
                        // Wait 800ms for DB writes to fully commit, then force fresh fetch
                        setTimeout(() => {
                            qc.invalidateQueries(['strategies'])
                            qc.invalidateQueries(['backtestSummary'])
                            qc.invalidateQueries(['backtestTable'])
                            qc.refetchQueries(['backtestTable'])
                            if (strategyToSelect) {
                                setSelectedStrategy(strategyToSelect)
                            }
                            toast.success('Backtest complete! Results are ready 🎉')
                        }, 800)
                    }}
                />
            )}
        </div>
    )
}
