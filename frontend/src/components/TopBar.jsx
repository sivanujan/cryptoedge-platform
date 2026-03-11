import { useEffect, useState } from 'react'
import { Wifi, WifiOff } from 'lucide-react'
import { useBackendStatus } from '../lib/useBackendStatus'

export default function TopBar({ btcPrice }) {
    const backendOnline = useBackendStatus()
    const [prevPrice, setPrevPrice] = useState(null)
    const [priceDir, setPriceDir] = useState(null) // 'up' | 'down'

    useEffect(() => {
        if (btcPrice && prevPrice) {
            setPriceDir(btcPrice > prevPrice ? 'up' : btcPrice < prevPrice ? 'down' : null)
        }
        setPrevPrice(btcPrice)
    }, [btcPrice]) // eslint-disable-line

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
            <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: 14, color: 'var(--text-secondary)' }}>
                Live Market Terminal
            </div>

            {/* Center: BTC live price */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                    background: 'rgba(0,229,255,0.06)',
                    border: '1px solid rgba(0,229,255,0.15)',
                    borderRadius: 8,
                    padding: '4px 16px',
                    display: 'flex', alignItems: 'center', gap: 8,
                }}>
                    <img
                        src="https://assets.coingecko.com/coins/images/1/thumb/bitcoin.png"
                        alt="BTC"
                        width={16} height={16}
                        style={{ borderRadius: '50%' }}
                        onError={e => { e.target.style.display = 'none' }}
                    />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', letterSpacing: '0.05em' }}>BTC/USDT</span>
                    <span
                        key={btcPrice}
                        style={{
                            fontFamily: 'var(--font-mono)', fontSize: 15, fontWeight: 700,
                            color: priceDir === 'up' ? 'var(--green)' : priceDir === 'down' ? 'var(--red)' : 'var(--cyan)',
                            letterSpacing: '-0.01em',
                            animation: btcPrice ? 'number-tick 0.3s ease' : 'none',
                            transition: 'color 0.5s',
                        }}
                    >
                        {fmtPrice(btcPrice)}
                    </span>
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
