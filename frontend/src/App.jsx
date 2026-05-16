import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { queryClient } from './lib/api'
import { usePriceSocket } from './lib/socket'

import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'

import Dashboard from './pages/Dashboard'
import BacktestResults from './pages/BacktestResults'
import StrategyLibrary from './pages/StrategyLibrary'
import Screener from './pages/Screener'
import SignalHistory from './pages/SignalHistory'
import DeepAnalysis from './pages/DeepAnalysis'
import FuturesAnalysis from './pages/FuturesAnalysis'
import TradingJournal from './pages/TradingJournal'
import Settings from './pages/Settings'
import AutoTrader from './pages/AutoTrader'
import SignalEngine from './pages/SignalEngine'
import ElitePicks from './pages/ElitePicks'

import { useQuery } from '@tanstack/react-query'
import { API } from './lib/api'

import { useLocation } from 'react-router-dom'

function AppShell() {
  const { prices } = usePriceSocket()
  const btcPrice = prices['BTC/USDT']

  const { data: stats } = useQuery({
    queryKey: ['dashboardStats'],
    queryFn: API.getDashboardStats,
    refetchInterval: 30000,
    retry: 1,
  })

  const sidebarStats = {
    totalCoins: stats?.total_coins_scanning || 0,
    activeSignals: stats?.active_signals || 0,
    todayWinRate: stats?.today_win_rate || 0,
    botStatus: stats?.bot_status || 'stopped',
  }

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--bg-primary)' }}>
      <Sidebar stats={sidebarStats} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <TopBar btcPrice={btcPrice} />
        <main className="grid-overlay" style={{ flex: 1, overflow: 'auto', padding: 16, background: 'var(--bg-primary)' }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/backtest" element={<BacktestResults />} />
            <Route path="/strategies" element={<StrategyLibrary />} />
            <Route path="/screener" element={<Screener />} />
            <Route path="/signals" element={<SignalHistory />} />
            <Route path="/analysis" element={<DeepAnalysis />} />
            <Route path="/deep-analysis" element={<DeepAnalysis />} />
            <Route path="/futures" element={<FuturesAnalysis />} />
            <Route path="/journal" element={<TradingJournal />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/autotrader" element={<AutoTrader />} />
            <Route path="/signal-engine" element={<SignalEngine />} />
            <Route path="/elite-picks" element={<ElitePicks />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell />
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border)',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
            },
            success: { iconTheme: { primary: 'var(--green)', secondary: 'var(--bg-card)' } },
            error: { iconTheme: { primary: 'var(--red)', secondary: 'var(--bg-card)' } },
          }}
        />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
