import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import StatCard from '../components/StatCard';
import { Cpu, Zap, Activity, Shield, Target, TrendingUp, DollarSign } from 'lucide-react';

export default function AutoTrader() {
  const [status, setStatus] = useState({ 
    is_enabled: false, futures_balance: 0, available_balance: 0, unrealized_pnl: 0, open_positions_count: 0, daily_pnl: 0 
  });
  const [settings, setSettings] = useState({ leverage: 10, per_trade_percent: 30, max_open_trades: 3, daily_loss_limit: 20 });
  const [strategies, setStrategies] = useState([]);
  const [positions, setPositions] = useState([]);
  const [history, setHistory] = useState([]);
  const [alertMsg, setAlertMsg] = useState(null);

  useEffect(() => {
    fetchData();
    api.get('/autotrader/settings').then(res => setSettings(res.data)).catch(console.error);
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [st, strat, pos, hist] = await Promise.all([
        api.get('/autotrader/status'),
        api.get('/autotrader/strategies'),
        api.get('/autotrader/positions'),
        api.get('/autotrader/trades')
      ]);
      setStatus(st.data);
      setStrategies(strat.data.strategies || []);
      setPositions(pos.data.positions || []);
      setHistory(hist.data.trades || []);
    } catch (e) {
      console.error(e);
    }
  };

  const toggleEngine = async () => {
    const nextState = !status.is_enabled;
    setStatus({...status, is_enabled: nextState});
    try {
      if (status.is_enabled) {
        await api.post('/autotrader/disable');
      } else {
        if(window.confirm("This will place REAL orders on Binance. Are you sure?")) {
          await api.post('/autotrader/enable');
        } else {
          setStatus({...status, is_enabled: status.is_enabled});
          return;
        }
      }
      fetchData();
    } catch (e) {
      console.error(e);
      setStatus({...status, is_enabled: status.is_enabled});
    }
  };

  const saveSettings = async (e) => {
    e.preventDefault();
    try {
      await api.post('/autotrader/settings', settings);
      setAlertMsg('Settings saved successfully!');
      setTimeout(() => setAlertMsg(null), 3000);
    } catch(e) {
      console.error(e);
    }
  };

  const toggleStrategy = async (name) => {
    const oldStrats = [...strategies];
    setStrategies(strategies.map(s => s.name === name ? {...s, enabled: !s.enabled} : s));
    try {
      await api.post(`/autotrader/strategies/${name}/toggle`);
      fetchData();
    } catch(e) { 
      console.error(e); 
      setStrategies(oldStrats);
    }
  };

  const calcMargin = (status.available_balance * (settings.per_trade_percent / 100)).toFixed(2);
  const calcSlMove = (50 / settings.leverage).toFixed(2);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, height: '100%', overflow: 'hidden', backgroundColor: '#0a0e1a', color: '#e2e8f0', fontFamily: 'var(--font-mono)' }}>
      
      {/* PAGE HEADER */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 16px', backgroundColor: '#111827', borderBottom: '1px solid #1e2a3a' }}>
        <div>
          <h1 style={{ color: '#00d4ff', fontSize: 18, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>⚡ Auto Trading Terminal</h1>
          <p style={{ color: '#64748b', fontSize: 11 }}>Automated execution engine</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 15 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ color: '#64748b', fontSize: 10 }}>FUTURES BALANCE</div>
            <div style={{ color: '#00ff88', fontSize: 18, fontWeight: 700 }}>
              ${status.futures_balance !== undefined ? parseFloat(status.futures_balance).toFixed(2) : '–'}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div className="live-dot" style={{ backgroundColor: status.is_enabled ? '#00ff88' : '#64748b' }} />
            <span style={{ fontSize: 10, color: status.is_enabled ? '#00ff88' : '#64748b', textTransform: 'uppercase' }}>
              {status.is_enabled ? 'LIVE' : 'IDLE'}
            </span>
          </div>
        </div>
      </div>

      {/* STATS ROW (Row of 6) */}
      <div style={{ display: 'flex', gap: 8, flexShrink: 0, flexWrap: 'wrap', padding: '0 16px' }}>
        <StatCard label="Futures Bal" value={status.futures_balance !== undefined ? `$${parseFloat(status.futures_balance).toFixed(2)}` : '—'} icon={DollarSign} color="cyan" />
        <StatCard label="Available" value={status.available_balance !== undefined ? `$${parseFloat(status.available_balance).toFixed(2)}` : '—'} icon={DollarSign} color="cyan" />
        <StatCard label="Unrealized PnL" value={status.unrealized_pnl ? `$${status.unrealized_pnl.toFixed(2)}` : '0.00'} icon={Activity} color={status.unrealized_pnl >= 0 ? 'green' : 'red'} />
        <StatCard label="Open Positions" value={String(status.open_positions_count)} icon={Target} color="yellow" />
        <StatCard label="Daily PnL" value={status.daily_pnl ? `$${status.daily_pnl.toFixed(2)}` : '0.00'} icon={TrendingUp} color={status.daily_pnl >= 0 ? 'green' : 'red'} />
        <StatCard label="Active Strats" value={String(strategies.filter(s => s.enabled).length)} icon={Cpu} color="purple" />
      </div>

      {/* ENGINE STATUS BAR */}
      <div style={{ margin: '0 16px', padding: '12px 16px', backgroundColor: '#111827', border: '1px solid #1e2a3a', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderRadius: 0 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 8, height: 8, backgroundColor: status.is_enabled ? '#00ff88' : '#ff4757' }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: status.is_enabled ? '#00ff88' : '#ff4757', textTransform: 'uppercase' }}>
              {status.is_enabled ? 'Auto Trading Active' : 'Auto Trading Stopped'}
            </span>
          </div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
            {status.is_enabled ? 'System is actively monitoring strategies and executing orders.' : 'System is idle. Enable to start automated execution.'}
          </div>
        </div>
        <button 
          onClick={toggleEngine}
          style={{ 
            backgroundColor: status.is_enabled ? '#ff4757' : '#00d4ff', 
            color: '#000', 
            border: 'none', 
            padding: '8px 16px', 
            fontSize: 12, 
            fontWeight: 700, 
            cursor: 'pointer',
            borderRadius: 0,
            textTransform: 'uppercase'
          }}
        >
          {status.is_enabled ? 'Disable Engine' : 'Enable Engine'}
        </button>
      </div>

      {/* MAIN CONTENT GRID */}
      <div style={{ display: 'flex', gap: 14, flex: 1, minHeight: 0, padding: '0 16px 16px 16px' }}>
        
        {/* LEFT COLUMN: Settings & Strategies */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
          
          {/* RISK SETTINGS */}
          <div style={{ backgroundColor: '#111827', border: '1px solid #1e2a3a', padding: '12px 16px', borderRadius: 0 }}>
            <div style={{ fontSize: 11, color: '#64748b', letterSpacing: '0.08em', marginBottom: 12, fontWeight: 700 }}>RISK CONFIGURATION</div>
            <form onSubmit={saveSettings} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: '#64748b' }}>LEVERAGE</span>
                  <span style={{ color: '#00d4ff' }}>{settings.leverage}x</span>
                </div>
                <input type="range" min="1" max="125" value={settings.leverage} onChange={e => setSettings({...settings, leverage: parseInt(e.target.value)})} style={{ width: 'full', accentColor: '#00d4ff' }} />
              </div>
              
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: '#64748b' }}>PER TRADE SIZE</span>
                  <span style={{ color: '#00d4ff' }}>{settings.per_trade_percent}%</span>
                </div>
                <input type="range" min="5" max="100" value={settings.per_trade_percent} onChange={e => setSettings({...settings, per_trade_percent: parseInt(e.target.value)})} style={{ width: 'full', accentColor: '#00d4ff' }} />
              </div>

              <div style={{ display: 'flex', gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>MAX OPEN TRADES</div>
                  <input type="number" value={settings.max_open_trades} onChange={e => setSettings({...settings, max_open_trades: parseInt(e.target.value)})} style={{ width: '100%', padding: '6px', backgroundColor: '#0a0e1a', border: '1px solid #1e2a3a', color: '#e2e8f0', fontSize: 12, borderRadius: 0 }} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>DAILY LOSS LIMIT (%)</div>
                  <input type="number" value={settings.daily_loss_limit} onChange={e => setSettings({...settings, daily_loss_limit: parseInt(e.target.value)})} style={{ width: '100%', padding: '6px', backgroundColor: '#0a0e1a', border: '1px solid #1e2a3a', color: '#e2e8f0', fontSize: 12, borderRadius: 0 }} />
                </div>
              </div>

              <div style={{ backgroundColor: '#0a0e1a', padding: '10px', display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                <div>
                  <span style={{ color: '#64748b' }}>EST MARGIN: </span>
                  <span style={{ color: '#e2e8f0' }}>${calcMargin}</span>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>SL DISTANCE: </span>
                  <span style={{ color: '#ff4757' }}>{calcSlMove}%</span>
                </div>
              </div>

              <button type="submit" style={{ backgroundColor: '#00d4ff', color: '#000', border: 'none', padding: '8px', fontSize: 11, fontWeight: 700, cursor: 'pointer', borderRadius: 0, textTransform: 'uppercase' }}>
                Apply Risk Settings
              </button>
            </form>
          </div>

          {/* STRATEGIES */}
          <div style={{ backgroundColor: '#111827', border: '1px solid #1e2a3a', padding: '12px 16px', borderRadius: 0, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ fontSize: 11, color: '#64748b', letterSpacing: '0.08em', marginBottom: 10, fontWeight: 700 }}>STRATEGY ALLOCATION</div>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
              {strategies.map(s => (
                <div key={s.name} style={{ backgroundColor: '#0a0e1a', border: '1px solid #1e2a3a', padding: '8px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: s.enabled ? '#00d4ff' : '#e2e8f0' }}>{s.name}</div>
                    <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>{s.description}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 10, color: '#64748b' }}>Signals: {s.signals_today}</span>
                    <div 
                      onClick={() => toggleStrategy(s.name)}
                      style={{ 
                        width: 32, height: 16, backgroundColor: s.enabled ? '#00d4ff' : '#1e2a3a', 
                        cursor: 'pointer', position: 'relative', display: 'flex', alignItems: 'center',
                        justifyContent: s.enabled ? 'flex-end' : 'flex-start', padding: 2
                      }}
                    >
                      <div style={{ width: 12, height: 12, backgroundColor: '#000' }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Positions & History */}
        <div style={{ flex: 1.5, display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
          
          {/* ACTIVE POSITIONS */}
          <div style={{ backgroundColor: '#111827', border: '1px solid #1e2a3a', padding: '12px 16px', borderRadius: 0, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ fontSize: 11, color: '#64748b', letterSpacing: '0.08em', marginBottom: 10, fontWeight: 700 }}>ACTIVE POSITIONS</div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {positions.length === 0 ? (
                <div style={{ color: '#64748b', fontSize: 11, textAlign: 'center', padding: '20px 0' }}>No active positions</div>
              ) : (
                <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ color: '#64748b', textAlign: 'left', borderBottom: '1px solid #1e2a3a' }}>
                      <th style={{ padding: '6px 4px' }}>Symbol</th>
                      <th style={{ padding: '6px 4px' }}>Side</th>
                      <th style={{ padding: '6px 4px' }}>Entry</th>
                      <th style={{ padding: '6px 4px' }}>PnL</th>
                      <th style={{ padding: '6px 4px' }}>SL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map(p => (
                      <tr key={p.id} style={{ borderBottom: '1px solid #1e2a3a' }}>
                        <td style={{ padding: '8px 4px', color: '#00d4ff', fontWeight: 700 }}>{p.symbol}</td>
                        <td style={{ padding: '8px 4px' }}>
                          <span style={{ color: p.side === 'LONG' ? '#00ff88' : '#ff4757', fontWeight: 700 }}>{p.side}</span>
                        </td>
                        <td style={{ padding: '8px 4px' }}>${p.entry.toFixed(2)}</td>
                        <td style={{ padding: '8px 4px', color: p.pnl >= 0 ? '#00ff88' : '#ff4757', fontWeight: 700 }}>
                          {p.pnl >= 0 ? '+' : ''}{p.pnl ? p.pnl.toFixed(2) : '0.00'}
                        </td>
                        <td style={{ padding: '8px 4px', color: '#64748b' }}>${p.sl.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* RECENT TRADES */}
          <div style={{ backgroundColor: '#111827', border: '1px solid #1e2a3a', padding: '12px 16px', borderRadius: 0, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ fontSize: 11, color: '#64748b', letterSpacing: '0.08em', marginBottom: 10, fontWeight: 700 }}>RECENT TERMINAL LOGS</div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {history.length === 0 ? (
                <div style={{ color: '#64748b', fontSize: 11, textAlign: 'center', padding: '20px 0' }}>No trade logs available</div>
              ) : (
                <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ color: '#64748b', textAlign: 'left', borderBottom: '1px solid #1e2a3a' }}>
                      <th style={{ padding: '6px 4px' }}>Symbol</th>
                      <th style={{ padding: '6px 4px' }}>Strategy</th>
                      <th style={{ padding: '6px 4px' }}>PnL</th>
                      <th style={{ padding: '6px 4px' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(h => (
                      <tr key={h.id} style={{ borderBottom: '1px solid #1e2a3a' }}>
                        <td style={{ padding: '8px 4px', color: '#00d4ff', fontWeight: 700 }}>{h.symbol}</td>
                        <td style={{ padding: '8px 4px' }}>{h.strategy}</td>
                        <td style={{ padding: '8px 4px', color: h.pnl >= 0 ? '#00ff88' : '#ff4757', fontWeight: 700 }}>
                          {h.pnl >= 0 ? '+' : ''}{h.pnl ? h.pnl.toFixed(2) : '0.00'}
                        </td>
                        <td style={{ padding: '8px 4px' }}>
                          <span style={{ 
                            fontSize: 10, padding: '2px 4px',
                            backgroundColor: h.status.includes('SL') ? 'rgba(255, 71, 87, 0.1)' : h.status.includes('TP') ? 'rgba(0, 255, 136, 0.1)' : 'rgba(0, 212, 255, 0.1)',
                            color: h.status.includes('SL') ? '#ff4757' : h.status.includes('TP') ? '#00ff88' : '#00d4ff',
                            fontWeight: 700
                          }}>
                            {h.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

        </div>
      </div>

      {alertMsg && (
        <div style={{
          position: 'fixed', top: '20px', right: '20px',
          backgroundColor: '#111827', border: '1px solid #00d4ff',
          padding: '12px 20px', color: '#e2e8f0', zIndex: 1000,
          boxShadow: '0 0 10px rgba(0, 212, 255, 0.3)',
          fontFamily: 'var(--font-mono)', fontSize: 12
        }}>
          <span style={{ color: '#00ff88' }}>[SUCCESS]</span> {alertMsg}
        </div>
      )}

    </div>
  );
}
