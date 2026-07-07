import { NavLink } from 'react-router-dom'
import {
    LayoutDashboard, FlaskConical, BookOpen,
    History, Settings, Activity, Zap, TrendingUp, TrendingDown, Filter, Cpu, Target, Award
} from 'lucide-react'

const NAV = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/journal', icon: BookOpen, label: 'Journal' },
    { to: '/backtest', icon: FlaskConical, label: 'Backtests' },
    { to: '/strategies', icon: BookOpen, label: 'Strategies' },
    { to: '/screener', icon: Filter, label: 'Screener' },
    { to: '/elite-picks', icon: Award, label: 'Elite Picks' },
    { to: '/signals', icon: History, label: 'Signals' },
    { to: '/deep-analysis', icon: Zap, label: 'Deep Analysis' },
    { to: '/futures', icon: Activity, label: 'Futures' },
    { to: '/autotrader', icon: Cpu, label: 'AutoTrader' },
    { to: '/signal-engine', icon: Target, label: 'Signal Engine' },
    { to: '/ai-filtered-signals', icon: Cpu, label: 'AI Filtered Signals' },
    { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar({ stats }) {
    const { totalCoins = 0, activeSignals = 0, todayWinRate = 0, botStatus = 'stopped' } = stats || {}

    return (
        <aside style={{
            width: 220,
            minWidth: 220,
            height: '100vh',
            background: 'var(--bg-secondary)',
            borderRight: '1px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
            zIndex: 10,
        }}>
            {/* Logo */}
            <div style={{
                padding: '20px 20px 16px',
                borderBottom: '1px solid var(--border)',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                        width: 32, height: 32,
                        background: 'linear-gradient(135deg, var(--cyan), var(--purple))',
                        borderRadius: 8,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <Zap size={16} color="#000" fill="#000" />
                    </div>
                    <div>
                        <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 800, fontSize: 16, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
                            CryptoEdge
                        </div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)', letterSpacing: '0.1em' }}>
                            TRADING TERMINAL
                        </div>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav style={{ flex: 1, padding: '12px 0', overflowY: 'auto' }}>
                {NAV.map(({ to, icon: Icon, label }) => (
                    <NavLink key={to} to={to} end={to === '/'} style={{ textDecoration: 'none' }}>
                        {({ isActive }) => (
                            <div 
                                className={isActive ? 'nav-active' : ''} 
                                title={label} // Browser tooltip fallback
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 12,
                                    padding: '10px 20px', cursor: 'pointer',
                                    color: isActive ? 'var(--cyan)' : 'var(--text-secondary)',
                                    fontSize: 13, fontWeight: isActive ? 700 : 500,
                                    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                                    position: 'relative',
                                    background: isActive ? 'rgba(0, 229, 255, 0.08)' : 'transparent',
                                    margin: '2px 12px',
                                    borderRadius: 8,
                                }}
                                onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-primary)' }}
                                onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-secondary)' }}
                            >
                                {isActive && (
                                    <div style={{
                                        position: 'absolute',
                                        left: -12,
                                        width: 3,
                                        height: 18,
                                        background: 'var(--cyan)',
                                        borderRadius: '0 4px 4px 0',
                                        boxShadow: '0 0 10px var(--cyan)'
                                    }} />
                                )}
                                <Icon size={16} strokeWidth={isActive ? 2.5 : 1.5} />
                                <span style={{ transition: 'opacity 0.2s', opacity: 0.9 }}>{label}</span>
                            </div>
                        )}
                    </NavLink>
                ))}
            </nav>

            {/* Bot Status */}
            <div style={{
                padding: '16px 20px',
                borderTop: '1px solid var(--border)',
                display: 'flex', flexDirection: 'column', gap: 12,
            }}>
                {/* Status badge */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>BOT STATUS</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div className={botStatus === 'running' ? 'live-dot' : ''} style={{
                            width: 7, height: 7, borderRadius: '50%',
                            background: botStatus === 'running' ? 'var(--green)' : 'var(--text-dim)',
                        }} />
                        <span style={{
                            fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 700,
                            color: botStatus === 'running' ? 'var(--green)' : 'var(--text-dim)',
                        }}>
                            {botStatus === 'running' ? 'LIVE' : 'STOPPED'}
                        </span>
                    </div>
                </div>

                {/* Quick stats */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {[
                        { label: 'COINS ACTIVE', value: totalCoins.toLocaleString(), color: 'var(--cyan)', icon: Activity },
                        { label: 'LIVE SIGNALS', value: activeSignals, color: activeSignals > 0 ? 'var(--green)' : 'var(--text-dim)', icon: Zap },
                        { label: 'TODAY W/R', value: `${todayWinRate}%`, color: todayWinRate >= 50 ? 'var(--green)' : 'var(--red)', icon: TrendingUp },
                    ].map(({ label, value, color, icon: Icon }) => (
                        <div key={label} style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <Icon size={11} color="var(--text-dim)" />
                                <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>{label}</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700, color }}>{value}</span>
                                {label === 'TODAY W/R' && (
                                    todayWinRate >= 50 ? <TrendingUp size={10} color="var(--green)" /> : <TrendingDown size={10} color="var(--red)" />
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </aside>
    )
}
