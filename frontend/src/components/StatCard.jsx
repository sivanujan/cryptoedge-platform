import { TrendingUp, TrendingDown } from 'lucide-react'

export default function StatCard({ label, value, sub, icon: Icon, color = 'cyan', delta }) {
    const colorMap = {
        cyan: { main: 'var(--cyan)', glow: 'var(--cyan-glow)', bg: 'rgba(0,229,255,0.06)' },
        green: { main: 'var(--green)', glow: 'var(--green-glow)', bg: 'rgba(0,230,118,0.06)' },
        red: { main: 'var(--red)', glow: 'var(--red-glow)', bg: 'rgba(255,23,68,0.06)' },
        yellow: { main: 'var(--yellow)', glow: 'rgba(255,214,0,0.15)', bg: 'rgba(255,214,0,0.05)' },
        purple: { main: 'var(--purple)', glow: 'rgba(124,77,255,0.2)', bg: 'rgba(124,77,255,0.06)' },
    }
    const c = colorMap[color] || colorMap.cyan

    return (
        <div className="card" style={{
            padding: '16px 18px',
            display: 'flex', flexDirection: 'column', gap: 10,
            background: 'var(--bg-card)',
            position: 'relative', overflow: 'hidden',
            flex: 1,
        }}>
            {/* BG glow */}
            <div style={{
                position: 'absolute', top: 0, right: 0,
                width: 80, height: 80,
                background: c.glow,
                borderRadius: '50%',
                filter: 'blur(25px)',
                pointerEvents: 'none',
            }} />

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                    color: 'var(--text-dim)', letterSpacing: '0.1em', textTransform: 'uppercase',
                }}>
                    {label}
                </span>
                {Icon && (
                    <div style={{
                        padding: 6, borderRadius: 8, background: c.bg,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <Icon size={14} color={c.main} />
                    </div>
                )}
            </div>

            {/* Value */}
            <div>
                {value === null ? (
                    // Loading skeleton
                    <div style={{
                        height: 28, width: '60%', borderRadius: 6,
                        background: 'linear-gradient(90deg, var(--bg-secondary) 25%, var(--bg-hover) 50%, var(--bg-secondary) 75%)',
                        backgroundSize: '200% 100%',
                        animation: 'shimmer 1.5s infinite',
                        marginBottom: 6,
                    }} />
                ) : (
                    <div key={String(value)} style={{
                        fontFamily: 'var(--font-mono)', fontSize: 24, fontWeight: 700,
                        color: c.main, letterSpacing: '-0.02em',
                        animation: 'number-tick 0.3s ease',
                    }}>
                        {value ?? '—'}
                    </div>
                )}
                {sub && (
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                        {sub}
                    </div>
                )}
            </div>

            {/* Delta */}
            {delta !== undefined && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    {delta >= 0
                        ? <TrendingUp size={12} color="var(--green)" />
                        : <TrendingDown size={12} color="var(--red)" />
                    }
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: delta >= 0 ? 'var(--green)' : 'var(--red)' }}>
                        {delta >= 0 ? '+' : ''}{delta}%
                    </span>
                </div>
            )}
        </div>
    )
}
