import { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Filter, X, ExternalLink, ArrowUpRight, ArrowDownRight, Target, ShieldAlert, History, Trash2, Zap, Cpu } from 'lucide-react'
import { API } from '../lib/api'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'

function SignalDetailsModal({ signal, onClose }) {
    if (!signal) return null

    // Auto-refresh timer for live signals
    const [livePrice, setLivePrice] = useState(signal.current_price)
    const [livePnl, setLivePnl] = useState(signal.pnl_percent)
    const [isRefreshing, setIsRefreshing] = useState(false)
    
    // Entry Panel State
    const [showEntryPanel, setShowEntryPanel] = useState(false)
    const [leverage, setLeverage] = useState(10)
    const [positionSize, setPositionSize] = useState('')
    const [customEntry, setCustomEntry] = useState(signal.entry_price || '')
    const [selectedSLMode, setSelectedSLMode] = useState('structure') // 'structure' or 'safe'


    useEffect(() => {
        if (signal.status !== 'active') return

        const interval = setInterval(async () => {
            setIsRefreshing(true)
            try {
                const res = await API.getSignal(signal.id)
                if (res.signal) {
                    setLivePrice(res.signal.current_price)
                    setLivePnl(res.signal.pnl_percent)
                }
            } catch (e) {
                console.error("Auto-refresh failed", e)
            } finally {
                setTimeout(() => setIsRefreshing(false), 1000)
            }
        }, 10000)

        return () => clearInterval(interval)
    }, [signal.id, signal.status, signal.symbol])

    const currentPrice = livePrice ?? signal.current_price
    const currentPnl = livePnl ?? signal.pnl_percent
    const pnl = currentPnl || 0
    const isSuccess = signal.status === 'closed' || pnl > 0
    const color = isSuccess ? 'var(--green)' : 'var(--red)'

    const fmt = (n) => n ? `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 })}` : '—'

    // Risk Analysis
    const entry = signal.entry_price || 0
    const sl = signal.stop_loss || 0
    const riskPct = entry > 0 ? (Math.abs(entry - sl) / entry) * 100 : 0
    const recommendedLeverage = riskPct > 0 ? Math.floor(20 / riskPct) : 10 // Targeting max 20% margin loss
    const isHighRisk = riskPct > 3

    // --- Liquidation Logic ---
    const lev = Number(leverage) > 0 ? Number(leverage) : 1
    const entryPriceNum = Number(customEntry) || signal.entry_price || 0
    const structureSL = signal.structure_sl || signal.stop_loss || 0
    const structureTP = signal.structure_tp || signal.take_profit || 0
    
    let liquidationPrice = 0
    let isStructureSLUnsafe = false
    let safeSL = 0
    
    if (entryPriceNum > 0) {
        if (signal.signal_type === 'BUY') {
            liquidationPrice = entryPriceNum * (1 - (1 / lev) + 0.005)
            isStructureSLUnsafe = structureSL <= liquidationPrice
            safeSL = liquidationPrice * 1.10
        } else {
            liquidationPrice = entryPriceNum * (1 + (1 / lev) - 0.005)
            isStructureSLUnsafe = structureSL >= liquidationPrice
            safeSL = liquidationPrice * 0.90
        }
    }
    
    // Auto-switch to safe if structure becomes unsafe when leverage changes
    useEffect(() => {
        if (isStructureSLUnsafe) setSelectedSLMode('safe')
        else setSelectedSLMode('structure')
    }, [isStructureSLUnsafe, leverage])

    const handleConfirmTrade = () => {
        const finalSL = selectedSLMode === 'safe' ? safeSL : structureSL
        toast.success(`Trade Executed!\nEntry: ${entryPriceNum}\nSL: ${finalSL}\nTP: ${structureTP}\nLeverage: ${lev}x\nMargin: $${positionSize}`)
        setShowEntryPanel(false)
    }


    return (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }} onClick={onClose}>
            <div className="card" style={{ maxWidth: 500, width: '100%', maxHeight: '90vh', overflowY: 'auto', padding: 24, position: 'relative', display: 'flex', flexDirection: 'column', gap: 20 }} onClick={e => e.stopPropagation()}>
                <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}><X size={20} /></button>

                
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 44, height: 44, borderRadius: 12, background: 'rgba(0,229,255,0.1)', border: '1px solid var(--cyan-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Target size={24} color="var(--cyan)" />
                    </div>
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>{signal.symbol}</div>
                            {isRefreshing && <div className="live-dot" style={{ width: 6, height: 6 }} />}
                        </div>
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
                    <div className="card" style={{ padding: 16, background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                            <div style={{ fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.05em' }}>CURRENT PRICE</div>
                            {signal.status === 'active' && currentPrice && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                    <div className="live-dot" style={{ width: 6, height: 6 }} />
                                    <span style={{ fontSize: 9, color: 'var(--green)', fontWeight: 700 }}>LIVE</span>
                                </div>
                            )}
                        </div>
                        <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: (currentPrice !== null && currentPrice !== undefined) ? 'var(--cyan)' : 'var(--text-dim)' }}>
                            {(currentPrice !== null && currentPrice !== undefined) ? fmt(currentPrice) : fmt(signal.entry_price)}
                            {(currentPrice === null || currentPrice === undefined) && <span style={{ fontSize: 11, color: 'var(--text-dim)', marginLeft: 4 }}>(entry)</span>}
                        </div>
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

                {signal.ai_analysis && (
                    <div className="card" style={{ padding: 16, background: 'rgba(0,229,255,0.05)', border: '1px solid var(--cyan-dim)', borderRadius: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                            <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--cyan)', display: 'flex', alignItems: 'center', gap: 6, letterSpacing: '0.05em' }}>
                                <Cpu size={14} /> AI AGENT ANALYSIS
                            </div>
                            <div style={{ 
                                fontSize: 12, 
                                fontWeight: 900, 
                                padding: '2px 8px',
                                borderRadius: 6,
                                background: signal.ai_score >= 70 ? 'rgba(0,230,118,0.1)' : signal.ai_score >= 50 ? 'rgba(255,235,59,0.1)' : 'rgba(255,23,68,0.1)',
                                color: signal.ai_score >= 70 ? 'var(--green)' : signal.ai_score >= 50 ? 'var(--yellow)' : 'var(--red)' 
                            }}>
                                SCORE: {signal.ai_score}/100
                            </div>
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6, fontStyle: 'italic', borderLeft: '2px solid var(--cyan-dim)', paddingLeft: 12 }}>
                            "{signal.ai_analysis}"
                        </div>
                    </div>
                )}

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

                {/* --- ENTRY PANEL --- */}
                {!showEntryPanel ? (
                    <button 
                        onClick={() => setShowEntryPanel(true)} 
                        className="cyber-button" 
                        style={{ marginTop: 8, background: 'var(--cyan)', color: '#000', fontWeight: 800, padding: '12px', border: 'none', borderRadius: 8, cursor: 'pointer' }}
                    >
                        ENTER TRADE
                    </button>
                ) : (
                    <div className="card" style={{ padding: 16, border: '1px solid var(--cyan-dim)', background: 'rgba(0, 229, 255, 0.03)', marginTop: 8 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                            <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--cyan)' }}>TRADE ENTRY PANEL</div>
                            <button onClick={() => setShowEntryPanel(false)} style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}><X size={16} /></button>
                        </div>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            <div style={{ display: 'flex', gap: 12 }}>
                                <div style={{ flex: 1 }}>
                                    <label style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 4, display: 'block' }}>LEVERAGE (x)</label>
                                    <input type="number" className="cyber-input" value={leverage} onChange={e => setLeverage(e.target.value)} style={{ width: '100%' }} />
                                </div>
                                <div style={{ flex: 1 }}>
                                    <label style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 4, display: 'block' }}>SIZE (USDT)</label>
                                    <input type="number" className="cyber-input" value={positionSize} onChange={e => setPositionSize(e.target.value)} placeholder="e.g. 100" style={{ width: '100%' }} />
                                </div>
                            </div>
                            
                            <div>
                                <label style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 4, display: 'block' }}>ENTRY PRICE</label>
                                <input type="number" className="cyber-input" value={customEntry} onChange={e => setCustomEntry(e.target.value)} style={{ width: '100%' }} />
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 8 }}>
                                <div>
                                    <label style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 4, display: 'block' }}>STRUCTURE TP</label>
                                    <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 12px', fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--green)' }}>{fmt(structureTP)}</div>
                                </div>
                                <div>
                                    <label style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 4, display: 'block' }}>LIQ. PRICE</label>
                                    <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 12px', fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>{fmt(liquidationPrice)}</div>
                                </div>
                            </div>

                            <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
                                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 12 }}>SELECT STOP LOSS</div>
                                
                                <label style={{ display: 'flex', gap: 12, alignItems: 'center', cursor: 'pointer', marginBottom: 12, opacity: isStructureSLUnsafe ? 0.5 : 1 }}>
                                    <input type="radio" name="slMode" value="structure" checked={selectedSLMode === 'structure'} onChange={() => !isStructureSLUnsafe && setSelectedSLMode('structure')} disabled={isStructureSLUnsafe} style={{ transform: 'scale(1.2)' }} />
                                    <div>
                                        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Structure SL <span style={{ color: 'var(--red)', fontFamily: 'var(--font-mono)' }}>{fmt(structureSL)}</span></div>
                                        <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>Based on unmitigated swing {signal.signal_type === 'BUY' ? 'low' : 'high'}.</div>
                                        {isStructureSLUnsafe && (
                                            <div style={{ fontSize: 11, color: 'var(--red)', fontWeight: 700, marginTop: 6, background: 'rgba(255,23,68,0.1)', padding: '6px 10px', borderRadius: 6 }}>
                                                ⚠️ Unsafe: Will liquidate before hitting Structure SL
                                            </div>
                                        )}
                                    </div>
                                </label>

                                {isStructureSLUnsafe && (
                                    <label style={{ display: 'flex', gap: 12, alignItems: 'center', cursor: 'pointer', background: 'rgba(0,230,118,0.05)', padding: 12, borderRadius: 8, border: '1px solid var(--green-dim)' }}>
                                        <input type="radio" name="slMode" value="safe" checked={selectedSLMode === 'safe'} onChange={() => setSelectedSLMode('safe')} style={{ transform: 'scale(1.2)' }} />
                                        <div>
                                            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Safe SL <span style={{ color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>{fmt(safeSL)}</span></div>
                                            <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>Leverage-adjusted to prevent liquidation (10% margin).</div>
                                        </div>
                                    </label>
                                )}
                            </div>
                            
                            <button 
                                onClick={handleConfirmTrade}
                                disabled={!positionSize || Number(positionSize) <= 0}
                                className="cyber-button" 
                                style={{ marginTop: 12, background: 'var(--green)', color: '#000', fontWeight: 800, padding: '12px', border: 'none', borderRadius: 8, cursor: (!positionSize || Number(positionSize) <= 0) ? 'not-allowed' : 'pointer', opacity: (!positionSize || Number(positionSize) <= 0) ? 0.5 : 1 }}
                            >
                                CONFIRM TRADE
                            </button>
                        </div>
                    </div>
                )}


                <div style={{ marginTop: 'auto', paddingTop: 16, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-dim)', fontSize: 11 }}>
                        <History size={12} />
                        Status: <span style={{ color: 'var(--text-primary)', textTransform: 'uppercase', fontWeight: 700 }}>{signal.status}</span>
                    </div>
                    <a 
                        href={`https://www.tradingview.com/chart/?symbol=BINANCE:${signal.symbol.split(':')[0].replace('/', '')}.P`} 
                        target="_blank" 
                        rel="noreferrer" 
                        className="btn-ghost" 
                        style={{ fontSize: 11, padding: '4px 8px', gap: 6 }}
                    >
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
    const [generationEnabled, setGenerationEnabled] = useState(true)

    useEffect(() => {
        API.getGenerationStatus().then(res => {
            if (res.status === 'success') {
                setGenerationEnabled(res.enabled)
            }
        }).catch(err => console.error("Failed to fetch generation status", err))
    }, [])

    const handleToggleGeneration = async () => {
        const newValue = !generationEnabled
        try {
            const res = await API.toggleGeneration(newValue)
            if (res.status === 'success') {
                setGenerationEnabled(newValue)
                toast.success(`Signal generation ${newValue ? 'enabled' : 'disabled'}!`)
            }
        } catch (e) {
            toast.error("Failed to toggle generation status.")
        }
    }
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
                            { label: 'TOTAL P&L', value: data?.total_pnl != null ? `${data.total_pnl > 0 ? '+' : ''}${data.total_pnl}%` : '—', color: data?.total_pnl >= 0 ? 'var(--green)' : 'var(--red)' },
                        ].map(({ label, value, color }) => (
                            <div key={label} className="card" style={{ padding: '8px 16px', textAlign: 'center', minWidth: 80 }}>
                                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 17, fontWeight: 700, color }}>{value}</div>
                                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)', letterSpacing: '0.08em', marginTop: 2 }}>{label}</div>
                            </div>
                        ))}
                    </div>
                    <div style={{ display: 'flex', gap: 12 }}>
                        <button 
                            className="btn-ghost" 
                            onClick={handleToggleGeneration}
                            style={{ fontSize: 10, color: generationEnabled ? 'var(--green)' : 'var(--red)', opacity: 0.7, padding: '4px 8px', gap: 6, display: 'flex', alignItems: 'center' }}
                        >
                            <Zap size={12} /> {generationEnabled ? 'Generation: ON' : 'Generation: OFF'}
                        </button>
                        <button 
                            className="btn-ghost" 
                            onClick={async () => {
                                try {
                                    await API.triggerScanNow()
                                    toast.success("Manual scan triggered in background!")
                                } catch (e) {
                                    toast.error("Failed to trigger scan.")
                                }
                            }}
                            style={{ fontSize: 10, color: 'var(--cyan)', opacity: 0.7, padding: '4px 8px', gap: 6, display: 'flex', alignItems: 'center' }}
                        >
                            <Cpu size={12} /> Scan Now
                        </button>
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
            </div>

            {/* Strategy Analytics */}
            {data?.strategy_stats?.length > 0 && (
                <div style={{ flexShrink: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, paddingLeft: 4 }}>
                        <Zap size={14} color="var(--purple)" />
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>STRATEGY PERFORMANCE</span>
                    </div>
                    <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 6, scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
                        {data.strategy_stats.map(strat => {
                            const noData = strat.win_rate === 0 && strat.total_pnl === 0 && !strat.has_backtest
                            const borderColor = noData ? 'var(--border)' : strat.win_rate >= 55 ? 'var(--green)' : strat.win_rate >= 45 ? 'var(--yellow)' : 'var(--red)'
                            return (
                                <div key={strat.name} className="card" style={{ padding: '12px 16px', minWidth: 195, display: 'flex', flexDirection: 'column', gap: 6, borderLeft: `3px solid ${borderColor}`, background: 'rgba(255,255,255,0.01)' }}>
                                    <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 160 }} title={strat.name}>{strat.name}</div>
                                    {noData ? (
                                        <div style={{ fontSize: 10, color: 'var(--text-dim)', fontStyle: 'italic', paddingTop: 4 }}>
                                            ⏳ No backtest data yet.<br />Run Full Backtest to populate stats.
                                        </div>
                                    ) : (
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                            <div>
                                                <div style={{ fontSize: 9, color: 'var(--text-dim)', marginBottom: 2 }}>WIN RATE</div>
                                                <div style={{ fontSize: 13, fontWeight: 800, color: strat.win_rate >= 55 ? 'var(--green)' : strat.win_rate >= 45 ? 'var(--yellow)' : 'var(--red)' }}>{strat.win_rate}%</div>
                                            </div>
                                            <div>
                                                <div style={{ fontSize: 9, color: 'var(--text-dim)', marginBottom: 2 }}>TOTAL P&L</div>
                                                <div style={{ fontSize: 13, fontWeight: 800, color: strat.total_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>{strat.total_pnl > 0 ? '+' : ''}{strat.total_pnl}%</div>
                                            </div>
                                        </div>
                                    )}
                                    <div style={{ fontSize: 9, color: 'var(--text-dim)', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 4 }}>
                                        {strat.total_signals} Signals ({strat.wins}W / {strat.losses}L)
                                        {strat.best_coin && <span style={{ marginLeft: 4, color: 'var(--cyan)' }}>· {strat.best_coin} {strat.best_timeframe}</span>}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}

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
                                    <th>Current Price</th>
                                    <th>Stop Loss</th>
                                    <th>Take Profit</th>
                                    <th>P&L</th>
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
                                        <td style={{ fontFamily: 'var(--font-mono)' }}>{fmt(s.entry_price)}</td>
                                        <td style={{ fontFamily: 'var(--font-mono)', color: s.current_price ? 'var(--cyan)' : 'var(--text-dim)' }}>
                                            {s.current_price ? fmt(s.current_price) : '—'}
                                        </td>
                                        <td style={{ color: 'var(--red)', fontFamily: 'var(--font-mono)' }}>{fmt(s.stop_loss)}</td>
                                        <td style={{ color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>{fmt(s.take_profit)}</td>
                                        <td>
                                            {s.pnl_percent != null ? (
                                                <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontWeight: 700, color: s.pnl_percent >= 0 ? 'var(--green)' : 'var(--red)', fontFamily: 'var(--font-mono)' }}>
                                                    {s.pnl_percent >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                                                    {s.pnl_percent > 0 ? '+' : ''}{s.pnl_percent.toFixed(2)}%
                                                </span>
                                            ) : <span style={{ color: 'var(--text-dim)' }}>—</span>}
                                        </td>
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
                                                s.status === 'active' ? {} :
                                                s.status === 'wait' ? { background: 'rgba(255,193,7,0.12)', color: 'var(--yellow)', borderColor: 'rgba(255,193,7,0.3)' } :
                                                ['closed', 'won'].includes(s.status) ? { background: 'rgba(0,230,118,0.12)', color: 'var(--green)', borderColor: 'rgba(0,230,118,0.3)' } :
                                                { background: 'rgba(255,23,68,0.12)', color: 'var(--red)', borderColor: 'rgba(255,23,68,0.3)' }
                                            }>
                                                {s.status}
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
