import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { API } from '../lib/api';
import { usePriceSocket } from '../lib/socket';
import toast from 'react-hot-toast';
import { 
    RefreshCw, TrendingUp, TrendingDown, DollarSign, Target, Activity, 
    Award, AlertTriangle, ArrowRight, ArrowDownRight, ArrowUpRight, 
    Calendar as CalendarIcon, Download, CheckCircle, XCircle, Zap 
} from 'lucide-react';
import { 
    LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, 
    Tooltip, ResponsiveContainer, ReferenceLine 
} from 'recharts';

export default function TradingJournal() {
    const queryClient = useQueryClient();
    const [page, setPage] = useState(1);
    const [filterSymbol, setFilterSymbol] = useState('');
    const [filterSide, setFilterSide] = useState('');
    const { prices } = usePriceSocket();

    const { data: summary, isLoading: loadingSummary } = useQuery({
        queryKey: ['journalSummary'],
        queryFn: API.getJournalSummary
    });

    const { data: coinsData, isLoading: loadingCoins } = useQuery({
        queryKey: ['journalCoins'],
        queryFn: API.getJournalCoins
    });

    const { data: tradesData, isLoading: loadingTrades } = useQuery({
        queryKey: ['journalTrades', page, filterSymbol, filterSide],
        queryFn: () => API.getJournalTrades({ page, limit: 50, symbol: filterSymbol, side: filterSide })
    });

    const { data: mistakesData, isLoading: loadingMistakes } = useQuery({
        queryKey: ['journalMistakes'],
        queryFn: API.getJournalMistakes,
        staleTime: 300000
    });

    const { data: calendarData, isLoading: loadingCalendar } = useQuery({
        queryKey: ['journalCalendar'],
        queryFn: API.getJournalCalendar
    });

    const refreshMutation = useMutation({
        mutationFn: API.refreshJournal,
        onSuccess: (res) => {
            if (res.status === 'success') {
                toast.success(res.message || 'Trades synced successfully!');
                queryClient.invalidateQueries({ queryKey: ['journalSummary'] });
                queryClient.invalidateQueries({ queryKey: ['journalCoins'] });
                queryClient.invalidateQueries({ queryKey: ['journalTrades'] });
                queryClient.invalidateQueries({ queryKey: ['journalMistakes'] });
                queryClient.invalidateQueries({ queryKey: ['journalCalendar'] });
            } else {
                toast.error(res.message || 'Failed to sync trades');
            }
        },
        onError: () => toast.error('Error syncing trades with Binance')
    });

    const formatMoney = (val) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val || 0);
    const formatPercent = (val) => `${(val || 0).toFixed(2)}%`;

    const chartData = useMemo(() => {
        if (!calendarData || calendarData.length === 0) return [];
        let cumulative = 0;
        const sortedData = [...calendarData].sort((a, b) => new Date(a.date) - new Date(b.date));
        
        const data = sortedData.map(d => {
            cumulative += d.pnl;
            return { ...d, cumulativePnl: cumulative };
        });

        // Extend the equity curve flat line to today
        const todayStr = new Date().toISOString().split('T')[0];
        const lastDateStr = data[data.length - 1].date;
        
        if (lastDateStr < todayStr) {
            data.push({
                date: todayStr,
                pnl: 0,
                count: 0,
                cumulativePnl: cumulative
            });
        }
        return data;
    }, [calendarData]);

    const heatmapDays = useMemo(() => {
        const days = [];
        const today = new Date();
        for (let i = 363; i >= 0; i--) {
            const d = new Date(today);
            d.setDate(today.getDate() - i);
            const dateStr = d.toISOString().split('T')[0];
            const dayData = calendarData?.find(c => c.date === dateStr);
            days.push({
                date: dateStr,
                pnl: dayData ? dayData.pnl : null,
                count: dayData ? dayData.count : 0
            });
        }
        return days;
    }, [calendarData]);

    const handleExport = () => {
        if (!tradesData?.trades) return;
        const csvContent = "data:text/csv;charset=utf-8," 
            + "Date,Symbol,Side,Entry,Exit,Qty,P&L,P&L%\n"
            + tradesData.trades.map(t => {
                return `${t.entry_time},${t.symbol},${t.side},${t.entry_price},${t.exit_price || ''},${t.qty},${t.pnl || 0},${t.pnl_percent || 0}`;
            }).join("\n");
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", "trades_export.csv");
        document.body.appendChild(link);
        link.click();
    };

    if (summary?.error) {
        return (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
                <AlertTriangle size={48} className="text-[var(--red)]" />
                <h2 className="text-xl font-bold text-[var(--text-primary)]">No Trade History Found</h2>
                <p className="text-[var(--text-secondary)]">Sync your Binance trades to populate the journal.</p>
                <button onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending} className="btn btn-primary flex items-center gap-2">
                    <RefreshCw size={16} className={refreshMutation.isPending ? 'animate-spin' : ''} />
                    {refreshMutation.isPending ? 'Syncing with Binance...' : 'Sync Binance Trades'}
                </button>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-6 pb-12 overflow-x-hidden" style={{ fontFamily: 'var(--font-sans)', color: 'var(--text-primary)' }}>
            <style>{`
                .custom-scrollbar::-webkit-scrollbar { height: 6px; width: 6px; }
                .custom-scrollbar::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); }
                .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
            `}</style>
            
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-[var(--text-primary)]">Trading Journal & Analytics</h1>
                    <p className="text-[var(--text-secondary)] text-sm mt-1">Deep analysis of your Binance trading performance</p>
                </div>
                <button onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending} className="btn btn-secondary flex items-center gap-2">
                    <RefreshCw size={14} className={refreshMutation.isPending ? 'animate-spin' : ''} />
                    {refreshMutation.isPending ? 'Syncing...' : 'Sync Trades'}
                </button>
            </div>

            {/* SECTION 1: TOP STATS BAR */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <StatCard title="Total Invested" value={formatMoney(summary?.total_invested)} icon={DollarSign} loading={loadingSummary} />
                <StatCard title="Net P&L" value={formatMoney(summary?.net_pnl)} subtitle={formatPercent(summary?.net_pnl_percent)} valueColor={summary?.net_pnl >= 0 ? 'var(--green)' : 'var(--red)'} icon={summary?.net_pnl >= 0 ? TrendingUp : TrendingDown} loading={loadingSummary} />
                <StatCard title="Win Rate" value={formatPercent(summary?.win_rate)} valueColor={summary?.win_rate >= 50 ? 'var(--green)' : 'var(--red)'} icon={Target} loading={loadingSummary} />
                <StatCard title="Total Trades" value={summary?.total_trades || 0} icon={Activity} loading={loadingSummary} />
                <StatCard title="Profit Factor" value={(summary?.profit_factor || 0).toFixed(2)} valueColor={summary?.profit_factor >= 1 ? 'var(--green)' : 'var(--red)'} icon={Award} loading={loadingSummary} />
                <StatCard title="Avg Gain / Loss" value={`${formatMoney(summary?.avg_gain)} / ${formatMoney(summary?.avg_loss)}`} icon={ArrowRight} loading={loadingSummary} />
            </div>

            {/* SECTION 2: CHARTS ROW */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="card p-4">
                    <h3 className="text-xs font-bold text-[var(--text-secondary)] mb-4 uppercase tracking-wider">Equity Curve (Cumulative P&L)</h3>
                    <div style={{ height: '300px', width: '100%' }}>
                        {loadingCalendar ? <div className="animate-pulse bg-[var(--border)] h-full w-full rounded" /> : (
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData} margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                                    <XAxis dataKey="date" stroke="var(--text-dim)" fontSize={10} tickMargin={8} minTickGap={30} />
                                    <YAxis stroke="var(--text-dim)" fontSize={10} tickFormatter={(v) => `$${v}`} width={50} />
                                    <Tooltip contentStyle={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)', borderRadius: 8, fontSize: 12 }} itemStyle={{ color: 'var(--cyan)' }} />
                                    <ReferenceLine y={0} stroke="var(--text-dim)" strokeDasharray="3 3" />
                                    <Line type="monotone" dataKey="cumulativePnl" stroke="var(--cyan)" strokeWidth={2} dot={false} name="Net P&L" />
                                </LineChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>

                <div className="card p-4">
                    <h3 className="text-xs font-bold text-[var(--text-secondary)] mb-4 uppercase tracking-wider">Daily P&L</h3>
                    <div style={{ height: '300px', width: '100%' }}>
                        {loadingCalendar ? <div className="animate-pulse bg-[var(--border)] h-full w-full rounded" /> : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={chartData} margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                                    <XAxis dataKey="date" stroke="var(--text-dim)" fontSize={10} tickMargin={8} minTickGap={30} />
                                    <YAxis stroke="var(--text-dim)" fontSize={10} tickFormatter={(v) => `$${v}`} width={50} />
                                    <Tooltip contentStyle={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)', borderRadius: 8, fontSize: 12 }} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
                                    <ReferenceLine y={0} stroke="var(--text-dim)" />
                                    <Bar dataKey="pnl" name="Daily P&L">
                                        {chartData.map((entry, index) => (
                                            <cell key={`cell-${index}`} fill={entry.pnl >= 0 ? 'var(--green)' : 'var(--red)'} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
            </div>

            {/* SECTION 4: AI ANALYSIS PANEL */}
            <div>
                <h3 className="text-xs font-bold text-[var(--text-secondary)] mb-3 uppercase tracking-wider flex items-center gap-2">
                    <Zap size={14} className="text-[var(--cyan)]" /> AI Trading Mistakes Analysis
                </h3>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
                    <AiCard title="What You Do Well" icon={CheckCircle} color="var(--green)" points={mistakesData?.well} loading={loadingMistakes} />
                    <AiCard title="Your Mistakes" icon={XCircle} color="var(--red)" points={mistakesData?.mistakes} loading={loadingMistakes} />
                    <AiCard title="Recommendations" icon={Target} color="var(--cyan)" points={mistakesData?.recommendations} loading={loadingMistakes} />
                </div>
            </div>

            {/* SECTION 3: COIN PERFORMANCE TABLE */}
            <div className="card overflow-hidden">
                <div className="p-3 border-b border-[var(--border)] flex justify-between items-center bg-[rgba(0,0,0,0.2)]">
                    <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider">Coin Performance Breakdown</h3>
                </div>
                <div className="overflow-x-auto custom-scrollbar">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-[var(--bg-secondary)] border-b border-[var(--border)] text-[10px] uppercase text-[var(--text-dim)] tracking-wider">
                                <th className="p-3 pl-4">Coin</th>
                                <th className="p-3 text-right">Trades</th>
                                <th className="p-3 text-right">Win/Loss</th>
                                <th className="p-3 text-right">Win Rate</th>
                                <th className="p-3 text-right">Total P&L</th>
                                <th className="p-3 text-right">Avg Gain</th>
                                <th className="p-3 text-right">Avg Loss</th>
                                <th className="p-3 text-right">Best</th>
                                <th className="p-3 text-right">Worst</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loadingCoins ? (
                                Array(3).fill(0).map((_, i) => (
                                    <tr key={i} className="border-b border-[var(--border)]">
                                        <td colSpan="9" className="p-3 pl-4"><div className="animate-pulse bg-[var(--border)] h-4 w-full rounded" /></td>
                                    </tr>
                                ))
                            ) : coinsData?.length === 0 ? (
                                <tr><td colSpan="9" className="p-8 text-center text-[var(--text-dim)]">No coin data available</td></tr>
                            ) : (
                                coinsData?.map((c, i) => {
                                    const isTop = i < 3 && c.total_pnl > 0;
                                    const isWorst = i >= coinsData.length - 3 && c.total_pnl < 0;
                                    return (
                                        <tr key={c.symbol} className="border-b border-[var(--border)] hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                                            <td className="p-3 pl-4 font-bold text-[var(--text-primary)] flex items-center gap-2">
                                                {c.symbol} {isTop && <span title="Top 3 Performer">🏆</span>} {isWorst && <span title="Worst 3 Performer">⚠️</span>}
                                            </td>
                                            <td className="p-3 font-mono text-right">{c.trades}</td>
                                            <td className="p-3 font-mono text-xs text-right">{c.wins}/{c.losses}</td>
                                            <td className={`p-3 font-mono font-bold text-right ${c.win_rate >= 50 ? 'text-[var(--green)]' : 'text-[var(--red)]'}`}>{formatPercent(c.win_rate)}</td>
                                            <td className={`p-3 font-mono font-bold text-right ${c.total_pnl >= 0 ? 'text-[var(--green)]' : 'text-[var(--red)]'}`}>{formatMoney(c.total_pnl)}</td>
                                            <td className="p-3 font-mono text-[var(--green)] text-right">{formatMoney(c.avg_gain)}</td>
                                            <td className="p-3 font-mono text-[var(--red)] text-right">{formatMoney(c.avg_loss)}</td>
                                            <td className="p-3 font-mono text-[var(--green)] text-right">{formatMoney(c.best_trade)}</td>
                                            <td className="p-3 font-mono text-[var(--red)] text-right">{formatMoney(c.worst_trade)}</td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* SECTION 6: CALENDAR HEATMAP (Full 52 Weeks) */}
            <div className="card p-4 overflow-x-auto custom-scrollbar">
                <h3 className="text-xs font-bold text-[var(--text-secondary)] mb-4 uppercase tracking-wider flex items-center gap-2">
                    <CalendarIcon size={14} /> 52-Week P&L Heatmap
                </h3>
                <div className="flex gap-2 min-w-[700px]">
                    {/* Day Labels */}
                    <div className="flex flex-col gap-1 mt-6 text-[9px] text-[var(--text-dim)] uppercase tracking-widest font-mono">
                        <div className="h-3 leading-3" />
                        <div className="h-3 leading-3">Mon</div>
                        <div className="h-3 leading-3" />
                        <div className="h-3 leading-3">Wed</div>
                        <div className="h-3 leading-3" />
                        <div className="h-3 leading-3">Fri</div>
                        <div className="h-3 leading-3" />
                    </div>
                    {loadingCalendar ? <div className="animate-pulse bg-[var(--border)] h-24 w-full rounded" /> : (
                        <div className="flex flex-col flex-1">
                            {/* Simple Month Layout (Approximate) */}
                            <div className="flex justify-between text-[10px] text-[var(--text-dim)] mb-2 px-1">
                                <span>Jan</span><span>Feb</span><span>Mar</span><span>Apr</span><span>May</span><span>Jun</span>
                                <span>Jul</span><span>Aug</span><span>Sep</span><span>Oct</span><span>Nov</span><span>Dec</span>
                            </div>
                            <div className="grid grid-flow-col gap-1" style={{ gridTemplateRows: 'repeat(7, 1fr)', gridTemplateColumns: 'repeat(52, 1fr)' }}>
                                {heatmapDays.map((d, i) => {
                                    const maxPnl = Math.max(...heatmapDays.map(c => c.pnl ? Math.abs(c.pnl) : 0), 1);
                                    let bg = '#1a1f2e';
                                    if (d.pnl != null) {
                                        const intensity = Math.max(0.3, Math.abs(d.pnl) / maxPnl);
                                        bg = d.pnl >= 0 ? `rgba(0, 255, 136, ${intensity})` : `rgba(255, 71, 87, ${intensity})`;
                                    }
                                    return (
                                        <div 
                                            key={i} 
                                            title={`${d.date} | P&L: ${formatMoney(d.pnl)} | Trades: ${d.count}`}
                                            className="w-3 h-3 rounded-sm cursor-help hover:ring-1 ring-white transition-all"
                                            style={{ backgroundColor: bg }}
                                        />
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* SECTION 5: TRADE HISTORY TABLE */}
            <div className="card overflow-hidden">
                <div className="p-3 border-b border-[var(--border)] flex flex-col md:flex-row justify-between items-center gap-4 bg-[rgba(0,0,0,0.2)]">
                    <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider">Trade History</h3>
                    <div className="flex items-center gap-3">
                        <input type="text" placeholder="Filter Symbol..." value={filterSymbol} onChange={(e) => setFilterSymbol(e.target.value.toUpperCase())} className="input-field text-xs py-1.5 px-3 w-32" />
                        <select value={filterSide} onChange={(e) => setFilterSide(e.target.value)} className="input-field text-xs py-1.5 px-3">
                            <option value="">All Sides</option>
                            <option value="LONG">LONG</option>
                            <option value="SHORT">SHORT</option>
                        </select>
                        <button onClick={handleExport} className="btn btn-secondary flex items-center gap-2 py-1.5 px-3 text-xs">
                            <Download size={12} /> Export CSV
                        </button>
                    </div>
                </div>
                <div className="overflow-x-auto custom-scrollbar">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-[var(--bg-secondary)] border-b border-[var(--border)] text-[10px] uppercase text-[var(--text-dim)] tracking-wider">
                                <th className="p-3 pl-4">Date</th>
                                <th className="p-3">Symbol</th>
                                <th className="p-3">Side</th>
                                <th className="p-3 text-right">Entry</th>
                                <th className="p-3 text-right">Exit</th>
                                <th className="p-3 text-right">Qty</th>
                                <th className="p-3 text-right">P&L</th>
                                <th className="p-3 text-right">Hold Time</th>
                                <th className="p-3 text-center">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loadingTrades ? (
                                Array(5).fill(0).map((_, i) => (
                                    <tr key={i} className="border-b border-[var(--border)]">
                                        <td colSpan="9" className="p-3 pl-4"><div className="animate-pulse bg-[var(--border)] h-4 w-full rounded" /></td>
                                    </tr>
                                ))
                            ) : tradesData?.trades?.length === 0 ? (
                                <tr><td colSpan="9" className="p-8 text-center text-[var(--text-dim)]">No trades found matching filters</td></tr>
                            ) : (
                                tradesData?.trades?.map((t) => {
                                    const isLive = t.status === 'OPEN';
                                    const livePrice = isLive ? prices[t.symbol] : null;
                                    const displayExit = isLive && livePrice ? livePrice : t.exit_price;
                                    
                                    let displayPnl = t.pnl;
                                    let displayPnlPercent = t.pnl_percent;
                                    if (isLive && livePrice) {
                                        displayPnl = t.side === 'LONG' ? (livePrice - t.entry_price) * t.qty : (t.entry_price - livePrice) * t.qty;
                                        const invested = t.entry_price * t.qty;
                                        displayPnlPercent = invested > 0 ? (displayPnl / invested) * 100 : 0;
                                    }

                                    return (
                                        <tr key={t.id} className="border-b border-[var(--border)] hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                                            <td className="p-3 pl-4 font-mono text-xs text-[var(--text-secondary)] whitespace-nowrap">
                                                {new Date(t.entry_time).toLocaleString()}
                                            </td>
                                            <td className="p-3 font-bold text-xs">{t.symbol}</td>
                                            <td className={`p-3 font-bold text-[10px] ${t.side === 'LONG' ? 'text-[var(--green)]' : 'text-[var(--red)]'}`}>{t.side}</td>
                                            <td className="p-3 font-mono text-xs text-[var(--text-secondary)] text-right">{t.entry_price}</td>
                                            <td className="p-3 font-mono text-xs text-[var(--text-secondary)] text-right">
                                                {displayExit || '-'} {isLive && livePrice && <span className="text-[9px] text-[var(--text-dim)] ml-1">(live)</span>}
                                            </td>
                                            <td className="p-3 font-mono text-xs text-right">{t.qty}</td>
                                            <td className="p-3 font-mono text-xs text-right">
                                                {displayPnl != null ? (
                                                    <div className={`flex items-center justify-end gap-1 font-bold ${isLive ? 'text-[#eab308]' : (displayPnl >= 0 ? 'text-[var(--green)]' : 'text-[var(--red)]')}`}>
                                                        {displayPnl >= 0 ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
                                                        {formatMoney(Math.abs(displayPnl))}
                                                        <span className="text-[9px] ml-1 opacity-80">({formatPercent(displayPnlPercent)})</span>
                                                    </div>
                                                ) : '-'}
                                            </td>
                                            <td className="p-3 font-mono text-xs text-[var(--text-dim)] text-right">
                                                {t.hold_time_mins ? `${Math.round(t.hold_time_mins)}m` : '-'}
                                            </td>
                                            <td className="p-3 text-center">
                                                <span className={`px-2 py-0.5 rounded text-[9px] font-bold tracking-wider ${
                                                    t.status === 'CLOSED' ? 'bg-[rgba(0,255,136,0.1)] text-[var(--green)]' : 'bg-[rgba(234,179,8,0.1)] text-[#eab308]'
                                                }`}>
                                                    {t.status}
                                                </span>
                                            </td>
                                        </tr>
                                    )
                                })
                            )}
                        </tbody>
                    </table>
                </div>
                {/* Pagination */}
                <div className="p-3 border-t border-[var(--border)] flex justify-between items-center bg-[rgba(0,0,0,0.2)]">
                    <span className="text-[10px] text-[var(--text-dim)] uppercase tracking-wider">
                        Showing page {page} ({tradesData?.total || 0} total)
                    </span>
                    <div className="flex gap-2">
                        <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="btn btn-secondary py-1 px-3 text-xs">Previous</button>
                        <button disabled={!tradesData?.trades || tradesData.trades.length < 50} onClick={() => setPage(p => p + 1)} className="btn btn-secondary py-1 px-3 text-xs">Next</button>
                    </div>
                </div>
            </div>

        </div>
    );
}

function StatCard({ title, value, subtitle, valueColor, icon: Icon, loading }) {
    return (
        <div className="card p-3 flex flex-col justify-center gap-1.5" style={{ height: '80px' }}>
            <div className="flex justify-between items-center w-full">
                <span className="text-[10px] font-bold text-[var(--text-dim)] uppercase tracking-widest">{title}</span>
                <Icon size={12} className="text-[var(--text-secondary)] opacity-30" />
            </div>
            {loading ? (
                <div className="animate-pulse bg-[var(--border)] h-6 w-16 rounded mt-1" />
            ) : (
                <div className="flex items-end gap-1.5">
                    <span className="text-lg font-bold font-mono tracking-tight leading-none" style={{ color: valueColor || 'var(--text-primary)' }}>
                        {value}
                    </span>
                    {subtitle && (
                        <span className="text-[9px] font-mono mb-0.5" style={{ color: valueColor || 'var(--text-secondary)' }}>
                            {subtitle}
                        </span>
                    )}
                </div>
            )}
        </div>
    );
}

function AiCard({ title, icon: Icon, color, points, loading }) {
    const displayPoints = Array.isArray(points) ? [...points] : [];
    while (displayPoints.length < 5) displayPoints.push(null);
    
    return (
        <div className="card flex flex-col h-full" style={{ border: `1px solid rgba(255,255,255,0.03)`, boxShadow: `0 -2px 10px -5px ${color}33, 0 4px 6px -1px rgba(0,0,0,0.1)` }}>
            <div className="p-3 border-b border-[var(--border)] flex items-center gap-2" style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}>
                <Icon size={14} style={{ color }} />
                <h3 className="text-[11px] font-bold tracking-wider uppercase" style={{ color }}>{title}</h3>
            </div>
            <div className="p-4 flex-1">
                <ul className="space-y-3">
                    {loading ? Array(5).fill(0).map((_, i) => (
                        <li key={i} className="flex items-center gap-2"><span className="w-1 h-1 rounded-full bg-[var(--border)]" /><div className="animate-pulse bg-[var(--border)] h-2 w-full rounded opacity-30" style={{ maxWidth: `${80 - i*10}%` }} /></li>
                    )) : displayPoints.map((pt, i) => (
                        pt ? (
                            <li key={i} className="text-[11px] text-[var(--text-secondary)] flex items-start gap-2 leading-relaxed">
                                <span className="mt-1.5 w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: color, boxShadow: `0 0 5px ${color}` }} />
                                {pt}
                            </li>
                        ) : (
                            <li key={i} className="flex items-center gap-2">
                                <span className="w-1 h-1 rounded-full flex-shrink-0 bg-[var(--border)]" />
                                <div className="bg-[var(--border)] h-1.5 w-full rounded opacity-10" style={{ maxWidth: `${70 - i*5}%` }} />
                            </li>
                        )
                    ))}
                </ul>
            </div>
        </div>
    );
}
