import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { TrendingUp, TrendingDown, Activity, Zap, Target, BarChart3, Clock, AlertTriangle, ChevronDown, ChevronUp, RefreshCw, ExternalLink } from 'lucide-react'
import { API } from '../lib/api'
import LoadingSpinner from '../components/LoadingSpinner'

export default function FuturesAnalysis() {
    const [timeframe, setTimeframe] = useState('1h')
    const [minVolume, setMinVolume] = useState(10000000)
    const [expandedSymbol, setExpandedSymbol] = useState(null)

    const { data, isLoading, error, refetch, isFetching } = useQuery({
        queryKey: ['futuresLongShort', timeframe, minVolume],
        queryFn: () => API.getFuturesLongShort({ timeframe, min_volume: minVolume }),
        staleTime: 120000, // 2 minutes
        retry: 1,
    })

    const formatPrice = (price) => {
        if (!price) return '-'
        if (price >= 1000) return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
        if (price >= 1) return `$${price.toFixed(2)}`
        return `$${price.toFixed(6)}`
    }

    const formatVolume = (vol) => {
        if (!vol) return '-'
        if (vol >= 1e9) return `$${(vol / 1e9).toFixed(2)}B`
        if (vol >= 1e6) return `$${(vol / 1e6).toFixed(2)}M`
        return `$${(vol / 1e3).toFixed(0)}K`
    }

    const getSignalColor = (signal) => {
        if (signal?.includes('RETEST')) return 'var(--cyan)'
        if (signal?.includes('MOMENTUM')) return 'var(--purple)'
        if (signal?.includes('LONG')) return 'var(--green)'
        if (signal?.includes('SHORT')) return 'var(--red)'
        return 'var(--text-dim)'
    }

    const getSignalBg = (signal) => {
        if (signal?.includes('RETEST')) return 'rgba(0,229,255,0.15)'
        if (signal?.includes('MOMENTUM')) return 'rgba(138,43,226,0.15)'
        if (signal?.includes('LONG')) return 'rgba(0,230,118,0.1)'
        if (signal?.includes('SHORT')) return 'rgba(255,23,68,0.1)'
        return 'rgba(255,255,255,0.05)'
    }

    const getRsiColor = (rsi) => {
        if (rsi > 70) return 'var(--red)'
        if (rsi < 30) return 'var(--green)'
        return 'var(--text-dim)'
    }

    const toggleExpand = (symbol) => {
        setExpandedSymbol(expandedSymbol === symbol ? null : symbol)
    }

    const renderSymbolCard = (item, type) => {
        const tech = item.technical || {}
        const breakout = item.breakout || null
        const isExpanded = expandedSymbol === item.symbol

        return (
            <div
                key={item.symbol}
                className={`card ${type === 'long' ? 'accent-border-long' : 'accent-border-short'}`}
                style={{
                    padding: '16px',
                    cursor: 'pointer',
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    position: 'relative',
                    overflow: 'hidden',
                    background: 'var(--bg-card)',
                }}
                onClick={(e) => {
                    if (e.target.closest('.hover-actions')) return;
                    toggleExpand(item.symbol);
                }}
            >
                {/* Entry Quality Badge */}
                {item.entry_quality === 'STRONG' && (
                    <div style={{
                        position: 'absolute',
                        top: 0,
                        right: 0,
                        background: 'var(--cyan)',
                        color: '#000',
                        fontSize: 9,
                        fontWeight: 900,
                        padding: '2px 8px',
                        borderBottomLeftRadius: 8,
                        letterSpacing: '0.05em'
                    }}>
                        STRONG RETEST
                    </div>
                )}

                {/* Header Row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        {type === 'long' ? (
                            <TrendingUp size={20} color="var(--green)" />
                        ) : (
                            <TrendingDown size={20} color="var(--red)" />
                        )}
                        <div>
                            <div style={{ fontWeight: 800, fontSize: 16, letterSpacing: '-0.01em' }}>{item.symbol.replace('USDT', '')}</div>
                            <div style={{ fontSize: 10, color: 'var(--text-dim)', background: 'rgba(255,255,255,0.05)', padding: '1px 6px', borderRadius: 4, display: 'inline-block', fontWeight: 600 }}>
                                VOL: {formatVolume(item.volume_24h)}
                            </div>
                        </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                        <div style={{
                            fontSize: 16,
                            fontWeight: 900,
                            padding: '4px 10px',
                            borderRadius: 8,
                            background: item.change_24h > 0 ? 'rgba(0,230,118,0.1)' : 'rgba(255,23,68,0.1)',
                            color: item.change_24h > 0 ? 'var(--green)' : 'var(--red)',
                            marginBottom: 2
                        }}>
                            {item.change_24h > 0 ? '+' : ''}{item.change_24h?.toFixed(2)}%
                        </div>
                        <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', opacity: 0.8 }}>
                            {formatPrice(item.price)}
                        </div>
                    </div>
                </div>

                {/* Quick Stats Row with Skeleton Loaders */}
                <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                    <div style={{ flex: 1, padding: '6px 8px', background: 'rgba(0,0,0,0.2)', borderRadius: 8, textAlign: 'center', border: '1px solid rgba(255,255,255,0.05)' }}>
                        <div style={{ fontSize: 9, color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>RSI</div>
                        {tech.rsi ? (
                            <div className="badge" style={{ 
                                marginTop: 4,
                                background: tech.rsi > 60 ? 'rgba(0,230,118,0.15)' : tech.rsi < 40 ? 'rgba(255,23,68,0.15)' : 'rgba(255,255,255,0.08)',
                                color: tech.rsi > 60 ? 'var(--green)' : tech.rsi < 40 ? 'var(--red)' : 'var(--text-secondary)',
                                fontSize: 12,
                                border: 'none',
                                width: '100%',
                                justifyContent: 'center'
                            }}>
                                {tech.rsi.toFixed(1)}
                            </div>
                        ) : (
                            <div className="skeleton" style={{ height: 18, marginTop: 4, width: '100%' }}></div>
                        )}
                    </div>
                    <div style={{ flex: 1, padding: '6px 8px', background: 'rgba(0,0,0,0.2)', borderRadius: 8, textAlign: 'center', border: '1px solid rgba(255,255,255,0.05)' }}>
                        <div style={{ fontSize: 9, color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>Vol Multi</div>
                        {tech.vol_ratio ? (
                            <div style={{ fontSize: 13, fontWeight: 800, color: tech.vol_ratio > 1.5 ? 'var(--cyan)' : 'var(--text-primary)', marginTop: 4 }}>
                                {tech.vol_ratio}x
                            </div>
                        ) : (
                            <div className="skeleton" style={{ height: 18, marginTop: 4, width: '100%' }}></div>
                        )}
                    </div>
                    <div style={{ flex: '1.5', padding: '6px 8px', background: getSignalBg(item.entry_signal), borderRadius: 8, textAlign: 'center', border: `1px solid ${getSignalColor(item.entry_signal)}44` }}>
                        <div style={{ fontSize: 9, color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>Entry Price</div>
                        {item.technical ? (
                            <div style={{ fontSize: 12, fontWeight: 900, color: getSignalColor(item.entry_signal), marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                                {breakout ? formatPrice(breakout.price) : formatPrice(item.price)}
                            </div>
                        ) : (
                            <div className="skeleton" style={{ height: 18, marginTop: 4, width: '100%' }}></div>
                        )}
                    </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                    <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                        {/* Advanced Ticker Data (Always show) */}
                        <div style={{ padding: 12, background: 'rgba(0,184,212,0.05)', borderRadius: 8, border: '1px solid rgba(0,184,212,0.1)', marginBottom: 12 }}>
                            <div style={{ fontSize: 10, color: 'var(--cyan)', fontWeight: 800, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: 6 }}>
                                <Zap size={12} /> Advanced Ticker Data
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                                <div>
                                    <div style={{ fontSize: 9, color: 'var(--text-dim)' }}>24H HIGH</div>
                                    <div style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{formatPrice(item.high_24h)}</div>
                                </div>
                                <div>
                                    <div style={{ fontSize: 9, color: 'var(--text-dim)' }}>24H LOW</div>
                                    <div style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{formatPrice(item.low_24h)}</div>
                                </div>
                                <div>
                                    <div style={{ fontSize: 9, color: 'var(--text-dim)' }}>QUOTE VOLUME</div>
                                    <div style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{formatVolume(item.volume_24h)}</div>
                                </div>
                            </div>
                        </div>

                        {tech && Object.keys(tech).length > 0 ? (
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                {/* Technicals */}
                                <div style={{ padding: 12, background: 'rgba(0,0,0,0.3)', borderRadius: 8, border: '1px solid rgba(255,255,255,0.03)' }}>
                                    <div style={{ fontSize: 10, color: 'var(--cyan)', fontWeight: 800, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Moving Averages</div>
                                    <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                                        <span style={{ color: 'var(--text-dim)' }}>EMA 21</span>
                                        <span style={{ fontFamily: 'var(--font-mono)' }}>{formatPrice(tech.ema_21)}</span>
                                    </div>
                                    <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between' }}>
                                        <span style={{ color: 'var(--text-dim)' }}>EMA 50</span>
                                        <span style={{ fontFamily: 'var(--font-mono)' }}>{formatPrice(tech.ema_50)}</span>
                                    </div>
                                </div>

                                {/* Volatility */}
                                <div style={{ padding: 12, background: 'rgba(0,0,0,0.3)', borderRadius: 8, border: '1px solid rgba(255,255,255,0.03)' }}>
                                    <div style={{ fontSize: 10, color: 'var(--purple)', fontWeight: 800, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Volatility</div>
                                    <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                                        <span style={{ color: 'var(--text-dim)' }}>ATR %</span>
                                        <span style={{ fontWeight: 700 }}>{item.volatility_pct || '-'}%</span>
                                    </div>
                                    <div style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between' }}>
                                        <span style={{ color: 'var(--text-dim)' }}>BB State</span>
                                        <span style={{ fontWeight: 700, color: item.bb_position === 'INSIDE' ? 'var(--text-dim)' : 'var(--yellow)' }}>{item.bb_position || 'UNKNOWN'}</span>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div style={{ padding: 16, textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: 8, color: 'var(--text-dim)', fontSize: 12 }}>
                                Detailed Technical Analysis Unavailable for this timeframe
                            </div>
                        )}

                        {/* Recommendation */}
                        {breakout && (
                            <div style={{ marginTop: 12, padding: 12, background: getSignalBg(item.entry_signal), borderRadius: 8, border: `1px solid ${getSignalColor(item.entry_signal)}33` }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                    <Target size={14} color={getSignalColor(item.entry_signal)} />
                                    <span style={{ fontSize: 11, fontWeight: 800, color: getSignalColor(item.entry_signal) }}>ANALYSIS REPORT</span>
                                </div>
                                <p style={{ margin: 0, fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.4 }}>
                                    {item.entry_signal?.includes('RETEST') 
                                        ? `Price is currently retesting the previous breakout level at ${formatPrice(breakout.price)}. This is a high-probability entry point if the level holds.`
                                        : item.entry_signal?.includes('MOMENTUM')
                                        ? `Momentum is strong following a breakout ${breakout.age} candles ago. Current price offers secondary entry for trend followers.`
                                        : `Found breakout at ${formatPrice(breakout.price)}, but price has diverged. Wait for a retest or new structure.`}
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {/* Hover Actions Button Row */}
                {!isExpanded && (
                    <div className="hover-actions" style={{
                        display: 'flex',
                        gap: 8,
                        marginTop: 4,
                        paddingTop: 8,
                        borderTop: '1px solid rgba(255,255,255,0.05)'
                    }}>
                        <a
                            href={`/deep-analysis?coin=${item.symbol.split(':')[0].replace('/USDT', '')}`}
                            className="btn"
                            style={{
                                flex: 1,
                                padding: '6px 0',
                                fontSize: 11,
                                fontWeight: 800,
                                background: 'rgba(0,229,255,0.1)',
                                color: 'var(--cyan)',
                                border: '1px solid rgba(0,229,255,0.2)',
                                borderRadius: 6,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: 4,
                                textDecoration: 'none',
                            }}
                            onClick={e => e.stopPropagation()}
                        >
                            <Activity size={12} /> Deep Analysis
                        </a>
                        <a
                            href={`https://www.tradingview.com/chart/?symbol=BINANCE:${item.symbol.split(':')[0].replace('/', '')}.P`}
                            target="_blank"
                            rel="noreferrer"
                            className="btn"
                            style={{
                                padding: '6px 12px',
                                background: 'rgba(255,255,255,0.05)',
                                color: 'var(--text-dim)',
                                borderRadius: 6,
                                border: '1px solid rgba(255,255,255,0.08)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 4,
                                textDecoration: 'none',
                            }}
                            onClick={e => e.stopPropagation()}
                        >
                            <ExternalLink size={12} /> TV
                        </a>
                    </div>
                )}

                {/* Status indicator on bottom when not expanded */}
                {!isExpanded && (
                    <div style={{ textAlign: 'center', marginTop: 8, color: 'var(--text-dim)', fontSize: 9, opacity: 0.5, letterSpacing: '0.05em' }}>
                        CLICK TO EXPAND DETAILS
                    </div>
                )}
                {isExpanded && (
                    <div style={{ textAlign: 'center', marginTop: 12, color: 'var(--text-dim)', fontSize: 9, opacity: 0.5, letterSpacing: '0.05em' }}>
                         CLICK TO COLLAPSE
                    </div>
                )}
            </div>
        )
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Header */}
            <div className="card" style={{ padding: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
                    <div>
                        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
                            <Activity size={28} color="var(--cyan)" />
                            Futures Long/Short Analysis
                        </h1>
                        <p style={{ color: 'var(--text-dim)', margin: '8px 0 0 0', fontSize: 13 }}>
                            Top gainers (longs) and losers (shorts) from Binance Futures with technical analysis
                        </p>
                    </div>

                    <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                        {/* Timeframe Selector */}
                        <div style={{ display: 'flex', gap: 4, background: 'rgba(0,0,0,0.2)', padding: 4, borderRadius: 8 }}>
                            {['15m', '1h', '4h'].map((tf) => (
                                <button
                                    key={tf}
                                    onClick={() => setTimeframe(tf)}
                                    className="btn"
                                    style={{
                                        padding: '8px 16px',
                                        fontSize: 12,
                                        fontWeight: 600,
                                        background: timeframe === tf ? 'var(--cyan)' : 'transparent',
                                        color: timeframe === tf ? '#000' : 'var(--text-secondary)',
                                        border: 'none',
                                    }}
                                >
                                    {tf}
                                </button>
                            ))}
                        </div>

                        {/* Refresh Button */}
                        <button
                            onClick={() => refetch()}
                            className="btn"
                            style={{
                                padding: '10px 16px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                background: 'rgba(0,229,255,0.1)',
                                border: '1px solid var(--cyan)',
                            }}
                            disabled={isFetching}
                        >
                            <RefreshCw size={16} style={isFetching ? { animation: 'spin 0.8s linear infinite' } : {}} />
                            {isFetching ? 'Refreshing...' : 'Refresh'}
                        </button>
                    </div>
                </div>

                {/* Unified Filter Bar */}
                <div style={{ 
                    marginTop: 20, 
                    padding: '8px 16px', 
                    background: 'rgba(0,0,0,0.25)', 
                    borderRadius: 12, 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: 0,
                    border: '1px solid rgba(255,255,255,0.03)',
                    transition: 'all 0.3s ease'
                }}>
                    {/* Timeframe Group */}
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', paddingRight: 20 }}>
                        <Clock size={14} color="var(--text-dim)" />
                        <div style={{ display: 'flex', gap: 4, background: 'rgba(255,255,255,0.03)', padding: 3, borderRadius: 8 }}>
                            {['15m', '1h', '4h'].map((tf) => (
                                <button
                                    key={tf}
                                    onClick={() => setTimeframe(tf)}
                                    className="btn"
                                    style={{
                                        padding: '6px 14px',
                                        fontSize: 11,
                                        fontWeight: 700,
                                        background: timeframe === tf ? 'var(--cyan)' : 'transparent',
                                        color: timeframe === tf ? '#000' : 'var(--text-secondary)',
                                        border: 'none',
                                        transition: 'all 0.2s ease'
                                    }}
                                >
                                    {tf}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Vertical Divider */}
                    <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.1)', margin: '0 4px' }} />

                    {/* Volume Filter Group */}
                    <div style={{ display: 'flex', gap: 12, alignItems: 'center', paddingLeft: 20, flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <BarChart3 size={14} color="var(--text-dim)" />
                            <span style={{ fontSize: 11, color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>Min 24h Vol:</span>
                        </div>
                        <div style={{ display: 'flex', gap: 6 }}>
                            {[5000000, 10000000, 50000000, 100000000].map((vol) => (
                                <button
                                    key={vol}
                                    onClick={() => setMinVolume(vol)}
                                    className="btn"
                                    style={{
                                        padding: '5px 12px',
                                        fontSize: 11,
                                        fontFamily: 'var(--font-mono)',
                                        background: minVolume === vol ? 'rgba(0,229,255,0.15)' : 'transparent',
                                        color: minVolume === vol ? 'var(--cyan)' : 'var(--text-dim)',
                                        border: minVolume === vol ? '1px solid var(--cyan)' : '1px solid transparent',
                                        borderRadius: 6,
                                        fontWeight: minVolume === vol ? 800 : 500,
                                        transition: 'all 0.2s ease'
                                    }}
                                >
                                    {vol >= 1e9 ? `${vol/1e9}B` : `${vol/1e6}M`}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Loading State */}
            {isLoading && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20, padding: 60 }}>
                    <LoadingSpinner size={48} />
                    <div style={{ textAlign: 'center' }}>
                        <p style={{ fontSize: 18, fontWeight: 700 }}>Fetching Futures Data...</p>
                        <p style={{ color: 'var(--text-dim)', fontSize: 14 }}>Getting top gainers/losers from Binance and running technical analysis</p>
                    </div>
                </div>
            )}

            {/* Error State */}
            {error && (
                <div className="card" style={{ padding: 40, border: '1px solid var(--red)', textAlign: 'center' }}>
                    <AlertTriangle size={40} color="var(--red)" style={{ marginBottom: 16 }} />
                    <h3 style={{ fontSize: 18, fontWeight: 700 }}>Failed to Load Data</h3>
                    <p style={{ color: 'var(--text-dim)' }}>{error.message || "Could not fetch futures data. Please try again."}</p>
                    <button onClick={() => refetch()} className="btn-primary" style={{ marginTop: 16 }}>Retry</button>
                </div>
            )}

            {/* Data Display */}
            {data && !isLoading && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                    {/* Longs (Gainers) Column */}
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                            <TrendingUp size={24} color="var(--green)" />
                            <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--green)' }}>Top Longs (Gainers)</h2>
                            <span style={{ marginLeft: 'auto', padding: '4px 12px', background: 'rgba(0,230,118,0.15)', borderRadius: 20, fontSize: 12, fontWeight: 700, color: 'var(--green)' }}>
                                {data.count?.longs || 0} coins
                            </span>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            {data.longs?.map((item) => renderSymbolCard(item, 'long'))}
                            {(!data.longs || data.longs.length === 0) && (
                                <div className="card" style={{ padding: 40, textAlign: 'center', opacity: 0.6 }}>
                                    <TrendingUp size={32} color="var(--text-dim)" style={{ marginBottom: 8 }} />
                                    <p style={{ color: 'var(--text-dim)' }}>No long positions found</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Shorts (Losers) Column */}
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                            <TrendingDown size={24} color="var(--red)" />
                            <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--red)' }}>Top Shorts (Losers)</h2>
                            <span style={{ marginLeft: 'auto', padding: '4px 12px', background: 'rgba(255,23,68,0.15)', borderRadius: 20, fontSize: 12, fontWeight: 700, color: 'var(--red)' }}>
                                {data.count?.shorts || 0} coins
                            </span>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            {data.shorts?.map((item) => renderSymbolCard(item, 'short'))}
                            {(!data.shorts || data.shorts.length === 0) && (
                                <div className="card" style={{ padding: 40, textAlign: 'center', opacity: 0.6 }}>
                                    <TrendingDown size={32} color="var(--text-dim)" style={{ marginBottom: 8 }} />
                                    <p style={{ color: 'var(--text-dim)' }}>No short positions found</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Timestamp */}
            {data?.timestamp && (
                <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontSize: 11, padding: '20px 0' }}>
                    Last updated: {new Date(data.timestamp).toLocaleString()} • Data from Binance Futures
                </div>
            )}
        </div>
    )
}