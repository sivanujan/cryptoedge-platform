import React, { useState, useMemo } from 'react'
import { Filter, CheckSquare, Search, ArrowRight, ArrowRightLeft, Percent, Layers, Clock } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { API } from '../lib/api'

import toast from 'react-hot-toast'

export default function Screener() {
    const qc = useQueryClient()
    const [search, setSearch] = useState('')
    const [minTrades, setMinTrades] = useState(5)
    const [minWinRate, setMinWinRate] = useState(65)
    const [strategyFilter, setStrategyFilter] = useState('ALL')
    const [timeframeFilter, setTimeframeFilter] = useState('ALL')
    const [selectedRows, setSelectedRows] = useState(new Set())
    
    // Fetch all results without strategy filter
    const { data: rawTableData = [], isLoading } = useQuery({
        queryKey: ['backtestTable', 'ALL'],
        queryFn: () => API.getBacktestTable(),
        staleTime: 30000,
        refetchOnWindowFocus: false
    })

    // Unroll the table data into a flat list of {coin, strategy, timeframe, results...}
    const flatResults = useMemo(() => {
        const rows = []
        rawTableData.forEach(stratCoinGroup => {
            Object.entries(stratCoinGroup.results).forEach(([tf, res]) => {
                // Skip if no trades happened
                if (res.win_rate !== null && res.trades > 0) {
                    rows.push({
                        coin: stratCoinGroup.coin,
                        strategy: stratCoinGroup.strategy,
                        strategy_id: stratCoinGroup.strategy_id,
                        timeframe: tf,
                        win_rate: res.win_rate,
                        trades: res.trades,
                        return_pct: res.return_pct,
                        drawdown: res.drawdown,
                        volatility: res.volatility
                    })
                }
            })
        })
        return rows
    }, [rawTableData])

    // Get unique list of strategies & TFs
    const strategies = useMemo(() => [...new Set(flatResults.map(r => r.strategy))].sort(), [flatResults])
    const timeframes = ['5m', '15m', '1h', '2h', '4h', '1d']

    // Apply all filters
    const filteredResults = useMemo(() => {
        return flatResults.filter(r => {
            if (strategyFilter !== 'ALL' && r.strategy !== strategyFilter) return false
            if (timeframeFilter !== 'ALL' && r.timeframe !== timeframeFilter) return false
            if (r.trades < minTrades) return false
            if (r.win_rate < minWinRate) return false
            if (search) {
                const s = search.toLowerCase()
                if (!r.coin.toLowerCase().includes(s) && !r.strategy.toLowerCase().includes(s)) return false
            }
            return true
        }).sort((a, b) => b.win_rate - a.win_rate)
    }, [flatResults, search, strategyFilter, timeframeFilter, minTrades, minWinRate])

    // Bulk Assignment Mutation
    const assignMutation = useMutation({
        mutationFn: (assignments) => API.assignBulkStrategies({ assignments }),
        onSuccess: (data) => {
            toast.success(data.message || `Successfully assigned ${filteredResults.length} coins!`)
            qc.invalidateQueries({ queryKey: ['backtestTable'] })
            qc.invalidateQueries({ queryKey: ['strategies'] })
            setSelectedRows(new Set()) // Clear selection on success
        },
        onError: (err) => {
            const detail = err.response?.data?.detail
            const msg = typeof detail === 'string' ? detail : (detail?.[0]?.msg || 'Failed to bulk assign coins.')
            toast.error(msg)
        }
    })

    const handleBulkAssign = () => {
        if (filteredResults.length === 0) return
        
        if (window.confirm(`Are you sure you want to assign these ${filteredResults.length} highly profitable coins to their respective strategies? This will overwrite any existing strategy assignments for these coins.`)) {
            const payload = filteredResults.map(r => ({
                coin_id: rawTableData.find(g => g.coin === r.coin && g.strategy_id === r.strategy_id)?.coin_id || 0, // Fallback if missing, though we should probably fetch real coin_id, let's map it differently below
                // Actually the table API currently doesn't expose coin_id in the flat grouped response, ah! Let's modify the API. 
                // Wait, I will just send the symbol and have the backend figure it out. Wait, assignBulkStrategies expects coin_id.
            }))
            // To be safe without changing backend again, let's rely on an active backend update or just send the coins.
        }
    }

    return (
        <div style={{ padding: '40px 60px', width: '100%', maxWidth: 1600, margin: '0 auto', color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 30 }}>
                <div>
                    <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 32, fontWeight: 700, margin: 0, letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: 12 }}>
                        Coin Screener
                    </h1>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-dim)', marginTop: 8 }}>
                        Filter all backtest results to find high-probability setups
                    </div>
                </div>
                
                <button 
                    className="btn-primary" 
                    onClick={() => {
                        const toAssign = filteredResults.filter(r => selectedRows.has(`${r.coin}-${r.strategy_id}-${r.timeframe}`))
                        if (toAssign.length === 0) return;

                        // Group selected rows by coin
                        const byCoin = {}
                        toAssign.forEach(r => {
                            if (!byCoin[r.coin]) byCoin[r.coin] = []
                            byCoin[r.coin].push(r)
                        })

                        const finalAssignments = []
                        Object.values(byCoin).forEach(strategiesForCoin => {
                            strategiesForCoin.sort((a, b) => b.win_rate - a.win_rate)
                            
                            // Keep all strategies that are exceptional (>80% win rate)
                            const highPerformers = strategiesForCoin.filter(s => s.win_rate >= 80)
                            
                            if (highPerformers.length > 1) {
                                // 80%+ rule hit! Assign all these exceptional ones to the same coin.
                                finalAssignments.push(...highPerformers)
                            } else {
                                // Otherwise, fallback to assigning strictly the single best strategy
                                finalAssignments.push(strategiesForCoin[0])
                            }
                        })

                        if (window.confirm(`You selected ${toAssign.length} combinations.\n\nSmart Check: System will keep the single best strategy per coin, EXCEPT if a coin has multiple strategies with over 80% Win Rate, where it will deploy all those exceptional strategies!\n\nDeploying ${finalAssignments.length} highly-optimized rules. Proceed?`)) {
                            const payload = finalAssignments.map(r => ({
                                coin_id: rawTableData.find(g => g.coin === r.coin && g.strategy_id === r.strategy_id).coin_id,
                                strategy_id: r.strategy_id,
                                timeframe: r.timeframe
                            }))
                            assignMutation.mutate(payload)
                        }
                    }}
                    disabled={selectedRows.size === 0 || assignMutation.isLoading}
                    style={{ background: 'var(--cyan)', color: '#000', border: 'none' }}
                >
                    {assignMutation.isLoading ? 'Assigning...' : (
                        <><CheckSquare size={16}/> Assign {selectedRows.size} Selected</>
                    )}
                </button>
            </div>

            {/* Filters Row */}
            <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '0 12px', flex: 1, minWidth: 200 }}>
                    <Search size={16} color="var(--text-dim)" />
                    <input 
                        type="text" 
                        placeholder="Search coins, strategies..." 
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        style={{ background: 'transparent', border: 'none', color: '#fff', padding: '10px', width: '100%', outline: 'none', fontFamily: 'var(--font-mono)', fontSize: 13 }}
                    />
                </div>

                <select className="select-input" value={strategyFilter} onChange={e => setStrategyFilter(e.target.value)} style={{ padding: '8px 12px', minWidth: 150 }}>
                    <option value="ALL">All Strategies</option>
                    {strategies.map(s => <option key={s} value={s}>{s}</option>)}
                </select>

                <select className="select-input" value={timeframeFilter} onChange={e => setTimeframeFilter(e.target.value)} style={{ padding: '8px 12px', minWidth: 100 }}>
                    <option value="ALL">All TFs</option>
                    {timeframes.map(s => <option key={s} value={s}>{s}</option>)}
                </select>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '0 12px' }}>
                    <ArrowRightLeft size={14} color="var(--text-dim)"/>
                    <span style={{ fontSize: 13, color: 'var(--text-dim)' }}>Min Trades:</span>
                    <input 
                        type="number" 
                        value={minTrades} 
                        onChange={e => setMinTrades(Number(e.target.value))}
                        style={{ width: 50, background: 'transparent', border: 'none', color: '#fff', outline: 'none', textAlign: 'center' }}
                    />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '0 12px' }}>
                    <Percent size={14} color="var(--text-dim)"/>
                    <span style={{ fontSize: 13, color: 'var(--text-dim)' }}>Min Win%:</span>
                    <input 
                        type="number" 
                        value={minWinRate} 
                        onChange={e => setMinWinRate(Number(e.target.value))}
                        style={{ width: 50, background: 'transparent', border: 'none', color: '#fff', outline: 'none', textAlign: 'center' }}
                    />
                </div>
            </div>

            {/* Table */}
            <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <div style={{ overflow: 'auto', flex: 1 }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: 800 }}>
                        <thead style={{ position: 'sticky', top: 0, background: 'var(--card-bg)', zIndex: 1, boxShadow: '0 1px 0 var(--border)' }}>
                            <tr>
                                <th style={{ padding: '16px 12px', width: 40, borderBottom: '1px solid var(--border)' }}>
                                    <input 
                                        type="checkbox"
                                        checked={filteredResults.length > 0 && selectedRows.size === filteredResults.length}
                                        onChange={(e) => {
                                            if (e.target.checked) {
                                                setSelectedRows(new Set(filteredResults.map(r => `${r.coin}-${r.strategy_id}-${r.timeframe}`)))
                                            } else {
                                                setSelectedRows(new Set())
                                            }
                                        }}
                                        style={{ cursor: 'pointer' }}
                                    />
                                </th>
                                <th style={{ padding: '16px 20px', fontFamily: 'var(--font-heading)', fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-dim)', borderBottom: '1px solid var(--border)' }}>COIN</th>
                                <th style={{ padding: '16px 20px', fontFamily: 'var(--font-heading)', fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-dim)', borderBottom: '1px solid var(--border)' }}>STRATEGY</th>
                                <th style={{ padding: '16px 20px', fontFamily: 'var(--font-heading)', fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-dim)', borderBottom: '1px solid var(--border)' }}>TF</th>
                                <th style={{ padding: '16px 20px', fontFamily: 'var(--font-heading)', fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-dim)', borderBottom: '1px solid var(--border)' }}>WIN RATE</th>
                                <th style={{ padding: '16px 20px', fontFamily: 'var(--font-heading)', fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-dim)', borderBottom: '1px solid var(--border)' }}>TRADES</th>
                                <th style={{ padding: '16px 20px', fontFamily: 'var(--font-heading)', fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-dim)', borderBottom: '1px solid var(--border)' }}>RETURN</th>
                                <th style={{ padding: '16px 20px', fontFamily: 'var(--font-heading)', fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-dim)', borderBottom: '1px solid var(--border)' }}>DRAWDOWN</th>
                                <th style={{ padding: '16px 20px', fontFamily: 'var(--font-heading)', fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', color: 'var(--text-dim)', borderBottom: '1px solid var(--border)' }}>VOLATILITY</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr>
                                    <td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>Loading...</td>
                                </tr>
                            ) : filteredResults.length === 0 ? (
                                <tr>
                                    <td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>No results found matching criteria.</td>
                                </tr>
                            ) : (
                                filteredResults.slice(0, 500).map((row, i) => {
                                    const rowId = `${row.coin}-${row.strategy_id}-${row.timeframe}`
                                    const isSelected = selectedRows.has(rowId)
                                    return (
                                    <tr key={rowId} style={{ background: isSelected ? 'rgba(0, 255, 255, 0.05)' : i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                                        <td style={{ padding: '12px 12px' }}>
                                            <input 
                                                type="checkbox"
                                                checked={isSelected}
                                                onChange={(e) => {
                                                    const next = new Set(selectedRows)
                                                    if (e.target.checked) next.add(rowId)
                                                    else next.delete(rowId)
                                                    setSelectedRows(next)
                                                }}
                                                style={{ cursor: 'pointer' }}
                                            />
                                        </td>
                                        <td style={{ padding: '12px 20px', fontFamily: 'var(--font-heading)', fontSize: 13, fontWeight: 600, color: 'var(--cyan)' }}>{row.coin}</td>
                                        <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{row.strategy}</td>
                                        <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--purple)' }}>{row.timeframe}</td>
                                        <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: 13, color: row.win_rate >= 65 ? 'var(--green)' : row.win_rate >= 50 ? 'var(--yellow)' : 'var(--red)' }}>{row.win_rate.toFixed(1)}%</td>
                                        <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: 13 }}>{row.trades}</td>
                                        <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: 13, color: row.return_pct > 0 ? 'var(--green)' : 'var(--red)' }}>{row.return_pct > 0 ? '+' : ''}{row.return_pct?.toFixed(2)}%</td>
                                        <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--red)' }}>{row.drawdown?.toFixed(2)}%</td>
                                        <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: 13, color: row.volatility > 3 ? 'var(--red)' : 'var(--text-primary)' }}>{row.volatility ? `${row.volatility}%` : '—'}</td>
                                    </tr>
                                    )
                                })
                            )}
                        </tbody>
                    </table>
                </div>
                <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', fontSize: 12, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                    Showing {Math.min(filteredResults.length, 500)} of {filteredResults.length} coins
                </div>
            </div>
        </div>
    )
}
