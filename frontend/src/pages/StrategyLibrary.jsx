import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, X, Trash2, LayoutGrid, Search, Filter, ChevronDown, ChevronUp, Download, Play, Activity } from 'lucide-react'
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

        const payload = { ...form, parameters }
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

    const pct = progress ? Math.min((progress.completed / Math.max(progress.total_tests, 1)) * 100, 100) : 0
    const eta = progress ? Math.ceil(((progress.total_tests - progress.completed) * 0.15) / 60) : 0

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
                                <span>Progress: {progress.completed}/{progress.total_tests} tests</span>
                                <span>{pct.toFixed(1)}%</span>
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
    const { data: tableData, isLoading } = useQuery({
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
        if (!tableData) return []
        return tableData.filter(row => {
            if (search && !row.coin.toLowerCase().includes(search.toLowerCase())) return false
            if (row.best_win_rate < minWr) return false
            if (tfFilter !== 'ALL' && row.best_timeframe !== tfFilter) return false
            return true
        }).sort((a, b) => {
            let va, vb;
            if (sortCol === 'COIN') { va = a.coin; vb = b.coin; }
            else if (sortCol.includes('m') || sortCol.includes('h') || sortCol.includes('d')) {
                va = a.results[sortCol]?.win_rate || 0; vb = b.results[sortCol]?.win_rate || 0;
            }
            else if (sortCol === 'BEST TF') { va = a.best_timeframe || ''; vb = b.best_timeframe || ''; }
            else if (sortCol === 'BEST WIN%') { va = a.best_win_rate; vb = b.best_win_rate; }
            else if (sortCol === 'TRADES') { va = a.results[a.best_timeframe]?.trades || 0; vb = b.results[b.best_timeframe]?.trades || 0; }
            else if (sortCol === 'RETURN%') { va = a.results[a.best_timeframe]?.return_pct || 0; vb = b.results[b.best_timeframe]?.return_pct || 0; }
            else if (sortCol === 'DRAWDOWN') { va = a.results[a.best_timeframe]?.drawdown || 0; vb = b.results[b.best_timeframe]?.drawdown || 0; }

            if (va < vb) return sortAsc ? -1 : 1
            if (va > vb) return sortAsc ? 1 : -1
            return 0
        })
    }, [tableData, search, minWr, tfFilter, sortCol, sortAsc])

    const totalPages = Math.ceil(filtered.length / ROWS_PER_PAGE)
    const pageData = filtered.slice((page - 1) * ROWS_PER_PAGE, page * ROWS_PER_PAGE)

    const thStyle = { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', padding: '12px 16px', textAlign: 'left', cursor: 'pointer', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }
    const tdStyle = { fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--text-primary)', padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.02)', whiteSpace: 'nowrap' }

    const renderCell = (wr) => {
        if (wr === undefined || wr === null) return <span style={{ color: 'var(--text-dim)' }}>—</span>
        let bg = 'transparent', color = 'var(--text-primary)'
        if (wr >= 65) { bg = 'rgba(0,255,170,0.15)'; color = 'var(--green)'; }
        else if (wr >= 50) { bg = 'rgba(255,214,0,0.15)'; color = 'var(--yellow)'; }
        else { bg = 'rgba(255,51,102,0.15)'; color = 'var(--red)'; }
        return <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 4, background: bg, color, fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 12 }}>{wr.toFixed(1)}%</span>
    }

    if (isLoading) return <LoadingSpinner text="Loading backtest results..." />
    if (!tableData || tableData.length === 0) return (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
            No results found. Please run a backtest first.
        </div>
    )

    return (
        <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* Toolbar */}
            <div style={{ display: 'flex', gap: 16, padding: '16px', borderBottom: '1px solid var(--border)', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-secondary)', borderRadius: 6, padding: '0 10px', flex: '1 1 200px' }}>
                    <Search size={14} color="var(--text-dim)" />
                    <input className="cyber-input" value={search} onChange={e => { setSearch(e.target.value); setPage(1) }} placeholder="Search coins..." style={{ border: 'none', background: 'transparent' }} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)' }}>MIN WIN%</span>
                    <input type="range" min="0" max="80" step="5" value={minWr} onChange={e => { setMinWr(Number(e.target.value)); setPage(1) }} style={{ width: 100 }} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, width: 30 }}>{minWr}%</span>
                </div>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)' }}>BEST TF</span>
                    <select className="cyber-input" value={tfFilter} onChange={e => { setTfFilter(e.target.value); setPage(1) }} style={{ width: 80, padding: '4px 8px' }}>
                        <option value="ALL">ALL</option>
                        {TF_OPTIONS.map(tf => <option key={tf} value={tf}>{tf}</option>)}
                    </select>
                </div>
                <button className="btn-ghost" onClick={exportCsv} style={{ marginLeft: 'auto', padding: '6px 12px', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Download size={14} /> Export CSV
                </button>
            </div>

            {/* Table wrapper */}
            <div style={{ flex: 1, overflow: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr>
                            {['COIN', 'STRATEGY', '5m', '15m', '1h', '2h', '4h', '1d', 'BEST TF', 'BEST WIN%', 'TRADES', 'RETURN%', 'DRAWDOWN'].map(col => (
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
                        {pageData.map((row, i) => {
                            const isBest = row.best_win_rate >= 65;
                            const isWorst = row.best_win_rate < 40;
                            const borderLeft = isBest ? '3px solid var(--green)' : isWorst ? '3px solid var(--red)' : '3px solid transparent';
                            const bestRes = row.results[row.best_timeframe] || {};

                            return (
                                <tr key={row.coin} style={{ background: i % 2 === 0 ? 'var(--bg-primary)' : 'var(--bg-secondary)', borderLeft }}>
                                    <td style={{ ...tdStyle, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{row.coin}</td>
                                    <td style={{ ...tdStyle, color: 'var(--text-secondary)' }}>{row.strategy}</td>
                                    <td style={tdStyle}>{renderCell(row.results['5m']?.win_rate)}</td>
                                    <td style={tdStyle}>{renderCell(row.results['15m']?.win_rate)}</td>
                                    <td style={tdStyle}>{renderCell(row.results['1h']?.win_rate)}</td>
                                    <td style={tdStyle}>{renderCell(row.results['2h']?.win_rate)}</td>
                                    <td style={tdStyle}>{renderCell(row.results['4h']?.win_rate)}</td>
                                    <td style={tdStyle}>{renderCell(row.results['1d']?.win_rate)}</td>
                                    <td style={{ ...tdStyle, color: 'var(--cyan)', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{row.best_timeframe || '—'}</td>
                                    <td style={tdStyle}>{renderCell(row.best_win_rate)}</td>
                                    <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{bestRes.trades || 0}</td>
                                    <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', color: bestRes.return_pct > 0 ? 'var(--green)' : 'var(--text-dim)' }}>
                                        {bestRes.return_pct ? `${bestRes.return_pct > 0 ? '+' : ''}${bestRes.return_pct.toFixed(2)}%` : '—'}
                                    </td>
                                    <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)' }}>{bestRes.drawdown ? `-${bestRes.drawdown.toFixed(2)}%` : '—'}</td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div>

            {/* Pagination & Footer */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px', borderTop: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                    Showing {Math.min(filtered.length, (page - 1) * ROWS_PER_PAGE + 1)} - {Math.min(filtered.length, page * ROWS_PER_PAGE)} of {filtered.length} results
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <button className="btn-ghost" disabled={page === 1} onClick={() => setPage(page - 1)} style={{ padding: '4px 10px', fontSize: 12 }}>Prev</button>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-primary)' }}>{page} / {totalPages || 1}</span>
                    <button className="btn-ghost" disabled={page === totalPages || totalPages === 0} onClick={() => setPage(page + 1)} style={{ padding: '4px 10px', fontSize: 12 }}>Next</button>
                </div>
            </div>
        </div>
    )
}


// ─── Main page ─────────────────────────────
export default function StrategyLibrary() {
    const [showModal, setShowModal] = useState(false)
    const [selectedStrategy, setSelectedStrategy] = useState(null)
    const [localStrategies, setLocalStrategies] = useState(loadLocalStrategies)
    const [jobProgress, setJobProgress] = useState(null)

    const qc = useQueryClient()

    const { data: serverStrategiesData, isLoading, isError } = useQuery({
        queryKey: ['strategies'],
        queryFn: API.getStrategies,
        retry: 1,
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
            } catch {
                const updated = saveLocalStrategy(payload)
                setLocalStrategies(updated)
                toast('Saved locally (backend error)', { icon: '⚠️' })
            }
        }
    }

    const handleRunBacktest = async (id) => {
        try {
            const res = await API.runStrategyBacktest(id)
            if (res?.job_id) {
                const strat = [...(serverStrategiesData?.strategies || []), ...localStrategies].find(s => s.id === id)
                setJobProgress({ id: res.job_id, name: strat?.name || 'Strategy', strategy: strat || { id } })
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
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
                <div>
                    <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 20, color: 'var(--text-primary)' }}>Strategy Library & Results</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                        {allStrategies.length} strategies {localStrategies.length > 0 && <span style={{ color: 'var(--yellow)', marginLeft: 6 }}>· {localStrategies.length} local</span>}
                    </div>
                </div>
                <button className="btn-primary" onClick={() => setShowModal(true)} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Plus size={14} />Add Strategy
                </button>
            </div>

            {isLoading ? (
                <LoadingSpinner text="Loading strategies..." />
            ) : (
                <div style={{
                    display: 'flex', gap: 14, overflowX: 'auto', paddingBottom: 8, flexShrink: 0,
                    scrollSnapType: 'x mandatory', msOverflowStyle: 'none', scrollbarWidth: 'none'
                }}>
                    {allStrategies.map((s, idx) => (
                        <div key={s.id || idx} style={{ flex: '0 0 auto', width: 320, scrollSnapAlign: 'start' }}>
                            <StrategyCard
                                strategy={{
                                    ...s,
                                    name: String(s.id).startsWith('local_') ? `${s.name} ⚡` : s.name,
                                }}
                                onClick={() => setSelectedStrategy(s)}
                                onRunBacktest={handleRunBacktest}
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

            {/* Comprehensive Data Table Area */}
            {selectedStrategy && !String(selectedStrategy.id).startsWith('local_') ? (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                    <div style={{ marginBottom: 10, fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 16, color: 'var(--cyan)', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Activity size={16} />
                        Detailed Multi-Timeframe Results for {selectedStrategy.name}
                        <button className="btn-ghost" onClick={() => setSelectedStrategy(null)} style={{ marginLeft: 'auto', padding: '4px 8px', fontSize: 11 }}>Close Table</button>
                    </div>
                    <StrategyResultsTable strategyId={selectedStrategy.id} />
                </div>
            ) : selectedStrategy ? (
                <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-dim)', flex: 1 }}>
                    ⚡ Local strategy — sync with backend to run backtests and view results matrix.
                </div>
            ) : (
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 12, color: 'var(--text-dim)', border: '1px dashed var(--border)', borderRadius: 12 }}>
                    <LayoutGrid size={32} opacity={0.5} />
                    <div style={{ fontFamily: 'var(--font-sans)', fontSize: 14 }}>Select "View Table" on any strategy above to expand full multi-timeframe backtest results.</div>
                </div>
            )}

            {showModal && <AddStrategyModal onClose={() => setShowModal(false)} onSave={handleSave} isOffline={isOffline} />}

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
