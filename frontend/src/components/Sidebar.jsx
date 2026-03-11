import { NavLink } from 'react-router-dom'
import {
    LayoutDashboard, FlaskConical, BookOpen,
    History, Settings, Activity, Zap, TrendingUp, Filter
} from 'lucide-react'

const NAV = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/backtest', icon: FlaskConical, label: 'Backtests' },
    { to: '/strategies', icon: BookOpen, label: 'Strategies' },
    { to: '/screener', icon: Filter, label: 'Screener' },
    { to: '/signals', icon: History, label: 'Signals' },
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
                            <div className={isActive ? 'nav-active' : ''} style={{
                                display: 'flex', alignItems: 'center', gap: 12,
                                padding: '10px 20px', cursor: 'pointer',
                                color: isActive ? 'var(--cyan)' : 'var(--text-secondary)',
                                fontSize: 13, fontWeight: 500,
                                transition: 'all 0.15s',
                                borderRight: isActive ? '2px solid var(--cyan)' : '2px solid transparent',
                            }}
                                onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-primary)' }}
                                onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-secondary)' }}
                            >
                                <Icon size={16} strokeWidth={isActive ? 2.5 : 1.5} />
                                {label}
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
                        { label: 'COINS ACTIVE', value: totalCoins.toLocaleString(), icon: Activity },
                        { label: 'LIVE SIGNALS', value: activeSignals, icon: Zap },
                        { label: 'TODAY W/R', value: `${todayWinRate}%`, icon: TrendingUp },
                    ].map(({ label, value, icon: Icon }) => (
                        <div key={label} style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <Icon size={11} color="var(--text-dim)" />
                                <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>{label}</span>
                            </div>
                            <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--cyan)' }}>{value}</span>
                        </div>
                    ))}
                </div>
            </div>
        </aside>
    )
}
