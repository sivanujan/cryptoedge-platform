import { useEffect, useState } from 'react'
import { Wifi, WifiOff } from 'lucide-react'
import { useBackendStatus } from '../lib/useBackendStatus'

export default function TopBar({ btcPrice }) {
    const backendOnline = useBackendStatus()
    const [prevPrice, setPrevPrice] = useState(null)
    const [priceDir, setPriceDir] = useState(null) // 'up' | 'down'

    useEffect(() => {
        if (btcPrice?.last && prevPrice) {
            setPriceDir(btcPrice.last > prevPrice ? 'up' : btcPrice.last < prevPrice ? 'down' : null)
        }
        setPrevPrice(btcPrice?.last)
    }, [btcPrice?.last]) // eslint-disable-line

    const fmtPrice = (p) =>
        p ? `$${Number(p).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'

    const statusColor =
        backendOnline === null ? 'var(--yellow)' :
            backendOnline ? 'var(--green)' : 'var(--red)'

    const statusLabel =
        backendOnline === null ? 'CONNECTING' :
            backendOnline ? 'LIVE' : 'DISCONNECTED'

    return (
        <header style={{
            height: 56,
            background: 'var(--bg-secondary)',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
            flexShrink: 0,
            zIndex: 10,
        }}>
            {/* Left: page title */}
            <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: 13, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--cyan)' }} />
                LIVE MARKET TERMINAL
            </div>

            {/* Center: BTC live price with Change % */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div 
                    className={priceDir === 'up' ? 'flash-up' : priceDir === 'down' ? 'flash-down' : ''}
                    style={{
                        background: 'rgba(0,0,0,0.2)',
                        border: '1px solid var(--border)',
                        borderRadius: 10,
                        padding: '4px 12px',
                        display: 'flex', alignItems: 'center', gap: 10,
                        transition: 'all 0.3s ease'
                    }}
                >
                    <div style={{ position: 'relative' }}>
                        <img
                            src="https://assets.coingecko.com/coins/images/1/thumb/bitcoin.png"
                            alt="BTC"
                            width={18} height={18}
                            style={{ borderRadius: '50%', filter: 'drop-shadow(0 0 4px rgba(247, 147, 26, 0.4))' }}
                            onError={e => { e.target.style.display = 'none' }}
                        />
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-dim)', letterSpacing: '0.05em', fontWeight: 700 }}>BTC/USDT</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                            <span
                                key={btcPrice?.last}
                                style={{
                                    fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 800,
                                    color: priceDir === 'up' ? 'var(--green)' : priceDir === 'down' ? 'var(--red)' : 'var(--text-primary)',
                                    letterSpacing: '-0.01em',
                                    transition: 'color 0.4s',
                                }}
                            >
                                {fmtPrice(btcPrice?.last)}
                            </span>
                            
                            {btcPrice?.percentage !== undefined && (
                                <span style={{
                                    fontSize: 11,
                                    fontWeight: 900,
                                    color: btcPrice.percentage >= 0 ? 'var(--green)' : 'var(--red)',
                                    background: btcPrice.percentage >= 0 ? 'rgba(0, 230, 118, 0.1)' : 'rgba(255, 23, 68, 0.1)',
                                    padding: '1px 6px',
                                    borderRadius: 4,
                                    letterSpacing: '0.02em'
                                }}>
                                    {btcPrice.percentage >= 0 ? '+' : ''}{btcPrice.percentage.toFixed(2)}%
                                </span>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Right: backend connection status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {backendOnline ? (
                    <div className="live-dot" />
                ) : (
                    <div style={{
                        width: 7, height: 7, borderRadius: '50%',
                        background: statusColor,
                        animation: backendOnline === null ? 'pulse-dot 1s ease-in-out infinite' : 'none',
                    }} />
                )}
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, color: statusColor, letterSpacing: '0.08em' }}>
                    {statusLabel}
                </span>
                {backendOnline
                    ? <Wifi size={13} color={statusColor} />
                    : <WifiOff size={13} color={statusColor} />}
            </div>
        </header>
    )
}
