import { useState } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'

function WinRateBadge({ value }) {
    const v = Number(value) || 0
    const color = v >= 65 ? 'var(--green)' : v >= 50 ? 'var(--yellow)' : 'var(--red)'
    const bg = v >= 65 ? 'rgba(0,230,118,0.12)' : v >= 50 ? 'rgba(255,214,0,0.12)' : 'rgba(255,23,68,0.12)'
    return (
        <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
            color, background: bg, padding: '2px 8px', borderRadius: 4,
        }}>
            {v.toFixed(1)}%
        </span>
    )
}

export default function CoinTable({ data = [], columns, onRowClick }) {
    const [sortKey, setSortKey] = useState(null)
    const [sortDir, setSortDir] = useState('desc')
    const [filter, setFilter] = useState('')

    const defaultColumns = [
        { key: 'symbol', label: 'Coin', render: (v) => <span style={{ color: 'var(--cyan)', fontWeight: 700 }}>{v}</span> },
        { key: 'best_strategy', label: 'Strategy' },
        { key: 'timeframe', label: 'TF', render: (v) => <span style={{ color: 'var(--text-dim)' }}>{v || '—'}</span> },
        { key: 'win_rate', label: 'Win Rate', render: (v) => <WinRateBadge value={v} /> },
        { key: 'total_trades', label: 'Trades' },
        {
            key: 'total_return', label: 'Return %', render: (v) => {
                const n = Number(v) || 0
                return <span style={{ color: n >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>{n >= 0 ? '+' : ''}{n.toFixed(2)}%</span>
            }
        },
        { key: 'max_drawdown', label: 'Drawdown', render: (v) => <span style={{ color: 'var(--red)' }}>{Number(v || 0).toFixed(2)}%</span> },
        { key: 'sharpe_ratio', label: 'Sharpe' },
    ]

    const cols = columns || defaultColumns

    const handleSort = (key) => {
        if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
        else { setSortKey(key); setSortDir('desc') }
    }

    const filtered = data.filter(row =>
        !filter || Object.values(row).some(v => String(v).toLowerCase().includes(filter.toLowerCase()))
    )

    const sorted = sortKey ? [...filtered].sort((a, b) => {
        const av = a[sortKey]; const bv = b[sortKey]
        const cmp = (av == null ? -Infinity : Number(av) || av) > (bv == null ? -Infinity : Number(bv) || bv) ? 1 : -1
        return sortDir === 'asc' ? cmp : -cmp
    }) : filtered

    const SortIcon = ({ col }) => {
        if (sortKey !== col) return <ChevronsUpDown size={10} color="var(--text-dim)" />
        return sortDir === 'asc' ? <ChevronUp size={10} color="var(--cyan)" /> : <ChevronDown size={10} color="var(--cyan)" />
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 0 }}>
            {/* Search */}
            <div style={{ padding: '8px 0 10px' }}>
                <input
                    className="cyber-input"
                    placeholder="Search coins, strategies..."
                    value={filter}
                    onChange={e => setFilter(e.target.value)}
                    style={{ maxWidth: 300 }}
                />
            </div>

            {/* Table */}
            <div style={{ flex: 1, overflowY: 'auto', overflowX: 'auto' }}>
                <table className="data-table">
                    <thead>
                        <tr>
                            {cols.map(col => (
                                <th key={col.key} onClick={() => handleSort(col.key)}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                        {col.label}
                                        <SortIcon col={col.key} />
                                    </div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {sorted.length === 0 ? (
                            <tr>
                                <td colSpan={cols.length} style={{ textAlign: 'center', padding: 32, color: 'var(--text-dim)' }}>
                                    No data available
                                </td>
                            </tr>
                        ) : (
                            sorted.map((row, i) => (
                                <tr
                                    key={row.id || i}
                                    onClick={() => onRowClick && onRowClick(row)}
                                    style={{ cursor: onRowClick ? 'pointer' : 'default' }}
                                >
                                    {cols.map(col => (
                                        <td key={col.key}>
                                            {col.render ? col.render(row[col.key], row) : (row[col.key] ?? '—')}
                                        </td>
                                    ))}
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
            <div style={{ paddingTop: 8, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)' }}>
                Showing {sorted.length} of {data.length} rows
            </div>
        </div>
    )
}
