import React, { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
    Cpu, Target, Award, ShieldAlert, CheckCircle2, AlertTriangle, 
    ArrowUpRight, ArrowDownRight, RefreshCw, X, ChevronRight, Zap 
} from 'lucide-react'
import { API } from '../lib/api'
import toast from 'react-hot-toast'

export default function AIFilteredSignals() {
    const queryClient = useQueryClient()
    const [strategyFilter, setStrategyFilter] = useState('ALL')
    const [coinSearch, setCoinSearch] = useState('')
    const [aiFilter, setAiFilter] = useState('ALL') // ALL, EVALUATED, PENDING
    const [selectedSignal, setSelectedSignal] = useState(null)
    const [showModal, setShowModal] = useState(false)
    const [evaluatingId, setEvaluatingId] = useState(null)

    // Fetch signals
    const { data, isLoading, refetch, isRefetching } = useQuery({
        queryKey: ['signalsHistory', { limit: 100 }],
        queryFn: () => API.getSignalHistory({ limit: 100 }),
        staleTime: 10000,
        refetchOnWindowFocus: false
    })

    // Fetch strategies for filters
    const { data: strategiesData } = useQuery({
        queryKey: ['strategies'],
        queryFn: () => API.getStrategies()
    })
    const strategies = strategiesData?.strategies || []

    const signalsList = data?.signals || []

    // Mutate to evaluate signal with AI
    const evaluateMutation = useMutation({
        mutationFn: (id) => API.evaluateSignalWithAI(id),
        onSuccess: (res, id) => {
            toast.success('AI Evaluation completed successfully!')
            queryClient.invalidateQueries(['signalsHistory'])
            setEvaluatingId(null)
            
            // Auto open the detailed modal
            const s = signalsList.find(item => item.id === id)
            if (s) {
                // Construct temporary updated signal to view details immediately
                const updatedSignal = {
                    ...s,
                    ai_score: res.ai_score,
                    ai_analysis: s.ai_analysis ? res.ai_analysis : JSON.stringify(res.ai_analysis)
                }
                setSelectedSignal(updatedSignal)
                setShowModal(true)
            }
        },
        onError: (err) => {
            console.error(err)
            toast.error(err.response?.data?.message || 'AI Evaluation failed. Please try again.')
            setEvaluatingId(null)
        }
    })

    const handleEvaluate = (id) => {
        setEvaluatingId(id)
        evaluateMutation.mutate(id)
    }

    // Filter & Search Logic
    const filteredSignals = useMemo(() => {
        return signalsList.filter(s => {
            const matchesStrategy = strategyFilter === 'ALL' || s.strategy === strategyFilter
            const matchesCoin = !coinSearch || s.symbol.toLowerCase().includes(coinSearch.toLowerCase())
            
            const isEvaluated = s.ai_score !== null && s.ai_score !== undefined
            const matchesAi = aiFilter === 'ALL' || 
                             (aiFilter === 'EVALUATED' && isEvaluated) || 
                             (aiFilter === 'PENDING' && !isEvaluated)

            return matchesStrategy && matchesCoin && matchesAi
        })
    }, [signalsList, strategyFilter, coinSearch, aiFilter])

    // Parse AI details safely
    const parsedAnalysis = useMemo(() => {
        if (!selectedSignal || !selectedSignal.ai_analysis) return null
        try {
            if (typeof selectedSignal.ai_analysis === 'object') {
                return selectedSignal.ai_analysis
            }
            return JSON.parse(selectedSignal.ai_analysis)
        } catch (e) {
            console.error("Failed to parse analysis JSON", e)
            return null
        }
    }, [selectedSignal])

    return (
        <div style={{ padding: '40px 60px', width: '100%', maxWidth: 1600, margin: '0 auto', color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'auto' }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 30 }}>
                <div>
                    <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 32, fontWeight: 700, margin: 0, letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: 12 }}>
                        <Cpu size={32} color="var(--cyan)" />
                        AI Filtered Signals
                    </h1>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-dim)', marginTop: 8 }}>
                        Run instant machine learning evaluations on strategy signals using free OpenRouter Llama models
                    </div>
                </div>
                
                <button 
                    onClick={() => refetch()}
                    disabled={isLoading || isRefetching}
                    style={{
                        padding: '10px 16px',
                        background: 'var(--bg-secondary)',
                        color: 'var(--text-primary)',
                        border: '1px solid var(--border)',
                        borderRadius: '10px',
                        cursor: 'pointer',
                        fontSize: '13px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        transition: 'all 0.2s',
                        fontWeight: 600
                    }}
                >
                    <RefreshCw size={14} className={isRefetching ? 'spin' : ''} />
                    Refresh
                </button>
            </div>

            {/* Filters */}
            <div className="card" style={{ padding: 20, marginBottom: 25, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, alignItems: 'center' }}>
                <div>
                    <label style={{ fontSize: '11px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 6 }}>SEARCH COIN</label>
                    <input 
                        type="text"
                        placeholder="e.g. BTC"
                        value={coinSearch}
                        onChange={e => setCoinSearch(e.target.value)}
                        style={{ width: '100%', padding: '10px 12px', background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '13px' }}
                    />
                </div>

                <div>
                    <label style={{ fontSize: '11px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 6 }}>STRATEGY</label>
                    <select 
                        value={strategyFilter} 
                        onChange={e => setStrategyFilter(e.target.value)} 
                        style={{ width: '100%', padding: '10px 12px', background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '13px' }}
                    >
                        <option value="ALL">All Strategies</option>
                        {strategies.map(s => <option key={s.id} value={s.name}>{s.name}</option>)}
                    </select>
                </div>

                <div>
                    <label style={{ fontSize: '11px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 6 }}>AI EVALUATION FILTER</label>
                    <div style={{ display: 'flex', gap: 8 }}>
                        {['ALL', 'EVALUATED', 'PENDING'].map(filter => (
                            <button
                                key={filter}
                                onClick={() => setAiFilter(filter)}
                                style={{
                                    flex: 1,
                                    padding: '8px 10px',
                                    borderRadius: '6px',
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                    border: '1px solid var(--border)',
                                    background: aiFilter === filter ? 'rgba(0, 229, 255, 0.15)' : 'var(--bg-primary)',
                                    color: aiFilter === filter ? 'var(--cyan)' : 'var(--text-secondary)',
                                    transition: 'all 0.2s'
                                }}
                            >
                                {filter}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Main Content Table */}
            <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto', flex: 1 }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: 900 }}>
                        <thead style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)', position: 'sticky', top: 0, zIndex: 2 }}>
                            <tr>
                                <th style={{ padding: '14px 20px', color: 'var(--text-dim)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>COIN / TF</th>
                                <th style={{ padding: '14px 20px', color: 'var(--text-dim)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>DIRECTION</th>
                                <th style={{ padding: '14px 20px', color: 'var(--text-dim)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>STRATEGY</th>
                                <th style={{ padding: '14px 20px', color: 'var(--text-dim)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>ENTRY PRICE</th>
                                <th style={{ padding: '14px 20px', color: 'var(--text-dim)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>SL / TP</th>
                                <th style={{ padding: '14px 20px', color: 'var(--text-dim)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>AI CONFLUENCE SCORE</th>
                                <th style={{ padding: '14px 20px', color: 'var(--text-dim)', fontSize: '12px', fontFamily: 'var(--font-mono)', textAlign: 'right' }}>ACTIONS</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr>
                                    <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: 'var(--text-dim)' }}>
                                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                                            <RefreshCw size={24} className="spin" color="var(--cyan)" />
                                            <span>Loading strategy signals...</span>
                                        </div>
                                    </td>
                                </tr>
                            ) : filteredSignals.length === 0 ? (
                                <tr>
                                    <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                                        No signals match your filters.
                                    </td>
                                </tr>
                            ) : (
                                filteredSignals.map((sig) => {
                                    const isBuy = sig.signal_type === 'BUY'
                                    const isEvaluated = sig.ai_score !== null && sig.ai_score !== undefined
                                    
                                    // Parse score analysis
                                    let verdict = 'PENDING'
                                    let parsedAnalysisObj = null
                                    try {
                                        if (sig.ai_analysis) {
                                            parsedAnalysisObj = typeof sig.ai_analysis === 'object' ? sig.ai_analysis : JSON.parse(sig.ai_analysis)
                                            verdict = parsedAnalysisObj.grade || (sig.ai_score >= 71 ? 'TAKE' : 'SKIP')
                                        }
                                    } catch(err) {}

                                    // Color indicators
                                    let scoreColor = 'var(--text-dim)'
                                    let scoreBg = 'rgba(255,255,255,0.03)'
                                    if (isEvaluated) {
                                        if (sig.ai_score >= 86) {
                                            scoreColor = 'var(--green)'
                                            scoreBg = 'rgba(0, 230, 118, 0.08)'
                                        } else if (sig.ai_score >= 71) {
                                            scoreColor = 'var(--cyan)'
                                            scoreBg = 'rgba(0, 229, 255, 0.08)'
                                        } else {
                                            scoreColor = 'var(--red)'
                                            scoreBg = 'rgba(255, 23, 68, 0.08)'
                                        }
                                    }

                                    return (
                                        <tr key={sig.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)', verticalAlign: 'middle', height: 60 }}>
                                            <td style={{ padding: '12px 20px' }}>
                                                <div style={{ fontWeight: 700, color: 'var(--cyan)' }}>{sig.symbol}</div>
                                                <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>{sig.timeframe}</div>
                                            </td>
                                            <td style={{ padding: '12px 20px' }}>
                                                <span style={{ 
                                                    display: 'inline-flex', alignItems: 'center', gap: 4,
                                                    fontSize: '11px', fontWeight: 800, padding: '4px 8px', borderRadius: 4,
                                                    background: isBuy ? 'rgba(0, 230, 118, 0.1)' : 'rgba(255, 23, 68, 0.1)',
                                                    color: isBuy ? 'var(--green)' : 'var(--red)'
                                                }}>
                                                    {isBuy ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                                                    {sig.signal_type}
                                                </span>
                                            </td>
                                            <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>{sig.strategy}</td>
                                            <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{sig.entry_price}</td>
                                            <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                                                <div><span style={{ color: 'var(--red)', marginRight: 4 }}>SL:</span>{sig.stop_loss || 'N/A'}</div>
                                                <div style={{ marginTop: 2 }}><span style={{ color: 'var(--green)', marginRight: 4 }}>TP:</span>{sig.take_profit || 'N/A'}</div>
                                            </td>
                                            <td style={{ padding: '12px 20px' }}>
                                                {isEvaluated ? (
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                        <span style={{
                                                            fontSize: '13px', fontWeight: 800, padding: '4px 10px', borderRadius: 6,
                                                            color: scoreColor, background: scoreBg, border: `1px solid ${scoreColor}20`
                                                        }}>
                                                            {Math.round(sig.ai_score)} / 100
                                                        </span>
                                                        <span style={{
                                                            fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)'
                                                        }}>
                                                            ({verdict})
                                                        </span>
                                                    </div>
                                                ) : (
                                                    <span style={{ color: 'var(--text-dim)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>Not Filtered</span>
                                                )}
                                            </td>
                                            <td style={{ padding: '12px 20px', textAlign: 'right' }}>
                                                {isEvaluated ? (
                                                    <button
                                                        onClick={() => {
                                                            setSelectedSignal(sig)
                                                            setShowModal(true)
                                                        }}
                                                        style={{
                                                            padding: '8px 14px',
                                                            background: 'rgba(0, 229, 255, 0.08)',
                                                            color: 'var(--cyan)',
                                                            border: '1px solid var(--cyan)',
                                                            borderRadius: '8px',
                                                            fontSize: '12px',
                                                            fontWeight: 700,
                                                            cursor: 'pointer',
                                                            transition: 'all 0.2s'
                                                        }}
                                                        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(0, 229, 255, 0.15)' }}
                                                        onMouseLeave={e => { e.currentTarget.style.background = 'rgba(0, 229, 255, 0.08)' }}
                                                    >
                                                        View Analysis
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={() => handleEvaluate(sig.id)}
                                                        disabled={evaluatingId !== null}
                                                        style={{
                                                            padding: '8px 14px',
                                                            background: 'linear-gradient(135deg, var(--cyan), var(--purple))',
                                                            color: '#000',
                                                            border: 'none',
                                                            borderRadius: '8px',
                                                            fontSize: '12px',
                                                            fontWeight: 800,
                                                            cursor: 'pointer',
                                                            display: 'inline-flex',
                                                            alignItems: 'center',
                                                            gap: 6,
                                                            transition: 'all 0.2s',
                                                            opacity: evaluatingId !== null ? 0.6 : 1
                                                        }}
                                                    >
                                                        {evaluatingId === sig.id ? (
                                                            <>
                                                                <RefreshCw size={12} className="spin" />
                                                                Evaluating...
                                                            </>
                                                        ) : (
                                                            <>
                                                                <Zap size={12} fill="#000" />
                                                                Evaluate with AI
                                                            </>
                                                        )}
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    )
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Analysis Detailed Modal */}
            {showModal && selectedSignal && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }} onClick={() => setShowModal(false)}>
                    <div className="card" style={{ maxWidth: 650, width: '100%', maxHeight: '90vh', overflowY: 'auto', padding: 28, position: 'relative', display: 'flex', flexDirection: 'column', gap: 20 }} onClick={e => e.stopPropagation()}>
                        <button onClick={() => setShowModal(false)} style={{ position: 'absolute', top: 20, right: 20, background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}><X size={20} /></button>

                        {/* Title */}
                        <div>
                            <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.05em' }}>AI SIGNAL AUDIT REPORT</div>
                            <h2 style={{ fontSize: '24px', fontWeight: 800, margin: '4px 0 0 0', display: 'flex', alignItems: 'center', gap: 10 }}>
                                {selectedSignal.symbol}
                                <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-dim)' }}>({selectedSignal.timeframe})</span>
                            </h2>
                        </div>

                        {/* Score Banner */}
                        <div style={{
                            padding: '16px 20px',
                            borderRadius: '12px',
                            background: 'var(--bg-secondary)',
                            border: '1px solid var(--border)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                        }}>
                            <div>
                                <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>DECISION VERDICT</div>
                                <div style={{ 
                                    fontSize: '22px', fontWeight: 900, marginTop: 4, 
                                    color: selectedSignal.ai_score >= 71 ? 'var(--green)' : 'var(--red)',
                                    display: 'flex', alignItems: 'center', gap: 6
                                }}>
                                    {selectedSignal.ai_score >= 71 ? <CheckCircle2 size={22} /> : <ShieldAlert size={22} />}
                                    {selectedSignal.ai_score >= 86 ? 'PREMIUM (TAKE)' : selectedSignal.ai_score >= 71 ? 'GOOD (TAKE)' : 'WEAK (SKIP)'}
                                </div>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                                <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>CONFIDENCE SCORE</div>
                                <div style={{ fontSize: '24px', fontWeight: 900, color: 'var(--cyan)', marginTop: 4 }}>
                                    {Math.round(selectedSignal.ai_score)} <span style={{ fontSize: 13, color: 'var(--text-dim)' }}>/ 100</span>
                                </div>
                            </div>
                        </div>

                        {/* Trade Parameters Info */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, background: 'rgba(255,255,255,0.01)', padding: '12px 16px', borderRadius: '8px', border: '1px solid var(--border)' }}>
                            <div>
                                <div style={{ fontSize: '9px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>DIRECTION</div>
                                <div style={{ fontWeight: 800, color: selectedSignal.signal_type === 'BUY' ? 'var(--green)' : 'var(--red)', fontSize: '13px', marginTop: 2 }}>{selectedSignal.signal_type}</div>
                            </div>
                            <div>
                                <div style={{ fontSize: '9px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>ENTRY</div>
                                <div style={{ fontWeight: 700, fontSize: '13px', marginTop: 2, fontFamily: 'var(--font-mono)' }}>{selectedSignal.entry_price}</div>
                            </div>
                            <div>
                                <div style={{ fontSize: '9px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>STOP LOSS</div>
                                <div style={{ fontWeight: 700, fontSize: '13px', marginTop: 2, fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>{selectedSignal.stop_loss || '—'}</div>
                            </div>
                            <div>
                                <div style={{ fontSize: '9px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>TAKE PROFIT</div>
                                <div style={{ fontWeight: 700, fontSize: '13px', marginTop: 2, fontFamily: 'var(--font-mono)', color: 'var(--green)' }}>{selectedSignal.take_profit || '—'}</div>
                            </div>
                        </div>

                        {/* AI Analysis details */}
                        {parsedAnalysis ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                                {/* Final Reasoning (Plain language summary) */}
                                {parsedAnalysis.final_reasoning && (
                                    <div style={{ padding: '12px 16px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', borderLeft: '3px solid var(--cyan)', fontSize: '13px', fontStyle: 'italic', color: 'var(--text-secondary)' }}>
                                        "{parsedAnalysis.final_reasoning}"
                                    </div>
                                )}

                                {/* Reasons */}
                                {(parsedAnalysis.confluence_reasons || parsedAnalysis.reasons) && (
                                    <div>
                                        <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--green)', margin: '0 0 8px 0', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <CheckCircle2 size={13} />
                                            CONFLUENCE REASONS
                                        </h4>
                                        <ul style={{ margin: 0, paddingLeft: 20, fontSize: '12.5px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                                            {(parsedAnalysis.confluence_reasons || parsedAnalysis.reasons || []).map((r, idx) => <li key={idx}>{r}</li>)}
                                        </ul>
                                    </div>
                                )}

                                {/* Warnings & Penalties */}
                                {(((parsedAnalysis.risk_warnings || parsedAnalysis.warnings) && (parsedAnalysis.risk_warnings || parsedAnalysis.warnings).length > 0) || 
                                  ((parsedAnalysis.penalty_breakdown || parsedAnalysis.penalties) && (parsedAnalysis.penalty_breakdown || parsedAnalysis.penalties).length > 0)) && (
                                    <div>
                                        <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--yellow)', margin: '0 0 8px 0', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <AlertTriangle size={13} />
                                            RISK WARNINGS & PENALTIES
                                        </h4>
                                        <ul style={{ margin: 0, paddingLeft: 20, fontSize: '12.5px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                                            {(parsedAnalysis.risk_warnings || parsedAnalysis.warnings || []).map((w, idx) => <li key={idx} style={{ color: 'var(--yellow)' }}>{w}</li>)}
                                            {(parsedAnalysis.penalty_breakdown || parsedAnalysis.penalties || []).map((p, idx) => {
                                                const pText = typeof p === 'object' ? `${p.reason} (${p.points} pts)` : p
                                                return <li key={idx} style={{ color: 'rgba(255,255,255,0.7)' }}>{pText}</li>
                                            })}
                                        </ul>
                                    </div>
                                )}

                                {/* ICT Analysis Context */}
                                {parsedAnalysis.ict_analysis && (
                                    <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
                                        <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--purple)', margin: '0 0 10px 0', fontFamily: 'var(--font-mono)' }}>ICT / SMART MONEY CONCEPTS</h4>
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: '12px', color: 'var(--text-dim)' }}>
                                            <div>Structure Event: <span style={{ color: 'var(--text-primary)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>{parsedAnalysis.ict_analysis.structure_event || 'none'}</span></div>
                                            <div>Structure Alignment: <span style={{ color: parsedAnalysis.ict_analysis.structure_supports_signal ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>{parsedAnalysis.ict_analysis.structure_supports_signal ? 'ALIGNED' : 'CONTRADICTING'}</span></div>
                                            <div>FVG in Favor: <span style={{ color: parsedAnalysis.ict_analysis.fvg_present_in_favor ? 'var(--green)' : 'var(--text-dim)', fontWeight: 600 }}>{parsedAnalysis.ict_analysis.fvg_present_in_favor ? 'YES' : 'NO'}</span></div>
                                            <div>FVG Details: <span style={{ color: 'var(--text-primary)' }}>{parsedAnalysis.ict_analysis.fvg_note || 'None nearby'}</span></div>
                                            <div>Liquidity Sweep: <span style={{ color: parsedAnalysis.ict_analysis.liquidity_sweep_detected ? 'var(--green)' : 'var(--text-dim)', fontWeight: 600 }}>{parsedAnalysis.ict_analysis.liquidity_sweep_detected ? 'YES' : 'NO'}</span></div>
                                            <div>Sweep Details: <span style={{ color: 'var(--text-primary)' }}>{parsedAnalysis.ict_analysis.liquidity_sweep_note || 'No recent sweep'}</span></div>
                                            <div>Order Block Retest: <span style={{ color: parsedAnalysis.ict_analysis.order_block_retest ? 'var(--green)' : 'var(--text-dim)', fontWeight: 600 }}>{parsedAnalysis.ict_analysis.order_block_retest ? 'YES' : 'NO'}</span></div>
                                        </div>
                                    </div>
                                )}

                                {/* Market Context / Details */}
                                <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
                                    <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-dim)', margin: '0 0 10px 0', fontFamily: 'var(--font-mono)' }}>DERIVATIVES & TECHNICAL CONTEXT</h4>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: '12px', color: 'var(--text-dim)' }}>
                                        <div>Timeframe: <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{parsedAnalysis.timeframe || selectedSignal.timeframe}</span></div>
                                        <div>HTF Confirmed: <span style={{ color: (parsedAnalysis.direction_alignment?.aligned || parsedAnalysis.htf_confirmed) ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>{(parsedAnalysis.direction_alignment?.aligned || parsedAnalysis.htf_confirmed) ? 'YES' : 'NO'}</span></div>
                                        <div>Expires In: <span style={{ color: 'var(--text-primary)' }}>{parsedAnalysis.expires_in_candles ? `${parsedAnalysis.expires_in_candles} candles` : (parsedAnalysis.signal_expires_in || '3 candles')}</span></div>
                                        <div>Risk-Reward Ratio: <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{parsedAnalysis.risk_reward_ratio ? `${parsedAnalysis.risk_reward_ratio}:1` : 'N/A'}</span></div>
                                        <div>Volatility Regime: <span style={{ color: 'var(--text-primary)', textTransform: 'uppercase' }}>{parsedAnalysis.volatility_regime || 'Normal'}</span></div>
                                        <div>RSI Value: <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{parsedAnalysis.momentum?.rsi_value !== undefined ? parsedAnalysis.momentum.rsi_value : 'N/A'}</span></div>
                                        <div>RSI Divergence: <span style={{ color: parsedAnalysis.momentum?.rsi_divergence && parsedAnalysis.momentum.rsi_divergence !== 'none' ? 'var(--yellow)' : 'var(--green)', textTransform: 'uppercase', fontWeight: 600 }}>{parsedAnalysis.momentum?.rsi_divergence || 'none'}</span></div>
                                        <div>Funding Rate Risk: <span style={{ 
                                            color: parsedAnalysis.funding_rate_risk === 'none' ? 'var(--green)' : (parsedAnalysis.funding_rate_risk?.startsWith('crowded') ? 'var(--red)' : 'var(--text-primary)'),
                                            textTransform: 'uppercase', fontWeight: 600 
                                        }}>{parsedAnalysis.funding_rate_risk || 'N/A'}</span></div>
                                        <div>Open Interest: <span style={{ 
                                            color: parsedAnalysis.open_interest_signal === 'confirming' ? 'var(--green)' : (parsedAnalysis.open_interest_signal === 'diverging' ? 'var(--red)' : 'var(--text-primary)'),
                                            textTransform: 'uppercase', fontWeight: 600
                                        }}>{parsedAnalysis.open_interest_signal || 'N/A'}</span></div>
                                        <div>BTC Correlation: <span style={{ 
                                            color: parsedAnalysis.btc_correlation_risk === 'none' ? 'var(--green)' : (parsedAnalysis.btc_correlation_risk === 'altcoin_against_btc_trend' ? 'var(--red)' : 'var(--text-primary)'),
                                            textTransform: 'uppercase', fontWeight: 600
                                        }}>{parsedAnalysis.btc_correlation_risk || 'N/A'}</span></div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div style={{ padding: '20px 0', textAlign: 'center', color: 'var(--text-dim)', fontSize: 13 }}>
                                No structured analysis details available. Here is the raw data:
                                <pre style={{ marginTop: 10, padding: 12, background: 'var(--bg-primary)', borderRadius: 6, fontSize: 11, textAlign: 'left', overflow: 'auto', maxHeight: 150 }}>
                                    {selectedSignal.ai_analysis}
                                </pre>
                            </div>
                        )}

                        {/* Execute Button */}
                        <div style={{ display: 'flex', gap: 12, marginTop: 10 }}>
                            <button
                                onClick={() => setShowModal(false)}
                                style={{
                                    flex: 1,
                                    padding: '12px',
                                    background: 'var(--bg-secondary)',
                                    color: 'var(--text-primary)',
                                    border: '1px solid var(--border)',
                                    borderRadius: '10px',
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                    fontSize: '13px'
                                }}
                            >
                                Close Report
                            </button>
                            <button
                                onClick={() => {
                                    setShowModal(false)
                                    handleEvaluate(selectedSignal.id)
                                }}
                                disabled={evaluatingId !== null}
                                style={{
                                    flex: 1,
                                    padding: '12px',
                                    background: 'linear-gradient(135deg, var(--cyan), var(--purple))',
                                    color: '#000',
                                    border: 'none',
                                    borderRadius: '10px',
                                    fontWeight: 800,
                                    cursor: 'pointer',
                                    fontSize: '13px',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: 6,
                                    opacity: evaluatingId !== null ? 0.6 : 1
                                }}
                            >
                                <RefreshCw size={13} className={evaluatingId === selectedSignal.id ? "spin" : ""} />
                                Re-Evaluate
                            </button>
                            {selectedSignal.ai_score >= 71 && (
                                <button
                                    onClick={() => {
                                        toast.success(`Trade triggered successfully via AutoTrader:\n${selectedSignal.signal_type} ${selectedSignal.symbol} at ${selectedSignal.entry_price}`)
                                        setShowModal(false)
                                    }}
                                    style={{
                                        flex: 2,
                                        padding: '12px',
                                        background: 'linear-gradient(135deg, var(--green), var(--cyan))',
                                        color: '#000',
                                        border: 'none',
                                        borderRadius: '10px',
                                        fontWeight: 800,
                                        cursor: 'pointer',
                                        fontSize: '13px'
                                    }}
                                >
                                    Confirm Execution
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
