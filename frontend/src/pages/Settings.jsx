import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Save, RefreshCw, CheckCircle } from 'lucide-react'
import { API } from '../lib/api'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'

function SettingRow({ label, sub, children }) {
    return (
        <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 0', borderBottom: '1px solid var(--border)',
        }}>
            <div>
                <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{label}</div>
                {sub && <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)', marginTop: 2 }}>{sub}</div>}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {children}
            </div>
        </div>
    )
}

export default function Settings() {
    const [form, setForm] = useState({})
    const [dirty, setDirty] = useState(false)

    const { data: settings, isLoading, refetch } = useQuery({
        queryKey: ['settings'],
        queryFn: API.getSettings,
    })

    useEffect(() => {
        if (settings) setForm(settings)
    }, [settings])

    const { mutateAsync: saveSettings, isPending: saving } = useMutation({
        mutationFn: API.saveSettings,
        onSuccess: () => {
            toast.success('Settings saved!')
            setDirty(false)
            refetch()
        },
        onError: () => toast.error('Failed to save settings'),
    })

    const set = (key, val) => {
        setForm(f => ({ ...f, [key]: val }))
        setDirty(true)
    }

    const handleSave = async () => {
        const payload = { ...form }
        await saveSettings(payload)
    }

    const handleSyncCoins = async () => {
        try {
            const res = await API.syncCoins()
            toast.success(`Synced! Added ${res.added} new coins (${res.synced} total)`)
        } catch {
            toast.error('Coin sync failed. Check Binance connection.')
        }
    }

    if (isLoading) return <LoadingSpinner text="Loading settings..." />

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 14, overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
                <div>
                    <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 20, color: 'var(--text-primary)' }}>Settings</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>Platform configuration</div>
                </div>
                <button
                    className="btn-primary"
                    onClick={handleSave}
                    disabled={saving || !dirty}
                    style={{ opacity: !dirty ? 0.5 : 1, display: 'flex', alignItems: 'center', gap: 6 }}
                >
                    <Save size={13} />{saving ? 'Saving...' : 'Save Changes'}
                </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', paddingBottom: 24 }}>
                {/* API Keys — loaded from .env, not editable in UI */}
                <div className="card" style={{ padding: '4px 20px' }}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--cyan)', letterSpacing: '0.1em', padding: '14px 0 2px' }}>BINANCE API</div>
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 12,
                        padding: '14px 0',
                        borderBottom: '1px solid var(--border)',
                    }}>
                        <CheckCircle size={16} color="var(--green)" />
                        <div>
                            <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>
                                API keys loaded from <code style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'var(--bg-secondary)', padding: '1px 6px', borderRadius: 4, color: 'var(--cyan)' }}>backend/.env</code>
                            </div>
                            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)', marginTop: 4 }}>
                                BINANCE_API_KEY and BINANCE_SECRET_KEY are read directly from the environment file.
                                Edit <code style={{ color: 'var(--cyan)' }}>backend/.env</code> to change them.
                            </div>
                        </div>
                    </div>
                </div>

                {/* Scanner */}
                <div className="card" style={{ padding: '4px 20px' }}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--cyan)', letterSpacing: '0.1em', padding: '14px 0 2px' }}>SCANNER</div>
                    <SettingRow label="Scan Interval" sub="How often to check for signals">
                        <select className="cyber-input" value={form.scanner_interval_minutes || '15'} onChange={e => set('scanner_interval_minutes', e.target.value)} style={{ width: 120 }}>
                            <option value="5">5 minutes</option>
                            <option value="15">15 minutes</option>
                            <option value="60">1 hour</option>
                        </select>
                    </SettingRow>
                    <SettingRow label="Sync Coin List" sub="Fetch all USDT pairs from Binance">
                        <button className="btn-ghost" onClick={handleSyncCoins} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <RefreshCw size={13} />Sync Now
                        </button>
                    </SettingRow>
                </div>

                {/* Risk */}
                <div className="card" style={{ padding: '4px 20px' }}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--cyan)', letterSpacing: '0.1em', padding: '14px 0 2px' }}>RISK MANAGEMENT</div>
                    {[
                        { key: 'risk_per_trade_pct', label: 'Risk Per Trade', sub: 'Percentage of capital to risk per trade', suffix: '%' },
                        { key: 'default_sl_pct', label: 'Default Stop Loss', sub: 'Stop loss % from entry price', suffix: '%' },
                        { key: 'default_tp_pct', label: 'Default Take Profit', sub: 'Take profit % from entry price', suffix: '%' },
                    ].map(({ key, label, sub, suffix }) => (
                        <SettingRow key={key} label={label} sub={sub}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                <input
                                    className="cyber-input" type="number" step="0.5" min="0.5" max="100"
                                    value={form[key] || ''}
                                    onChange={e => set(key, e.target.value)}
                                    style={{ width: 80, textAlign: 'right' }}
                                />
                                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-dim)' }}>{suffix}</span>
                            </div>
                        </SettingRow>
                    ))}
                </div>

                {/* Notifications */}
                <div className="card" style={{ padding: '4px 20px' }}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--cyan)', letterSpacing: '0.1em', padding: '14px 0 2px' }}>NOTIFICATIONS</div>
                    {[
                        { key: 'notify_browser', label: 'Browser Notifications', sub: 'Show desktop notification on new signal' },
                        { key: 'notify_telegram', label: 'Telegram Bot', sub: 'Send signals to your Telegram bot' },
                    ].map(({ key, label, sub }) => (
                        <SettingRow key={key} label={label} sub={sub}>
                            <div
                                onClick={() => set(key, form[key] === 'true' ? 'false' : 'true')}
                                style={{
                                    width: 40, height: 22, borderRadius: 11,
                                    background: form[key] === 'true' ? 'var(--cyan-dim)' : 'var(--border)',
                                    position: 'relative', cursor: 'pointer', transition: 'background 0.2s',
                                }}
                            >
                                <div style={{
                                    position: 'absolute', top: 3,
                                    left: form[key] === 'true' ? 20 : 3,
                                    width: 16, height: 16,
                                    background: '#fff', borderRadius: '50%',
                                    transition: 'left 0.2s',
                                    boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
                                }} />
                            </div>
                        </SettingRow>
                    ))}
                </div>
            </div>
        </div>
    )
}
