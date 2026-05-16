import React, { useState, useEffect } from 'react';
import { 
    Zap, Activity, TrendingUp, TrendingDown, Filter, 
    Download, Upload, Plus, Trash2, Edit2, Copy, 
    Check, X, AlertTriangle, Info, Clock, BarChart2
} from 'lucide-react';

// API helper
const api = {
    get: async (url) => {
        const resp = await fetch(url);
        return resp.json();
    },
    post: async (url, data) => {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return resp.json();
    },
    delete: async (url) => {
        const resp = await fetch(url, { method: 'DELETE' });
        return resp.json();
    }
};

export default function SignalEngine() {
    const [activeTab, setActiveTab] = useState('generator'); // generator, manager, history
    const [strategies, setStrategies] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadStrategies();
    }, []);

    const loadStrategies = async () => {
        setLoading(true);
        try {
            const data = await api.get('/api/v1/strategies');
            setStrategies(data.strategies || []);
        } catch (err) {
            console.error("Failed to load strategies:", err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ padding: '24px', color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', height: 'calc(100vh - 48px)', overflowY: 'auto' }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div>
                    <h1 style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.03em', margin: 0, background: 'linear-gradient(135deg, var(--cyan), var(--purple))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                        Strategy Signal Engine
                    </h1>
                    <p style={{ color: 'var(--text-dim)', fontSize: '14px', marginTop: '4px' }}>
                        Generate high-confidence trade signals from backtested strategies.
                    </p>
                </div>
                
                {/* Tabs */}
                <div style={{ display: 'flex', gap: '8px', background: 'var(--bg-secondary)', padding: '4px', borderRadius: '12px', border: '1px solid var(--border)' }}>
                    {[
                        { id: 'generator', label: 'Signal Generator', icon: Zap },
                        { id: 'manager', label: 'Strategy Manager', icon: BarChart2 },
                        { id: 'history', label: 'Signal History', icon: Clock },
                    ].map(tab => {
                        const IsActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: '8px',
                                    padding: '8px 16px', borderRadius: '8px',
                                    border: 'none', cursor: 'pointer',
                                    background: IsActive ? 'var(--bg-primary)' : 'transparent',
                                    color: IsActive ? 'var(--cyan)' : 'var(--text-secondary)',
                                    fontWeight: IsActive ? 700 : 500,
                                    fontSize: '13px',
                                    transition: 'all 0.2s ease',
                                    boxShadow: IsActive ? '0 4px 12px rgba(0,0,0,0.1)' : 'none',
                                }}
                            >
                                <tab.icon size={14} />
                                {tab.label}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Content */}
            {activeTab === 'generator' && <GeneratorTab strategies={strategies} />}
            {activeTab === 'manager' && <ManagerTab strategies={strategies} reload={loadStrategies} />}
            {activeTab === 'history' && <HistoryTab strategies={strategies} />}
        </div>
    );
}

// ── GENERATOR TAB ──────────────────────────────────────────────────────────
function GeneratorTab({ strategies }) {
    const [formData, setFormData] = useState({
        strategy_id: '',
        coin: '',
        timeframe: '1h',
        direction: 'both',
        rr_ratio: 2.0,
        sl_method: 'atr',
        account_size: 10000,
        risk_pct: 1.0,
        extra_context: ''
    });
    const [generating, setGenerating] = useState(false);
    const [signalOutput, setSignalOutput] = useState('');
    const [parsedSignal, setParsedSignal] = useState(null);

    const handleGenerate = async () => {
        if (!formData.strategy_id || !formData.coin || !formData.timeframe) {
            alert("Please fill in required fields (Strategy, Coin, Timeframe)");
            return;
        }

        setGenerating(true);
        setSignalOutput('');
        setParsedSignal(null);

        try {
            const resp = await fetch('/api/v1/signals/generate-signal', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let accumulated = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                accumulated += chunk;
                setSignalOutput(accumulated);
            }

            // Try to parse JSON at the end
            try {
                const json = JSON.parse(accumulated);
                setParsedSignal(json);
            } catch (e) {
                console.error("Failed to parse signal JSON:", e);
                // Try to find JSON block if mixed with text
                const jsonMatch = accumulated.match(/\{[\s\S]*\}/);
                if (jsonMatch) {
                    try {
                        setParsedSignal(JSON.parse(jsonMatch[0]));
                    } catch (e2) {}
                }
            }
        } catch (err) {
            console.error("Generation failed:", err);
            setSignalOutput(`Error: ${err.message}`);
        } finally {
            setGenerating(false);
        }
    };

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
            {/* Form */}
            <div style={{ background: 'var(--bg-secondary)', padding: '20px', borderRadius: '16px', border: '1px solid var(--border)', height: 'fit-content' }}>
                <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: 700 }}>Request Parameters</h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div>
                        <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>STRATEGY *</label>
                        <select 
                            value={formData.strategy_id}
                            onChange={e => setFormData({...formData, strategy_id: e.target.value})}
                            style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                        >
                            <option value="">Select Strategy</option>
                            {strategies.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                        </select>
                    </div>

                    <div>
                        <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>COIN *</label>
                        <input 
                            placeholder="e.g. BTC/USDT"
                            value={formData.coin}
                            onChange={e => setFormData({...formData, coin: e.target.value.toUpperCase()})}
                            style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                        />
                    </div>

                    <div>
                        <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>TIMEFRAME *</label>
                        <select 
                            value={formData.timeframe}
                            onChange={e => setFormData({...formData, timeframe: e.target.value})}
                            style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                        >
                            {["5m", "15m", "1h", "2h", "4h", "1d"].map(tf => <option key={tf} value={tf}>{tf}</option>)}
                        </select>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                        <div>
                            <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>DIRECTION</label>
                            <select 
                                value={formData.direction}
                                onChange={e => setFormData({...formData, direction: e.target.value})}
                                style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                            >
                                <option value="both">Both</option>
                                <option value="long">Long</option>
                                <option value="short">Short</option>
                            </select>
                        </div>
                        <div>
                            <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>R:R RATIO</label>
                            <input 
                                type="number" step="0.1"
                                value={formData.rr_ratio}
                                onChange={e => setFormData({...formData, rr_ratio: parseFloat(e.target.value)})}
                                style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                            />
                        </div>
                    </div>

                    <div>
                        <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>SL METHOD</label>
                        <select 
                            value={formData.sl_method}
                            onChange={e => setFormData({...formData, sl_method: e.target.value})}
                            style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                        >
                            <option value="atr">ATR</option>
                            <option value="swing">Swing High/Low</option>
                            <option value="fixed_pct">Fixed %</option>
                            <option value="volatility_band">Volatility Band</option>
                        </select>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                        <div>
                            <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>ACCOUNT SIZE ($)</label>
                            <input 
                                type="number"
                                value={formData.account_size}
                                onChange={e => setFormData({...formData, account_size: parseFloat(e.target.value)})}
                                style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                            />
                        </div>
                        <div>
                            <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>RISK PER TRADE (%)</label>
                            <input 
                                type="number" step="0.1"
                                value={formData.risk_pct}
                                onChange={e => setFormData({...formData, risk_pct: parseFloat(e.target.value)})}
                                style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                            />
                        </div>
                    </div>

                    <div>
                        <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>EXTRA CONTEXT (Optional)</label>
                        <textarea 
                            placeholder="Add chart patterns, news, or specific conditions..."
                            value={formData.extra_context}
                            onChange={e => setFormData({...formData, extra_context: e.target.value})}
                            style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', height: '80px', resize: 'none' }}
                        />
                    </div>

                    <button
                        onClick={handleGenerate}
                        disabled={generating}
                        style={{
                            width: '100%', padding: '12px', borderRadius: '8px',
                            background: generating ? 'var(--bg-primary)' : 'linear-gradient(135deg, var(--cyan), var(--purple))',
                            color: generating ? 'var(--text-dim)' : '#000',
                            fontWeight: 700, border: 'none', cursor: generating ? 'not-allowed' : 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                            transition: 'all 0.2s ease',
                        }}
                    >
                        {generating ? <div className="spinner" style={{ width: 14, height: 14, border: '2px solid var(--text-dim)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /> : <Zap size={16} fill="#000" />}
                        {generating ? 'Generating Signal...' : 'Generate Signal'}
                    </button>
                </div>
            </div>

            {/* Output */}
            <div style={{ background: 'var(--bg-secondary)', padding: '20px', borderRadius: '16px', border: '1px solid var(--border)', height: '100%', overflowY: 'auto' }}>
                <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: 700 }}>Signal Output</h3>
                
                {!signalOutput && !generating && (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '80%', color: 'var(--text-dim)' }}>
                        <Zap size={48} strokeWidth={1} style={{ marginBottom: '16px', opacity: 0.5 }} />
                        <p style={{ margin: 0 }}>Configure parameters and click Generate.</p>
                        <p style={{ fontSize: '12px', marginTop: '4px' }}>AI will analyze backtest data and generate a structured trade plan.</p>
                    </div>
                )}

                {signalOutput && !parsedSignal && (
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', whiteSpace: 'pre-wrap', color: 'var(--text-secondary)' }}>
                        {signalOutput}
                    </div>
                )}

                {parsedSignal && <SignalDisplay signal={parsedSignal} />}
            </div>
        </div>
    );
}

// ── SIGNAL DISPLAY COMPONENT ──────────────────────────────────────────────
function SignalDisplay({ signal }) {
    const verdictColors = {
        'TAKE': { bg: 'rgba(0, 200, 83, 0.1)', text: '#00c853', border: '#00c853' },
        'SKIP': { bg: 'rgba(213, 0, 0, 0.1)', text: '#d50000', border: '#d50000' },
        'WAIT': { bg: 'rgba(255, 214, 0, 0.1)', text: '#ffd600', border: '#ffd600' }
    };

    const vColor = verdictColors[signal.verdict] || { bg: 'var(--bg-primary)', text: 'var(--text-primary)', border: 'var(--border)' };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Verdict Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: vColor.bg, padding: '16px', borderRadius: '12px', border: `1px solid ${vColor.border}` }}>
                <div>
                    <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)' }}>Verdict</span>
                    <h2 style={{ margin: 0, fontSize: '32px', fontWeight: 900, color: vColor.text, letterSpacing: '0.05em' }}>{signal.verdict}</h2>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)' }}>Validity Score</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                        <div style={{ width: '100px', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                            <div style={{ width: `${(signal.validity_score || 0) * 10}%`, height: '100%', background: 'linear-gradient(90deg, var(--purple), var(--cyan))' }} />
                        </div>
                        <span style={{ fontSize: '18px', fontWeight: 800 }}>{signal.validity_score}/10</span>
                    </div>
                </div>
            </div>

            {/* Verdict Reason */}
            <div style={{ fontSize: '14px', color: 'var(--text-secondary)', fontStyle: 'italic', padding: '0 8px' }}>
                "{signal.verdict_reason}"
            </div>

            {/* Low Sample Warning */}
            {signal.low_sample_warning && (
                <div style={{ background: 'rgba(255, 214, 0, 0.1)', padding: '12px', borderRadius: '8px', border: '1px solid #ffd600', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <AlertTriangle size={16} color="#ffd600" />
                    <span style={{ fontSize: '12px', color: '#ffd600', fontWeight: 600 }}>Low Sample Warning: Backtest has fewer than 5 trades for this setup. Use caution.</span>
                </div>
            )}

            {/* Risk Flags */}
            {signal.risk_flags && signal.risk_flags.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {signal.risk_flags.map((flag, i) => (
                        <div key={i} style={{ background: 'rgba(213, 0, 0, 0.05)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(213, 0, 0, 0.2)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <AlertTriangle size={14} color="#d50000" />
                            <span style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{flag}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* Price Cards (Entry, SL, TP) */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
                {/* Entry */}
                <div style={{ background: 'var(--bg-primary)', padding: '12px', borderRadius: '12px', border: '1px solid var(--border)' }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>Entry Zone</span>
                    <div style={{ fontSize: '16px', fontWeight: 800, marginTop: '4px' }}>
                        {signal.entry?.zone_low} - {signal.entry?.zone_high}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--cyan)', marginTop: '2px' }}>{signal.entry?.trigger}</div>
                </div>

                {/* Stop Loss */}
                <div style={{ background: 'var(--bg-primary)', padding: '12px', borderRadius: '12px', border: '1px solid var(--border)' }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>Stop Loss</span>
                    <div style={{ fontSize: '16px', fontWeight: 800, marginTop: '4px', color: '#d50000' }}>
                        {signal.stop_loss?.price}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>-{signal.stop_loss?.pct_from_entry}% | {signal.stop_loss?.logic}</div>
                </div>

                {/* Take Profit */}
                <div style={{ background: 'var(--bg-primary)', padding: '12px', borderRadius: '12px', border: '1px solid var(--border)' }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>Take Profit 1</span>
                    <div style={{ fontSize: '16px', fontWeight: 800, marginTop: '4px', color: '#00c853' }}>
                        {signal.take_profit?.tp1_price}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>+{signal.take_profit?.tp1_pct}% (Exit {signal.take_profit?.tp1_exit_size_pct}%)</div>
                </div>
            </div>

            {/* Position Size & Confluence */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                {/* Position Size */}
                <div style={{ background: 'var(--bg-primary)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border)' }}>
                    <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: 700 }}>Position Sizing</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                            <span style={{ color: 'var(--text-dim)' }}>Risk Amount:</span>
                            <span style={{ fontWeight: 700 }}>${signal.position_size?.risk_amount_usd}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                            <span style={{ color: 'var(--text-dim)' }}>Position Size:</span>
                            <span style={{ fontWeight: 700 }}>${signal.position_size?.position_size_usd}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                            <span style={{ color: 'var(--text-dim)' }}>Recommended Leverage:</span>
                            <span style={{ fontWeight: 700, color: 'var(--cyan)' }}>{signal.position_size?.recommended_leverage}x</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                            <span style={{ color: 'var(--text-dim)' }}>Contracts:</span>
                            <span style={{ fontWeight: 700 }}>{signal.position_size?.contracts}</span>
                        </div>
                    </div>
                </div>

                {/* Confluence */}
                <div style={{ background: 'var(--bg-primary)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border)' }}>
                    <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: 700 }}>Confluence Checklist</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {[
                            { label: 'BTC Strength', val: signal.confluence?.btc_strength },
                            { label: 'Volume Above Avg', val: signal.confluence?.volume_above_avg },
                            { label: 'HTF Aligned', val: signal.confluence?.htf_aligned },
                            { label: 'Near Key Level', val: signal.confluence?.near_key_level },
                        ].map(item => (
                            <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', alignItems: 'center' }}>
                                <span style={{ color: 'var(--text-dim)' }}>{item.label}:</span>
                                {item.val === true ? <Check size={14} color="#00c853" /> : item.val === false ? <X size={14} color="#d50000" /> : <span style={{ color: 'var(--text-dim)' }}>N/A</span>}
                            </div>
                        ))}
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                            <span style={{ color: 'var(--text-dim)' }}>Session Quality:</span>
                            <span style={{ fontWeight: 700, textTransform: 'uppercase', color: signal.confluence?.session_quality === 'high' ? '#00c853' : signal.confluence?.session_quality === 'medium' ? '#ffd600' : '#d50000' }}>
                                {signal.confluence?.session_quality}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Trade Management */}
            <div style={{ background: 'var(--bg-primary)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border)' }}>
                <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: 700 }}>Trade Management</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                        <span style={{ color: 'var(--text-dim)', minWidth: '120px' }}>Move SL to BE at:</span>
                        <span>{signal.trade_management?.move_sl_to_be_at}</span>
                    </div>
                    {signal.trade_management?.add_condition && (
                        <div style={{ display: 'flex', gap: '8px' }}>
                            <span style={{ color: 'var(--text-dim)', minWidth: '120px' }}>Add Condition:</span>
                            <span>{signal.trade_management?.add_condition}</span>
                        </div>
                    )}
                    <div style={{ display: 'flex', gap: '8px' }}>
                        <span style={{ color: 'var(--text-dim)', minWidth: '120px' }}>Early Exit:</span>
                        <span>{signal.trade_management?.early_exit}</span>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                        <span style={{ color: 'var(--text-dim)', minWidth: '120px' }}>Max Hold Candles:</span>
                        <span style={{ fontWeight: 700 }}>{signal.trade_management?.max_hold_candles}</span>
                    </div>
                </div>
            </div>

            {/* Copy Button */}
            <button
                onClick={() => {
                    const text = `🚨 SIGNAL: ${signal.verdict} 🚨\nEntry: ${signal.entry?.zone_low} - ${signal.entry?.zone_high}\nSL: ${signal.stop_loss?.price}\nTP1: ${signal.take_profit?.tp1_price}\nLeverage: ${signal.position_size?.recommended_leverage}x`;
                    navigator.clipboard.writeText(text);
                    alert("Signal copied to clipboard!");
                }}
                style={{
                    padding: '12px', borderRadius: '8px', background: 'var(--bg-secondary)', color: 'var(--text-primary)',
                    fontWeight: 700, border: '1px solid var(--border)', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                    transition: 'all 0.2s ease',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-primary)'}
                onMouseLeave={e => e.currentTarget.style.background = 'var(--bg-secondary)'}
            >
                <Copy size={16} />
                Copy Signal for Telegram/Discord
            </button>
        </div>
    );
}

// ── MANAGER TAB ────────────────────────────────────────────────────────────
function ManagerTab({ strategies, reload }) {
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [importData, setImportData] = useState({ strategy_id: '', data: '', format: 'json' });
    const [isImporting, setIsImporting] = useState(false);

    const handleImport = async () => {
        if (!importData.strategy_id || !importData.data) {
            alert("Please fill in required fields");
            return;
        }

        setIsImporting(true);
        try {
            const resp = await api.post(`/api/v1/strategies/${importData.strategy_id}/import-results`, {
                results: importData.data,
                format: importData.format
            });
            alert(resp.message);
            setImportData({ strategy_id: '', data: '', format: 'json' });
            reload();
        } catch (err) {
            console.error("Import failed:", err);
            alert("Import failed: " + err.message);
        } finally {
            setIsImporting(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm("Are you sure you want to delete this strategy? All results will be lost.")) return;
        try {
            await api.delete(`/api/v1/strategies/${id}`);
            reload();
        } catch (err) {
            console.error("Delete failed:", err);
        }
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Header Actions */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Managed Strategies ({strategies.length})</h3>
                <button
                    onClick={() => setIsAddModalOpen(true)}
                    style={{
                        padding: '10px 16px', borderRadius: '8px', background: 'var(--cyan)', color: '#000',
                        fontWeight: 700, border: 'none', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: '8px',
                    }}
                >
                    <Plus size={16} fill="#000" />
                    Add Strategy
                </button>
            </div>

            {/* Strategy Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
                {strategies.map(strat => (
                    <div key={strat.id} style={{ background: 'var(--bg-secondary)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <div>
                                <h4 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>{strat.name}</h4>
                                <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                                    {strat.description || 'No description'}
                                </p>
                            </div>
                            <button 
                                onClick={() => handleDelete(strat.id)}
                                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-dim)' }}
                                onMouseEnter={e => e.currentTarget.style.color = '#d50000'}
                                onMouseLeave={e => e.currentTarget.style.color = 'var(--text-dim)'}
                            >
                                <Trash2 size={16} />
                            </button>
                        </div>

                        {/* Stats */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px', background: 'var(--bg-primary)', padding: '8px', borderRadius: '8px' }}>
                            <div>
                                <span style={{ color: 'var(--text-dim)' }}>Best TF:</span>
                                <span style={{ fontWeight: 700, marginLeft: '4px', color: 'var(--cyan)' }}>{strat.best_tf || 'N/A'}</span>
                            </div>
                            <div>
                                <span style={{ color: 'var(--text-dim)' }}>Win Rate:</span>
                                <span style={{ fontWeight: 700, marginLeft: '4px', color: '#00c853' }}>{strat.best_win_rate ? `${strat.best_win_rate}%` : 'N/A'}</span>
                            </div>
                            <div>
                                <span style={{ color: 'var(--text-dim)' }}>Coins Tested:</span>
                                <span style={{ fontWeight: 700, marginLeft: '4px' }}>{strat.coins_tested || 0}</span>
                            </div>
                            <div>
                                <span style={{ color: 'var(--text-dim)' }}>Pass &gt;65%:</span>
                                <span style={{ fontWeight: 700, marginLeft: '4px', color: 'var(--purple)' }}>{strat.coins_above_65 || 0}</span>
                            </div>
                        </div>

                        {/* Tags */}
                        {strat.tags && (
                            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                {Array.isArray(strat.tags) ? strat.tags.map(tag => (
                                    <span key={tag} style={{ fontSize: '10px', background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px', color: 'var(--text-dim)' }}>{tag}</span>
                                )) : <span style={{ fontSize: '10px', background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px', color: 'var(--text-dim)' }}>{strat.tags}</span>}
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {/* Bulk Import Section */}
            <div style={{ background: 'var(--bg-secondary)', padding: '20px', borderRadius: '16px', border: '1px solid var(--border)', marginTop: '12px' }}>
                <h3 style={{ margin: '0 0 4px 0', fontSize: '18px', fontWeight: 700 }}>Bulk Import Results</h3>
                <p style={{ color: 'var(--text-dim)', fontSize: '13px', margin: '0 0 16px 0' }}>Import per-coin backtest results from TradingView CSV or custom JSON.</p>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                        <div>
                            <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>TARGET STRATEGY</label>
                            <select 
                                value={importData.strategy_id}
                                onChange={e => setImportData({...importData, strategy_id: e.target.value})}
                                style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                            >
                                <option value="">Select Strategy</option>
                                {strategies.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                            </select>
                        </div>
                        <div>
                            <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>FORMAT</label>
                            <select 
                                value={importData.format}
                                onChange={e => setImportData({...importData, format: e.target.value})}
                                style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                            >
                                <option value="json">JSON</option>
                                <option value="csv">CSV (TradingView Export)</option>
                            </select>
                        </div>
                    </div>

                    <div>
                        <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>DATA (Paste here)</label>
                        <textarea 
                            placeholder={importData.format === 'json' ? '[{"coin": "BTC/USDT", "tf_results": {"1h": {"win_rate": 70, "trades": 50}}}]' : 'coin,5m_win,5m_trades,...\nBTC/USDT,70,50,...'}
                            value={importData.data}
                            onChange={e => setImportData({...importData, data: e.target.value})}
                            style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', height: '120px', fontFamily: 'var(--font-mono)', fontSize: '12px' }}
                        />
                    </div>

                    <button
                        onClick={handleImport}
                        disabled={isImporting}
                        style={{
                            padding: '12px', borderRadius: '8px', background: 'var(--purple)', color: '#fff',
                            fontWeight: 700, border: 'none', cursor: isImporting ? 'not-allowed' : 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                            transition: 'all 0.2s ease',
                        }}
                    >
                        <Upload size={16} />
                        {isImporting ? 'Importing...' : 'Import Results'}
                    </button>
                </div>
            </div>

            {/* Add Modal */}
            {isAddModalOpen && (
                <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
                    <div style={{ background: 'var(--bg-secondary)', padding: '24px', borderRadius: '16px', border: '1px solid var(--border)', width: '500px', maxWidth: '90%' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Add New Strategy</h3>
                            <button onClick={() => setIsAddModalOpen(false)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-dim)' }}><X size={20} /></button>
                        </div>
                        
                        <AddStrategyForm onSuccess={() => { setIsAddModalOpen(false); reload(); }} />
                    </div>
                </div>
            )}
        </div>
    );
}

function AddStrategyForm({ onSuccess }) {
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        coins_tested: 0,
        coins_above_65: 0,
        best_win_rate: 0,
        best_tf: '1h',
        tags: ''
    });

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await api.post('/api/v1/strategies', {
                ...formData,
                tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean)
            });
            onSuccess();
        } catch (err) {
            console.error("Failed to add strategy:", err);
            alert("Failed: " + err.message);
        }
    };

    return (
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
                <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>NAME *</label>
                <input 
                    required
                    value={formData.name}
                    onChange={e => setFormData({...formData, name: e.target.value})}
                    style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                />
            </div>
            <div>
                <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>DESCRIPTION</label>
                <textarea 
                    value={formData.description}
                    onChange={e => setFormData({...formData, description: e.target.value})}
                    style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', height: '60px' }}
                />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>COINS TESTED</label>
                    <input 
                        type="number"
                        value={formData.coins_tested}
                        onChange={e => setFormData({...formData, coins_tested: parseInt(e.target.value)})}
                        style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                    />
                </div>
                <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>COINS &gt;65%</label>
                    <input 
                        type="number"
                        value={formData.coins_above_65}
                        onChange={e => setFormData({...formData, coins_above_65: parseInt(e.target.value)})}
                        style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                    />
                </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>BEST WIN RATE (%)</label>
                    <input 
                        type="number" step="0.1"
                        value={formData.best_win_rate}
                        onChange={e => setFormData({...formData, best_win_rate: parseFloat(e.target.value)})}
                        style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                    />
                </div>
                <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>BEST TF</label>
                    <select 
                        value={formData.best_tf}
                        onChange={e => setFormData({...formData, best_tf: e.target.value})}
                        style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                    >
                        {["5m", "15m", "1h", "2h", "4h", "1d"].map(tf => <option key={tf} value={tf}>{tf}</option>)}
                    </select>
                </div>
            </div>
            <div>
                <label style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px', display: 'block' }}>TAGS (Comma separated)</label>
                <input 
                    placeholder="trend, momentum, scalp"
                    value={formData.tags}
                    onChange={e => setFormData({...formData, tags: e.target.value})}
                    style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                />
            </div>
            <button
                type="submit"
                style={{
                    padding: '12px', borderRadius: '8px', background: 'var(--cyan)', color: '#000',
                    fontWeight: 700, border: 'none', cursor: 'pointer', marginTop: '8px'
                }}
            >
                Save Strategy
            </button>
        </form>
    );
}

// ── HISTORY TAB ────────────────────────────────────────────────────────────
function HistoryTab({ strategies }) {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [filters, setFilters] = useState({ coin: '', strategy_id: '', verdict: '' });

    useEffect(() => {
        loadHistory();
    }, [filters]);

    const loadHistory = async () => {
        setLoading(true);
        try {
            const query = new URLSearchParams(filters).toString();
            const data = await api.get(`/api/v1/signals/history-detailed?${query}`);
            setHistory(data.history || []);
        } catch (err) {
            console.error("Failed to load history:", err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Filters */}
            <div style={{ display: 'flex', gap: '12px', background: 'var(--bg-secondary)', padding: '12px', borderRadius: '12px', border: '1px solid var(--border)', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Filter size={16} color="var(--text-dim)" />
                    <span style={{ fontSize: '13px', fontWeight: 700 }}>Filters:</span>
                </div>
                
                <input 
                    placeholder="Coin (e.g. BTC)"
                    value={filters.coin}
                    onChange={e => setFilters({...filters, coin: e.target.value})}
                    style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: '12px' }}
                />

                <select 
                    value={filters.strategy_id}
                    onChange={e => setFilters({...filters, strategy_id: e.target.value})}
                    style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: '12px' }}
                >
                    <option value="">All Strategies</option>
                    {strategies.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>

                <select 
                    value={filters.verdict}
                    onChange={e => setFilters({...filters, verdict: e.target.value})}
                    style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: '12px' }}
                >
                    <option value="">All Verdicts</option>
                    <option value="TAKE">TAKE</option>
                    <option value="SKIP">SKIP</option>
                    <option value="WAIT">WAIT</option>
                </select>
            </div>

            {/* Table */}
            <div style={{ background: 'var(--bg-secondary)', borderRadius: '16px', border: '1px solid var(--border)', overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead>
                        <tr style={{ background: 'var(--bg-primary)', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                            <th style={{ padding: '12px 16px', color: 'var(--text-dim)' }}>DATE</th>
                            <th style={{ padding: '12px 16px', color: 'var(--text-dim)' }}>COIN</th>
                            <th style={{ padding: '12px 16px', color: 'var(--text-dim)' }}>STRATEGY</th>
                            <th style={{ padding: '12px 16px', color: 'var(--text-dim)' }}>TF</th>
                            <th style={{ padding: '12px 16px', color: 'var(--text-dim)' }}>VERDICT</th>
                            <th style={{ padding: '12px 16px', color: 'var(--text-dim)' }}>SCORE</th>
                            <th style={{ padding: '12px 16px', color: 'var(--text-dim)' }}>OUTCOME</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan="7" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-dim)' }}>Loading history...</td>
                            </tr>
                        ) : history.length === 0 ? (
                            <tr>
                                <td colSpan="7" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-dim)' }}>No signals found matching filters.</td>
                            </tr>
                        ) : history.map(row => (
                            <tr key={row.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)', cursor: 'pointer' }} onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.01)'} onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                                <td style={{ padding: '12px 16px', color: 'var(--text-dim)' }}>{row.created_at ? new Date(row.created_at).toLocaleString() : 'N/A'}</td>
                                <td style={{ padding: '12px 16px', fontWeight: 700 }}>{row.coin}</td>
                                <td style={{ padding: '12px 16px' }}>{row.strategy_name}</td>
                                <td style={{ padding: '12px 16px' }}>{row.timeframe}</td>
                                <td style={{ padding: '12px 16px' }}>
                                    <span style={{ 
                                        padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 700,
                                        background: row.verdict === 'TAKE' ? 'rgba(0,200,83,0.1)' : row.verdict === 'SKIP' ? 'rgba(213,0,0,0.1)' : 'rgba(255,214,0,0.1)',
                                        color: row.verdict === 'TAKE' ? '#00c853' : row.verdict === 'SKIP' ? '#d50000' : '#ffd600'
                                    }}>
                                        {row.verdict}
                                    </span>
                                </td>
                                <td style={{ padding: '12px 16px', fontWeight: 700 }}>{row.validity_score}/10</td>
                                <td style={{ padding: '12px 16px' }}>
                                    <span style={{ 
                                        padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 700,
                                        background: row.outcome === 'Win' ? 'rgba(0,200,83,0.1)' : row.outcome === 'Loss' ? 'rgba(213,0,0,0.1)' : 'rgba(255,255,255,0.05)',
                                        color: row.outcome === 'Win' ? '#00c853' : row.outcome === 'Loss' ? '#d50000' : 'var(--text-dim)'
                                    }}>
                                        {row.outcome}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
