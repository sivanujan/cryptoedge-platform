import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Filter } from 'lucide-react'
import { API } from '../lib/api'
import LoadingSpinner from '../components/LoadingSpinner'

export default function SignalHistory() {
    const [filters, setFilters] = useState({ coin: '', strategy: '', signal_type: '', result: '' })
    const [page, setPage] = useState(0)
    const limit = 50

    const { data, isLoading } = useQuery({
        queryKey: ['signalHistory', filters, page],
        queryFn: () => API.getSignalHistory({ ...filters, limit, offset: page * limit }),
        refetchInterval: 30000,
    })

    const signals = data?.signals || []

    const fmt = (n) => n ? `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 })}` : '—'
    const timeStr = (dt) => dt ? new Date(dt).toLocaleString() : '—'

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 14 }}>

            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexShrink: 0 }}>
                <div>
                    <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 20, color: 'var(--text-primary)' }}>Signal History</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>All generated signals & outcomes</div>
                </div>
                {/* Top stats */}
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
            </div>

            {/* Filters */}
            <div className="card" style={{ padding: '10px 14px', display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0, flexWrap: 'wrap' }}>
                <Filter size={14} color="var(--text-dim)" />
                <input className="cyber-input" placeholder="Coin..." value={filters.coin} onChange={e => setFilters(f => ({ ...f, coin: e.target.value }))} style={{ maxWidth: 130 }} />
                <input className="cyber-input" placeholder="Strategy..." value={filters.strategy} onChange={e => setFilters(f => ({ ...f, strategy: e.target.value }))} style={{ maxWidth: 150 }} />
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
                                    <th>Status</th>
                                    <th>Time</th>
                                </tr>
                            </thead>
                            <tbody>
                                {signals.length === 0 ? (
                                    <tr><td colSpan={10} style={{ textAlign: 'center', padding: 40, color: 'var(--text-dim)' }}>No signals found</td></tr>
                                ) : signals.map((s, i) => (
                                    <tr key={s.id || i}>
                                        <td style={{ color: 'var(--cyan)', fontWeight: 700 }}>{s.symbol}</td>
                                        <td style={{ color: 'var(--text-secondary)' }}>{s.strategy}</td>
                                        <td><span className={s.signal_type === 'BUY' ? 'badge badge-buy' : 'badge badge-sell'}>{s.signal_type}</span></td>
                                        <td style={{ color: 'var(--text-dim)' }}>{s.timeframe}</td>
                                        <td>{fmt(s.entry_price)}</td>
                                        <td style={{ color: 'var(--red)' }}>{fmt(s.stop_loss)}</td>
                                        <td style={{ color: 'var(--green)' }}>{fmt(s.take_profit)}</td>
                                        <td>
                                            <span style={{ color: Number(s.confidence) >= 70 ? 'var(--green)' : 'var(--yellow)', fontWeight: 700 }}>
                                                {s.confidence}%
                                            </span>
                                        </td>
                                        <td>
                                            <span className="badge badge-active" style={
                                                s.status === 'closed' ? { background: 'rgba(0,230,118,0.12)', color: 'var(--green)', borderColor: 'rgba(0,230,118,0.3)' } :
                                                    s.status === 'stopped' ? { background: 'rgba(255,23,68,0.12)', color: 'var(--red)', borderColor: 'rgba(255,23,68,0.3)' } : {}
                                            }>{s.status}</span>
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
        </div>
    )
}
