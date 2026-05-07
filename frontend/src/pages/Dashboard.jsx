import { useQuery, useMutation } from '@tanstack/react-query'
import { useState, useCallback, useEffect } from 'react'
import { Scan, Zap, TrendingUp, TrendingDown, BarChart2, Star, Activity } from 'lucide-react'
import { API } from '../lib/api'
import { useSignalSocket } from '../lib/socket'
import StatCard from '../components/StatCard'
import PriceChart from '../components/PriceChart'
import SignalCard from '../components/SignalCard'
import toast from 'react-hot-toast'

// Fallback stats shown when backend is offline
const EMPTY_STATS = {
    total_coins_scanning: 0,
    active_signals: 0,
    today_total_signals: 0,
    today_wins: 0,
    today_losses: 0,
    today_win_rate: 0,
    today_loss_rate: 0,
    total_return: 0,
    top_performing_coins: [],
    bot_status: 'stopped',
}

export default function Dashboard() {
    const [liveSignals, setLiveSignals] = useState([])

    const { data: stats, isLoading: statsLoading, isError: statsError } = useQuery({
        queryKey: ['dashboardStats'],
        queryFn: API.getDashboardStats,
        refetchInterval: 30_000,
        retry: 1,
        // Return empty stats instead of undefined on error
        placeholderData: EMPTY_STATS,
    })

    const { data: signalsData } = useQuery({
        queryKey: ['liveSignals'],
        queryFn: API.getLiveSignals,
        refetchInterval: 15_000,
        retry: 1,
    })

    useEffect(() => {
        if (signalsData?.signals) setLiveSignals(signalsData.signals)
    }, [signalsData])

    const handleNewSignal = useCallback((sig) => {
        setLiveSignals(prev => [sig, ...prev].slice(0, 20))
    }, [])
    useSignalSocket(handleNewSignal)

    // Manual Scan Mutation
    const scanMutation = useMutation({
        mutationFn: () => API.triggerScanNow(),
        onSuccess: (data) => toast.success(data.message || 'Scan triggered!'),
        onError: () => toast.error('Failed to trigger scan')
    })

    // Use real stats or fallback
    const s = stats || EMPTY_STATS
    const topCoins = s.top_performing_coins || []

    const statCards = [
        {
            label: 'Coins Scanning',
            value: statsLoading ? null : statsError ? 'Offline' : String(s.total_coins_scanning),
            sub: statsError ? 'Start backend to scan' : 'Active USDT pairs',
            icon: Scan, color: statsError ? 'red' : 'cyan',
        },
        {
            label: 'Active Signals',
            value: statsLoading ? null : statsError ? '—' : String(s.active_signals),
            sub: 'Live right now',
            icon: Zap, color: 'yellow',
        },
        {
            label: 'Today Win %',
            value: statsLoading ? null : statsError ? '—' : `${s.today_win_rate}%`,
            sub: statsError ? '—' : `${s.today_wins} wins today`,
            icon: TrendingUp, color: 'green',
        },
        {
            label: 'Today Loss %',
            value: statsLoading ? null : statsError ? '—' : `${s.today_loss_rate}%`,
            sub: statsError ? '—' : `${s.today_losses} losses today`,
            icon: TrendingDown, color: 'red',
        },
        {
            label: 'Today Signals',
            value: statsLoading ? null : statsError ? '—' : String(s.today_total_signals),
            sub: statsError ? '—' : 'Total signals today',
            icon: Activity, color: 'cyan',
        },
        {
            label: 'Avg Return',
            value: statsLoading ? null : statsError ? '—' : `${s.total_return >= 0 ? '+' : ''}${s.total_return}%`,
            sub: 'Backtest average',
            icon: BarChart2, color: !statsError && s.total_return < 0 ? 'red' : 'green',
        },
        {
            label: 'Best Coin',
            value: statsLoading ? null : statsError ? '—' : (topCoins[0]?.symbol?.split('/')[0] ?? '—'),
            sub: statsError ? 'Run backtest first' : (topCoins[0] ? `${topCoins[0].win_rate?.toFixed(1)}% win rate` : 'Run backtest first'),
            icon: Star, color: 'purple',
        },
    ]

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, height: '100%', overflow: 'hidden' }}>

            {/* Stats Row */}
            <div style={{ display: 'flex', gap: 8, flexShrink: 0, flexWrap: 'wrap' }}>
                {statCards.map((card) => (
                    <StatCard
                        key={card.label}
                        label={card.label}
                        value={card.value}      // null = loading skeleton
                        sub={card.sub}
                        icon={card.icon}
                        color={card.color}
                    />
                ))}
            </div>

            {/* Main content */}
            <div style={{ display: 'flex', gap: 14, flex: 1, minHeight: 0 }}>

                {/* Left: Chart + table */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
                    {/* Price chart — always works (fetches from Binance directly) */}
                    <div className="card" style={{ flex: 1, padding: 0, overflow: 'hidden', minHeight: 200 }}>
                        <PriceChart />
                    </div>

                    {/* Top backtest performers */}
                    <div className="card" style={{ flexShrink: 0, padding: '12px 16px' }}>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', letterSpacing: '0.08em', marginBottom: 10 }}>
                            TOP BACKTEST PERFORMERS
                        </div>
                        {topCoins.length === 0 ? (
                            <div style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                                {statsError
                                    ? '⚡ Start backend to load backtest data'
                                    : 'No backtest results yet — run a backtest to populate'}
                            </div>
                        ) : (
                            <table className="data-table" style={{ minWidth: 500 }}>
                                <thead><tr><th>Coin</th><th>Strategy</th><th>Win Rate</th><th>Return</th></tr></thead>
                                <tbody>
                                    {topCoins.slice(0, 5).map((c, i) => (
                                        <tr key={i}>
                                            <td style={{ color: 'var(--cyan)', fontWeight: 700 }}>{c.symbol}</td>
                                            <td>{c.strategy}</td>
                                            <td><span style={{ color: (c.win_rate || 0) >= 65 ? 'var(--green)' : 'var(--yellow)', fontWeight: 700 }}>{(c.win_rate || 0).toFixed(1)}%</span></td>
                                            <td style={{ color: (c.total_return || 0) >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>
                                                {(c.total_return || 0) >= 0 ? '+' : ''}{(c.total_return || 0).toFixed(2)}%
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>

                {/* Right: Live Signals panel */}
                <div className="card" style={{
                    width: 320, flexShrink: 0,
                    display: 'flex', flexDirection: 'column',
                    padding: '12px 14px', overflow: 'hidden',
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', letterSpacing: '0.08em' }}>LIVE SIGNALS</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <button 
                                onClick={() => scanMutation.mutate()}
                                disabled={scanMutation.isPending || statsError}
                                style={{ 
                                    background: 'var(--card-hover)', border: '1px solid var(--border)', 
                                    color: 'var(--text-primary)', fontSize: 10, padding: '4px 8px', 
                                    borderRadius: 4, cursor: 'pointer', fontFamily: 'var(--font-mono)' 
                                }}
                            >
                                {scanMutation.isPending ? 'Scanning...' : 'Scan Now'}
                            </button>
                            {liveSignals.length > 0 && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                                    <div className="live-dot" />
                                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--green)' }}>{liveSignals.length}</span>
                                </div>
                            )}
                        </div>
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {liveSignals.length === 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '28px 0', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 11, textAlign: 'center', gap: 8 }}>
                                <Zap size={22} color="var(--text-dim)" strokeWidth={1} />
                                <div>No active signals</div>
                                <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>
                                    {statsError
                                        ? 'Start the backend scanner to generate signals'
                                        : 'Scanner generates signals every 15 min'}
                                </div>
                            </div>
                        ) : liveSignals.map((sig, i) => (
                            <div key={sig.id || i} className="animate-fade-in">
                                <SignalCard signal={sig} />
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    )
}
