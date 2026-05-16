import React, { useMemo, useState } from 'react'
import { Target, Award, Zap, TrendingUp, TrendingDown, Clock, Percent, Shield } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { API } from '../lib/api'

export default function ElitePicks() {
    const [strategyFilter, setStrategyFilter] = useState('ALL')
    // Fetch all results
    const { data: rawTableData = [], isLoading } = useQuery({
        queryKey: ['backtestTable', 'ALL'],
        queryFn: () => API.getBacktestTable(),
        staleTime: 30000,
        refetchOnWindowFocus: false
    })

    // Unroll the table data into a flat list
    // Unroll the table data into a flat list and calculate scores
    const flatResults = useMemo(() => {
        const rows = []
        rawTableData.forEach(stratCoinGroup => {
            Object.entries(stratCoinGroup.results).forEach(([tf, res]) => {
                if (res.win_rate !== null && res.trades > 0) {
                    const row = {
                        coin: stratCoinGroup.coin,
                        strategy: stratCoinGroup.strategy,
                        strategy_id: stratCoinGroup.strategy_id,
                        timeframe: tf,
                        win_rate: res.win_rate,
                        trades: res.trades,
                        return_pct: res.return_pct,
                        drawdown: res.drawdown,
                        volatility: res.volatility
                    }

                    // Step 1: Hard Filter (Lowered to show results)
                    if (row.win_rate >= 50 && row.trades >= 5 && row.return_pct > 0) {
                        // Step 2: Confidence Weight
                        let weight = 0;
                        if (row.trades >= 100) weight = 1.00;
                        else if (row.trades >= 50) weight = 0.90;
                        else if (row.trades >= 30) weight = 0.75;
                        else if (row.trades >= 20) weight = 0.60;
                        else if (row.trades >= 5) weight = 0.40; // Added for lower threshold

                        // Step 3: Effective Win Rate
                        const effective_win = row.win_rate * weight;

                        // Step 4: Return Score
                        const return_score = Math.min(row.return_pct / 40, 1.0) * 20;

                        // Step 5: Final Score
                        const final_score = effective_win + return_score;

                        row.confidence_weight = weight;
                        row.effective_win = effective_win;
                        row.return_score = return_score;
                        row.final_score = final_score;

                        rows.push(row)
                    }
                }
            })
        })

        // Step 6: Find Valid Timeframes Per Coin
        const coinGroups = {}
        rows.forEach(r => {
            if (!coinGroups[r.coin]) coinGroups[r.coin] = []
            coinGroups[r.coin].push(r)
        })

        const finalRows = []
        Object.entries(coinGroups).forEach(([coin, coinRows]) => {
            const bestScore = Math.max(...coinRows.map(r => r.final_score))
            const threshold = bestScore * 0.70

            coinRows.forEach(r => {
                if (r.final_score >= threshold) {
                    finalRows.push(r)
                }
            })
        })

        return finalRows
    }, [rawTableData])

    const strategies = useMemo(() => [...new Set(flatResults.map(r => r.strategy))].sort(), [flatResults])

    // Filter by strategy for display
    const displayedResults = useMemo(() => {
        return flatResults.filter(r => 
            strategyFilter === 'ALL' || r.strategy === strategyFilter
        ).sort((a, b) => b.final_score - a.final_score)
    }, [flatResults, strategyFilter])

    // Calculate Dashboard Stats based on displayed results
    const stats = useMemo(() => {
        const uniqueCoins = new Set(displayedResults.map(r => r.coin))
        const profitableRows = displayedResults.filter(r => r.return_pct > 0)
        const uniqueProfitableCoins = new Set(profitableRows.map(r => r.coin))
        
        // Find top return
        let topReturn = { return_pct: 0, coin: 'N/A', timeframe: 'N/A' }
        if (displayedResults.length > 0) {
            const sortedByReturn = [...displayedResults].sort((a, b) => b.return_pct - a.return_pct)
            if (sortedByReturn[0]) {
                topReturn = sortedByReturn[0]
            }
        }

        // Find best timeframe (mode of profitable rows)
        const tfCounts = {}
        profitableRows.forEach(r => {
            tfCounts[r.timeframe] = (tfCounts[r.timeframe] || 0) + 1
        })
        const bestTf = Object.entries(tfCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A'

        return {
            coinsTested: uniqueCoins.size,
            profitableCoins: uniqueProfitableCoins.size,
            hitRate: uniqueCoins.size > 0 ? Math.round((uniqueProfitableCoins.size / uniqueCoins.size) * 100) : 0,
            bestTf,
            topReturn
        }
    }, [displayedResults])

    return (
        <div style={{ padding: '40px 60px', width: '100%', maxWidth: 1600, margin: '0 auto', color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'auto' }}>
            <div style={{ marginBottom: 30 }}>
                <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 32, fontWeight: 700, margin: 0, letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: 12 }}>
                    <Target size={32} color="var(--cyan)" />
                    Elite Picks & Analysis
                </h1>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-dim)', marginTop: 8 }}>
                    Curated high-probability setups and top performers
                </div>

                <div style={{ marginTop: 15 }}>
                    <select 
                        value={strategyFilter} 
                        onChange={e => setStrategyFilter(e.target.value)} 
                        style={{ padding: '8px 12px', minWidth: 250, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '13px' }}
                    >
                        <option value="ALL" style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}>All Strategies</option>
                        {strategies.map(s => <option key={s} value={s} style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}>{s}</option>)}
                    </select>
                </div>
            </div>

            {/* Stats Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 20, marginBottom: 30 }}>
                <div className="card" style={{ padding: '20px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>COINS TESTED</div>
                    <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--cyan)' }}>{stats.coinsTested}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>all USDT pairs</div>
                </div>
                <div className="card" style={{ padding: '20px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>PROFITABLE (&gt;0% return)</div>
                    <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--green)' }}>{stats.profitableCoins}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>{stats.hitRate}% hit rate</div>
                </div>
                <div className="card" style={{ padding: '20px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>BEST TIMEFRAME</div>
                    <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--purple)' }}>{stats.bestTf}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>of winners</div>
                </div>
                <div className="card" style={{ padding: '20px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>TOP RETURN FOUND</div>
                    <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--yellow)' }}>{Math.round(stats.topReturn.return_pct)}%</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>{stats.topReturn.coin} @ {stats.topReturn.timeframe}</div>
                </div>
            </div>

            {/* Ranked Coins Table */}
            <div style={{ marginBottom: 40 }}>
                <h2 style={{ fontSize: '18px', fontWeight: 700, marginBottom: 15, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Award size={20} color="var(--cyan)" />
                    RANKED COINS — FORMULA APPLIED (WIN ≥ 50%, TRADES ≥ 5)
                </h2>
                <div className="card" style={{ overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                        <thead style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
                            <tr>
                                <th style={{ padding: '12px 20px', color: 'var(--text-dim)', fontSize: '12px' }}>COIN</th>
                                <th style={{ padding: '12px 20px', color: 'var(--text-dim)', fontSize: '12px' }}>STRATEGY</th>
                                <th style={{ padding: '12px 20px', color: 'var(--text-dim)', fontSize: '12px' }}>TF</th>
                                <th style={{ padding: '12px 20px', color: 'var(--text-dim)', fontSize: '12px' }}>WIN RATE</th>
                                <th style={{ padding: '12px 20px', color: 'var(--text-dim)', fontSize: '12px' }}>TRADES</th>
                                <th style={{ padding: '12px 20px', color: 'var(--text-dim)', fontSize: '12px' }}>RETURN</th>
                                <th style={{ padding: '12px 20px', color: 'var(--text-dim)', fontSize: '12px' }}>FINAL SCORE</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr><td colSpan={7} style={{ padding: '20px', textAlign: 'center', color: 'var(--text-dim)' }}>Loading...</td></tr>
                            ) : displayedResults.length === 0 ? (
                                <tr><td colSpan={7} style={{ padding: '20px', textAlign: 'center', color: 'var(--text-dim)' }}>No coins match the criteria.</td></tr>
                            ) : (
                                displayedResults.slice(0, 50).map((row, i) => (
                                    <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                                        <td style={{ padding: '12px 20px', fontWeight: 700, color: 'var(--cyan)' }}>{row.coin}</td>
                                        <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>{row.strategy}</td>
                                        <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)' }}>{row.timeframe}</td>
                                        <td style={{ padding: '12px 20px', color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>{row.win_rate.toFixed(1)}%</td>
                                        <td style={{ padding: '12px 20px', fontFamily: 'var(--font-mono)' }}>{row.trades}</td>
                                        <td style={{ padding: '12px 20px', color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>+{row.return_pct.toFixed(1)}%</td>
                                        <td style={{ padding: '12px 20px', color: 'var(--yellow)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{row.final_score.toFixed(2)}</td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    )
}
