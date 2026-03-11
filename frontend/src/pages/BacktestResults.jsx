import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Filter, RefreshCw, Play, BarChart2, AlertCircle } from 'lucide-react'
import { API } from '../lib/api'
import CoinTable from '../components/CoinTable'
import toast from 'react-hot-toast'

const TIMEFRAMES = ['1h', '4h', '1d']

function EmptyState({ onRunAll, running }) {
    return (
        <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', gap: 16, padding: 60,
        }}>
            <div style={{
                width: 56, height: 56, borderRadius: 16,
                background: 'rgba(0,229,255,0.08)', border: '1px solid rgba(0,229,255,0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
                <BarChart2 size={24} color="var(--cyan)" strokeWidth={1.5} />
            </div>
            <div style={{ textAlign: 'center' }}>
                <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 16, color: 'var(--text-primary)', marginBottom: 6 }}>
                    No backtest results yet
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                    Run backtests first to see results here
                </div>
            </div>
            <button
                className="btn-primary"
                onClick={onRunAll}
                disabled={running}
                style={{ display: 'flex', alignItems: 'center', gap: 6, opacity: running ? 0.6 : 1 }}
            >
                <Play size={13} />
                {running ? 'Running backtests...' : 'Run All Backtests'}
            </button>
        </div>
    )
}

function ErrorState() {
    return (
        <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', gap: 12, padding: 60,
        }}>
            <AlertCircle size={28} color="var(--red)" strokeWidth={1.5} />
            <div style={{ textAlign: 'center' }}>
                <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 15, color: 'var(--red)', marginBottom: 4 }}>
                    Backend offline
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)' }}>
                    Start your Python server to load backtest results
                </div>
                <div style={{
                    marginTop: 10, display: 'inline-flex', alignItems: 'center', gap: 6,
                    background: 'rgba(255,23,68,0.08)', border: '1px solid rgba(255,23,68,0.2)',
                    borderRadius: 6, padding: '4px 12px',
                }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--red)' }} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--red)' }}>OFFLINE</span>
                </div>
            </div>
        </div>
    )
}

export default function BacktestResults() {
    const [filters, setFilters] = useState({ strategy: '', timeframe: '', min_win_rate: '' })
    const [running, setRunning] = useState(false)
    const [progress, setProgress] = useState(null)

    const { data, isLoading, isError, refetch } = useQuery({
        queryKey: ['backtestResults', filters],
        queryFn: () => API.getBacktestResults({
            strategy: filters.strategy || undefined,
            timeframe: filters.timeframe || undefined,
            min_win_rate: filters.min_win_rate ? Number(filters.min_win_rate) : undefined,
            limit: 500,
        }),
        retry: 1,
        // 5 second timeout handled by axios config
    })

    const results = data?.results || []

    const startRunAll = async () => {
        try {
            setRunning(true)
            const res = await API.runAllBacktests()
            toast.success('Full backtest started!')

            const pollId = setInterval(async () => {
                try {
                    const prog = await API.getBacktestProgress(res.job_id)
                    setProgress(prog)
                    if (prog.status === 'completed') {
                        clearInterval(pollId)
                        setRunning(false)
                        setProgress(null)
                        refetch()
                        toast.success('Backtest complete!')
                    } else if (prog.status === 'failed') {
                        clearInterval(pollId)
                        setRunning(false)
                        toast.error(`Backtest failed: ${prog.error}`)
                    }
                } catch { clearInterval(pollId); setRunning(false) }
            }, 2000)
        } catch {
            setRunning(false)
            toast.error('Failed to start backtest — is the backend running?')
        }
    }

    const columns = [
        { key: 'symbol', label: 'Coin', render: v => <span style={{ color: 'var(--cyan)', fontWeight: 700 }}>{v}</span> },
        { key: 'strategy', label: 'Strategy' },
        {
            key: 'timeframe', label: 'TF',
            render: v => <span style={{ background: 'var(--bg-secondary)', color: 'var(--text-dim)', padding: '1px 5px', borderRadius: 3, fontFamily: 'var(--font-mono)', fontSize: 10 }}>{v}</span>
        },
        {
            key: 'win_rate', label: 'Win Rate', render: v => {
                const n = Number(v) || 0
                const color = n >= 65 ? 'var(--green)' : n >= 50 ? 'var(--yellow)' : 'var(--red)'
                return <span style={{ color, background: n >= 65 ? 'rgba(0,230,118,0.12)' : n >= 50 ? 'rgba(255,214,0,0.12)' : 'rgba(255,23,68,0.12)', padding: '2px 8px', borderRadius: 4, fontWeight: 700 }}>{n.toFixed(1)}%</span>
            }
        },
        { key: 'total_trades', label: 'Trades', render: v => <span style={{ color: 'var(--text-secondary)' }}>{v ?? '—'}</span> },
        {
            key: 'total_return', label: 'Return', render: v => {
                const n = Number(v) || 0
                return <span style={{ color: n >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>{n >= 0 ? '+' : ''}{n.toFixed(2)}%</span>
            }
        },
        { key: 'max_drawdown', label: 'Drawdown', render: v => <span style={{ color: 'var(--red)' }}>{(Number(v) || 0).toFixed(2)}%</span> },
        { key: 'sharpe_ratio', label: 'Sharpe', render: v => <span style={{ color: 'var(--text-secondary)' }}>{(Number(v) || 0).toFixed(3)}</span> },
    ]

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 14 }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
                <div>
                    <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 20, color: 'var(--text-primary)' }}>Backtest Results</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>{data?.total || 0} total results</div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn-ghost" onClick={() => refetch()} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <RefreshCw size={13} />Refresh
                    </button>
                    <button className="btn-primary" onClick={startRunAll} disabled={running}
                        style={{ display: 'flex', alignItems: 'center', gap: 6, opacity: running ? 0.6 : 1 }}>
                        <Play size={13} />
                        {running ? `Running... ${progress?.progress || 0}%` : 'Run All Backtests'}
                    </button>
                </div>
            </div>

            {/* Filter bar */}
            <div className="card" style={{ padding: '10px 14px', display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0 }}>
                <Filter size={14} color="var(--text-dim)" />
                <input className="cyber-input" placeholder="Strategy..." value={filters.strategy}
                    onChange={e => setFilters(f => ({ ...f, strategy: e.target.value }))} style={{ maxWidth: 160 }} />
                <select className="cyber-input" value={filters.timeframe}
                    onChange={e => setFilters(f => ({ ...f, timeframe: e.target.value }))} style={{ maxWidth: 100 }}>
                    <option value="">All TFs</option>
                    {TIMEFRAMES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <input className="cyber-input" placeholder="Min win rate %" type="number" value={filters.min_win_rate}
                    onChange={e => setFilters(f => ({ ...f, min_win_rate: e.target.value }))} style={{ maxWidth: 140 }} />
                <button className="btn-ghost" onClick={() => setFilters({ strategy: '', timeframe: '', min_win_rate: '' })}>Clear</button>
            </div>

            {/* Content area */}
            <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                {isLoading ? (
                    // Loading skeleton — max visible for 5s due to axios timeout
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10, padding: 20 }}>
                        {Array.from({ length: 6 }).map((_, i) => (
                            <div key={i} style={{
                                height: 36, borderRadius: 6,
                                background: 'linear-gradient(90deg, var(--bg-secondary) 25%, var(--bg-hover) 50%, var(--bg-secondary) 75%)',
                                backgroundSize: '200% 100%',
                                animation: 'shimmer 1.5s infinite',
                                opacity: 1 - i * 0.1,
                            }} />
                        ))}
                    </div>
                ) : isError ? (
                    <ErrorState />
                ) : results.length === 0 ? (
                    <EmptyState onRunAll={startRunAll} running={running} />
                ) : (
                    <div style={{ flex: 1, padding: '0 14px 14px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                        <CoinTable data={results} columns={columns} />
                    </div>
                )}
            </div>
            <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
        </div>
    )
}
