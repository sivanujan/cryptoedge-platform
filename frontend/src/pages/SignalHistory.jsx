import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Filter, X, ExternalLink, ArrowUpRight, ArrowDownRight, Target, ShieldAlert, History, Trash2, Zap } from 'lucide-react'
import { API } from '../lib/api'
import LoadingSpinner from '../components/LoadingSpinner'

function SignalDetailsModal({ signal, onClose }) {
    if (!signal) return null

    const pnl = signal.pnl_percent || 0
    const isSuccess = signal.status === 'closed' || pnl > 0
    const color = isSuccess ? 'var(--green)' : 'var(--red)'

    const fmt = (n) => n ? `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 })}` : '—'

    // Risk Analysis
    const entry = signal.entry_price || 0
    const sl = signal.stop_loss || 0
    const riskPct = entry > 0 ? (Math.abs(entry - sl) / entry) * 100 : 0
    const recommendedLeverage = riskPct > 0 ? Math.floor(20 / riskPct) : 10 // Targeting max 20% margin loss
    const isHighRisk = riskPct > 3

    return (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }} onClick={onClose}>
            <div className="card" style={{ maxWidth: 500, width: '100%', padding: 24, position: 'relative', display: 'flex', flexDirection: 'column', gap: 20 }} onClick={e => e.stopPropagation()}>
                <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}><X size={20} /></button>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 44, height: 44, borderRadius: 12, background: 'rgba(0,229,255,0.1)', border: '1px solid var(--cyan-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Target size={24} color="var(--cyan)" />
                    </div>
                    <div>
                        <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>{signal.symbol}</div>
                        <div style={{ fontSize: 12, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>{signal.strategy} · {signal.timeframe}</div>
                    </div>
                    <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                        <div className="badge" style={{ background: signal.signal_type === 'BUY' ? 'rgba(0,230,118,0.15)' : 'rgba(255,23,68,0.15)', color: signal.signal_type === 'BUY' ? 'var(--green)' : 'var(--red)', fontSize: 14 }}>{signal.signal_type}</div>
                    </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                    <div className="card" style={{ padding: 16, background: 'rgba(255,255,255,0.03)' }}>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.05em', marginBottom: 4 }}>ENTRY PRICE</div>
                        <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{fmt(signal.entry_price)}</div>
                    </div>
                    <div className="card" style={{ padding: 16, background: 'rgba(255,255,255,0.03)' }}>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.05em', marginBottom: 4 }}>CURRENT PRICE</div>
                        <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>{fmt(signal.current_price || signal.entry_price)}</div>
                    </div>
                </div>

                <div className="card" style={{ padding: 16, border: isHighRisk ? '1px solid var(--red-dim)' : '1px solid var(--border)', background: isHighRisk ? 'rgba(255,23,68,0.05)' : 'rgba(255,255,255,0.02)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: isHighRisk ? 'var(--red)' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <ShieldAlert size={14} /> RISK ANALYSIS
                        </div>
                        <span style={{ fontSize: 12, fontWeight: 700, color: isHighRisk ? 'var(--red)' : 'var(--green)' }}>
                            {riskPct.toFixed(2)}% Dist. to SL
                        </span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <div style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 600 }}>
                            Recommended Max Leverage: <span style={{ color: 'var(--cyan)' }}>{recommendedLeverage}x</span>
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', lineHeight: 1.4 }}>
                            At {recommendedLeverage}x leverage, hitting the Stop Loss would result in a ~{(riskPct * recommendedLeverage).toFixed(0)}% loss of your trade margin.
                             {isHighRisk && <span style={{ color: 'var(--red)', display: 'block', marginTop: 4 }}>⚠️ Warning: High volatility detected. Keep leverage low.</span>}
                        </div>
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-dim)' }}>
                        <span>PROFIT / LOSS</span>
                        <span style={{ color, fontWeight: 700 }}>{pnl > 0 ? '+' : ''}{pnl.toFixed(2)}%</span>
                    </div>
                    <div style={{ height: 6, background: 'var(--bg-secondary)', borderRadius: 3, overflow: 'hidden', position: 'relative' }}>
                        <div style={{ position: 'absolute', top: 0, height: '100%', left: '50%', width: `${Math.min(Math.abs(pnl) * 5, 50)}%`, background: color, transformOrigin: pnl >=0 ? 'left' : 'right', transform: pnl >=0 ? 'none' : 'translateX(-100%)' }} />
                        <div style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', width: 1, background: 'var(--text-dim)', opacity: 0.5 }} />
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Target size={14} color="var(--green)" />
                        <span style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1 }}>Take Profit</span>
                        <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--green)' }}>{fmt(signal.take_profit)}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <ShieldAlert size={14} color="var(--red)" />
                        <span style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1 }}>Stop Loss</span>
                        <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>{fmt(signal.stop_loss)}</span>
                    </div>
                    {signal.volatility && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <History size={14} color="var(--purple)" />
                            <span style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1 }}>Volatility (ATR)</span>
                            <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', color: signal.volatility > 3 ? 'var(--red)' : 'var(--purple)' }}>{signal.volatility}%</span>
                        </div>
                    )}
                </div>

                <div style={{ marginTop: 'auto', paddingTop: 16, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-dim)', fontSize: 11 }}>
                        <History size={12} />
                        Status: <span style={{ color: 'var(--text-primary)', textTransform: 'uppercase', fontWeight: 700 }}>{signal.status}</span>
                    </div>
                    <a href={`https://www.tradingview.com/chart/?symbol=BINANCE:${signal.symbol.replace('/', '')}P`} target="_blank" rel="noreferrer" className="btn-ghost" style={{ fontSize: 11, padding: '4px 8px', gap: 6 }}>
                        View on TradingView <ExternalLink size={12} />
                    </a>
                </div>
            </div>
        </div>
    )
}

export default function SignalHistory() {
    const [filters, setFilters] = useState({ coin: '', strategy: '', signal_type: '', result: '' })
    const [page, setPage] = useState(0)
    const [selectedSignal, setSelectedSignal] = useState(null)
    const [showHighVolatility, setShowHighVolatility] = useState(false)
    const [sortVolatility, setSortVolatility] = useState(false)
    const limit = 50

    const { data, isLoading } = useQuery({
        queryKey: ['signalHistory', filters, page],
        queryFn: () => API.getSignalHistory({ ...filters, limit, offset: page * limit }),
        refetchInterval: 30000,
    })

    const queryClient = useQueryClient()
    const clearMutation = useMutation({
        mutationFn: () => API.clearSignalHistory(),
        onSuccess: () => {
            queryClient.invalidateQueries(['signalHistory'])
        }
    })

    const handleClearHistory = () => {
        if (window.confirm("Are you sure you want to PERMANENTLY delete all signal history? This cannot be undone.")) {
            clearMutation.mutate()
        }
    }

    const allSignals = data?.signals || []
    
    // Derived signals based on filters/sorting
    let signals = [...allSignals]
    
    if (showHighVolatility) {
        signals = signals.filter(s => s.volatility && Number(s.volatility) >= 3.0)
    }
    
    if (sortVolatility) {
        signals.sort((a, b) => (b.volatility || 0) - (a.volatility || 0))
    }

    const fmt = (n) => n ? `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 })}` : '—'
    const timeStr = (dt) => {
        if (!dt) return '—'
        return new Date(dt).toLocaleString('en-GB', { 
            timeZone: 'Asia/Colombo',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        }).replace(/\//g, '/') // Ensure forward slashes
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 14 }}>

            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexShrink: 0 }}>
                <div>
                    <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 20, color: 'var(--text-primary)' }}>Signal History</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>All generated signals & outcomes</div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
                    <div style={{ display: 'flex', gap: 12 }}>
                        {[
                            { label: 'TOTAL', value: data?.total_signals ?? '—', color: 'var(--cyan)' },
                            { label: 'WINS', value: data?.wins ?? '—', color: 'var(--green)' },
                            { label: 'LOSSES', value: data?.losses ?? '—', color: 'var(--red)' },
                            { label: 'WIN RATE', value: data?.win_rate != null ? `${data.win_rate}%` : '—', color: data?.win_rate >= 50 ? 'var(--green)' : 'var(--red)' },
                        ].map(({ label, value, color }) => (
                            <div key={label} className="card" style={{ padding: '8px 16px', textAlign: 'center' }}>
                                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 17, fontWeight: 700, color }}>{value}</div>
                                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)', letterSpacing: '0.08em', marginTop: 2 }}>{label}</div>
                            </div>
                        ))}
                    </div>
                    <button 
                        className="btn-ghost" 
                        onClick={handleClearHistory}
                        disabled={clearMutation.isPending || (data?.total_signals === 0)}
                        style={{ fontSize: 10, color: 'var(--red)', opacity: 0.7, padding: '4px 8px', gap: 6, display: 'flex', alignItems: 'center' }}
                    >
                        <Trash2 size={12} /> {clearMutation.isPending ? 'Clearing...' : 'Clear All History'}
                    </button>
                </div>
            </div>

            {/* Filters */}
            <div className="card" style={{ padding: '10px 14px', display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0, flexWrap: 'wrap' }}>
                <Filter size={14} color="var(--text-dim)" />
                <input className="cyber-input" placeholder="Coin..." value={filters.coin} onChange={e => setFilters(f => ({ ...f, coin: e.target.value }))} style={{ maxWidth: 130 }} />
                <input className="cyber-input" placeholder="Strategy..." value={filters.strategy} onChange={e => setFilters(f => ({ ...f, strategy: e.target.value }))} style={{ maxWidth: 150 }} />
                    {/* High Volatility Toggle */}
                    <button 
                        onClick={() => {
                            setShowHighVolatility(!showHighVolatility)
                            if (!showHighVolatility) setSortVolatility(true)
                        }}
                        style={{
                            padding: '8px 12px',
                            borderRadius: '6px',
                            fontSize: '11px',
                            fontWeight: 700,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                            transition: 'all 0.2s',
                            background: showHighVolatility ? 'rgba(255, 23, 68, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                            border: `1px solid ${showHighVolatility ? 'var(--red)' : 'var(--border)'}`,
                            color: showHighVolatility ? 'var(--red)' : 'var(--text-dim)'
                        }}
                    >
                        <Zap size={14} /> {showHighVolatility ? 'High Volatility ON' : 'Show High Volatility'}
                    </button>
                    
                    <button 
                        className="cyber-input"
                        onClick={() => setSortVolatility(!sortVolatility)}
                        style={{ 
                            fontSize: '11px', 
                            cursor: 'pointer',
                            background: sortVolatility ? 'rgba(0, 230, 118, 0.08)' : 'transparent',
                            borderColor: sortVolatility ? 'var(--green)' : 'var(--border)',
                            color: sortVolatility ? 'var(--green)' : 'var(--text-dim)',
                            width: 'auto',
                            padding: '0 12px'
                        }}
                    >
                        Sort: {sortVolatility ? 'Volatility' : 'Recent'}
                    </button>

                    <select className="cyber-input" value={filters.signal_type} onChange={e => setFilters(f => ({ ...f, signal_type: e.target.value }))} style={{ maxWidth: 110 }}>
                        <option value="">All Types</option>
                    <option value="BUY">BUY</option>
                    <option value="SELL">SELL</option>
                </select>
                <select className="cyber-input" value={filters.result} onChange={e => setFilters(f => ({ ...f, result: e.target.value }))} style={{ maxWidth: 110 }}>
                    <option value="">All Results</option>
                    <option value="win">Win</option>
                    <option value="loss">Loss</option>
                </select>
                <button className="btn-ghost" onClick={() => { setFilters({ coin: '', strategy: '', signal_type: '', result: '' }); setPage(0) }}>Clear</button>
            </div>

            {/* Table */}
            <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                {isLoading ? <LoadingSpinner text="Loading signals..." /> : (
                    <div style={{ flex: 1, overflowY: 'auto', overflowX: 'auto' }}>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Coin</th>
                                    <th>Strategy</th>
                                    <th>Type</th>
                                    <th>TF</th>
                                    <th>Entry</th>
                                    <th>Stop Loss</th>
                                    <th>Take Profit</th>
                                    <th>Confidence</th>
                                    <th>Volatility</th>
                                    <th>Status</th>
                                    <th>Time</th>
                                </tr>
                            </thead>
                            <tbody>
                                {signals.length === 0 ? (
                                    <tr><td colSpan={10} style={{ textAlign: 'center', padding: 40, color: 'var(--text-dim)' }}>No signals found</td></tr>
                                ) : signals.map((s, i) => (
                                    <tr key={s.id || i} onClick={() => setSelectedSignal(s)} style={{ cursor: 'pointer' }}>
                                        <td style={{ color: 'var(--cyan)', fontWeight: 700 }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                {s.symbol}
                                                <ExternalLink size={10} style={{ opacity: 0.5 }} />
                                            </div>
                                        </td>
                                        <td style={{ color: 'var(--text-secondary)' }}>{s.strategy}</td>
                                        <td><span className={s.signal_type === 'BUY' ? 'badge badge-buy' : 'badge badge-sell'}>{s.signal_type}</span></td>
                                        <td style={{ color: 'var(--text-dim)' }}>{s.timeframe}</td>
                                        <td>{fmt(s.entry_price)}</td>
                                        <td style={{ color: 'var(--red)' }}>{fmt(s.stop_loss)}</td>
                                        <td style={{ color: 'var(--green)' }}>{fmt(s.take_profit)}</td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                <span style={{ color: Number(s.confidence) >= 70 ? 'var(--green)' : 'var(--yellow)', fontWeight: 700 }}>
                                                    {s.confidence}%
                                                </span>
                                            </div>
                                        </td>
                                        <td>
                                            {s.volatility ? (
                                                <span style={{ color: Number(s.volatility) > 3 ? 'var(--red)' : 'var(--text-primary)', fontWeight: 700 }}>
                                                    {s.volatility}%
                                                </span>
                                            ) : '—'}
                                        </td>
                                        <td>
                                            <span className="badge badge-active" style={
                                                s.status === 'closed' || (s.pnl_percent > 0) ? { background: 'rgba(0,230,118,0.12)', color: 'var(--green)', borderColor: 'rgba(0,230,118,0.3)' } :
                                                    (s.status === 'stopped' || s.pnl_percent < 0) ? { background: 'rgba(255,23,68,0.12)', color: 'var(--red)', borderColor: 'rgba(255,23,68,0.3)' } : {}
                                            }>
                                                {s.pnl_percent != null ? (
                                                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                                        {s.pnl_percent > 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                                                        {s.pnl_percent > 0 ? '+' : ''}{s.pnl_percent.toFixed(2)}%
                                                    </span>
                                                ) : s.status}
                                            </span>
                                        </td>
                                        <td style={{ color: 'var(--text-dim)' }}>{timeStr(s.created_at)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {/* Pagination */}
                <div style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 10, borderTop: '1px solid var(--border)', flexShrink: 0 }}>
                    <button className="btn-ghost" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={{ padding: '4px 10px', fontSize: 11 }}>← Prev</button>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)' }}>Page {page + 1}</span>
                    <button className="btn-ghost" onClick={() => setPage(p => p + 1)} disabled={signals.length < limit} style={{ padding: '4px 10px', fontSize: 11 }}>Next →</button>
                </div>
            </div>
            {selectedSignal && <SignalDetailsModal signal={selectedSignal} onClose={() => setSelectedSignal(null)} />}
        </div>
    )
}
