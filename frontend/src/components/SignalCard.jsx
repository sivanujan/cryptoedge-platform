import { ArrowUpRight, ArrowDownRight, Shield, Target, TrendingUp, Cpu } from 'lucide-react'

export default function SignalCard({ signal }) {
    const {
        symbol = '—',
        strategy = '—',
        signal_type = 'BUY',
        entry_price = 0,
        stop_loss,
        take_profit,
        confidence = 0,
        timeframe = '1h',
        created_at,
    } = signal || {}

    const isBuy = signal_type === 'BUY'
    const mainColor = isBuy ? 'var(--green)' : 'var(--red)'
    const bgColor = isBuy ? 'rgba(0,230,118,0.05)' : 'rgba(255,23,68,0.05)'
    const borderColor = isBuy ? 'rgba(0,230,118,0.2)' : 'rgba(255,23,68,0.2)'

    const fmt = (n) => n ? `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 })}` : '—'
    const timeAgo = (dt) => {
        if (!dt) return ''
        const diff = Math.floor((Date.now() - new Date(dt).getTime()) / 60000)
        if (diff < 1) return 'just now'
        if (diff < 60) return `${diff}m ago`
        return `${Math.floor(diff / 60)}h ago`
    }

    return (
        <div style={{
            background: bgColor,
            border: `1px solid ${borderColor}`,
            borderRadius: 10,
            padding: '12px 14px',
            display: 'flex', flexDirection: 'column', gap: 8,
            transition: 'transform 0.15s, box-shadow 0.15s',
            cursor: 'default',
        }}
            onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = `0 4px 20px ${isBuy ? 'var(--green-glow)' : 'var(--red-glow)'}` }}
            onMouseLeave={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = 'none' }}
        >
            {/* Header row */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {isBuy
                        ? <ArrowUpRight size={14} color="var(--green)" />
                        : <ArrowDownRight size={14} color="var(--red)" />
                    }
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                        {symbol}
                    </span>
                    <span className={isBuy ? 'badge badge-buy' : 'badge badge-sell'}>
                        {signal_type}
                    </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)' }}>{timeAgo(created_at)}</span>
                    <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 10,
                        background: 'rgba(0,229,255,0.08)', color: 'var(--cyan)',
                        padding: '1px 5px', borderRadius: 3,
                    }}>{timeframe}</span>
                </div>
            </div>

            {/* Strategy */}
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)' }}>
                {strategy}
            </div>

            {/* Price data */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                {[
                    { label: 'ENTRY', value: fmt(entry_price), icon: TrendingUp },
                    { label: 'SL', value: fmt(stop_loss), icon: Shield, color: 'var(--red)' },
                    { label: 'TP', value: fmt(take_profit), icon: Target, color: 'var(--green)' },
                ].map(({ label, value, icon: Icon, color = 'var(--text-secondary)' }) => (
                    <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                            <Icon size={8} color={color} />
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)', letterSpacing: '0.06em' }}>{label}</span>
                        </div>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color, fontWeight: 700 }}>{value}</span>
                    </div>
                ))}
            </div>

            {/* AI Score (Small badge) */}
            {(signal.ai_score !== undefined && signal.ai_score !== null) && (
                <div style={{ 
                    display: 'flex', alignItems: 'center', gap: 6, 
                    padding: '4px 8px', background: 'rgba(0,229,255,0.05)', 
                    borderRadius: 6, border: '1px solid rgba(0,229,255,0.1)'
                }}>
                    <Cpu size={12} color="var(--cyan)" />
                    <span style={{ fontSize: 10, fontWeight: 800, color: 'var(--cyan)', letterSpacing: '0.04em' }}>
                        AI AGENT: {signal.ai_score}/100
                    </span>
                    <span style={{ fontSize: 9, color: 'var(--text-dim)', fontStyle: 'italic', marginLeft: 'auto' }}>
                        {signal.ai_score >= 70 ? 'Strong' : signal.ai_score >= 50 ? 'Neutral' : 'Weak'}
                    </span>
                </div>
            )}
        </div>
    )
}
