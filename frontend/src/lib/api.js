import axios from 'axios'
import { QueryClient } from '@tanstack/react-query'

export const api = axios.create({
    baseURL: '/api/v1',
    timeout: 300000,
    headers: { 'Content-Type': 'application/json' },
})

// Separate fast instance for polling (short timeout so it never blocks)
export const pollApi = axios.create({
    baseURL: '/api/v1',
    timeout: 5000,
    headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
    (res) => res,
    (err) => {
        console.error('API Error:', err.response?.status, err.message)
        return Promise.reject(err)
    }
)

export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 15_000,
            retry: 1,
            refetchOnWindowFocus: false,
        },
    },
})

// Helper hooks (to be used in components)
export const API = {
    getDashboardStats: () => api.get('/dashboard/stats').then(r => r.data),
    getCoins: () => api.get('/coins').then(r => r.data),
    getCoinPrice: (symbol) => api.get(`/coins/${encodeURIComponent(symbol)}/price`).then(r => r.data),
    getLiveSignals: () => api.get('/signals/live').then(r => r.data),
    getSignal: (id) => api.get(`/signals/${id}`).then(r => r.data),
    triggerScanNow: () => api.post('/signals/scan-now').then(r => r.data),
    getSignalHistory: (params) => api.get('/signals/history', { params }).then(r => r.data),
    clearSignalHistory: () => api.delete('/signals/history').then(r => r.data),
    getGenerationStatus: () => api.get('/signals/generation-status').then(r => r.data),
    toggleGeneration: (enabled) => api.post('/signals/toggle-generation', { enabled }).then(r => r.data),
    getBacktestResults: (params) => api.get('/backtest/results', { params }).then(r => r.data),
    runBacktest: (body) => api.post('/backtest/run', body).then(r => r.data),
    runStrategyBacktest: (id, data) => api.post(`/backtest/run-strategy/${id}`, data).then(r => r.data),
    runAllBacktests: () => api.post('/backtest/run-all').then(r => r.data),
    getBacktestProgress: (jobId) => pollApi.get(`/backtest/progress/${jobId}`).then(r => r.data),
    getBacktestTable: (strategyId) => api.get(`/backtest/results/table`, { params: { strategy_id: strategyId } }).then(r => r.data),
    assignBulkStrategies: (body) => api.post(`/backtest/assign-bulk`, body).then(r => r.data),
    getBacktestSummary: (strategyId) => api.get(`/backtest/summary/${strategyId}`).then(r => r.data),
    getStrategies: () => api.get('/strategies').then(r => r.data),
    getAllStrategies: () => api.get('/strategies/all').then(r => r.data),
    createStrategy: (body) => api.post('/strategies', body).then(r => r.data),
    reactivateStrategy: (id) => api.post(`/strategies/${id}/reactivate`).then(r => r.data),
    deleteStrategy: (id) => api.delete(`/strategies/${id}`).then(r => r.data),
    convertPineScript: (id) => api.post(`/strategies/${id}/convert-pine`).then(r => r.data),
    getPythonCode: (id) => api.get(`/strategies/${id}/python-code`).then(r => r.data),
    getStrategyCions: (id) => api.get(`/strategies/${id}/coins`).then(r => r.data),
    getSettings: () => api.get('/settings').then(r => r.data),
    saveSettings: (body) => api.post('/settings', body).then(r => r.data),
    syncCoins: () => api.post('/coins/sync').then(r => r.data),
    getDeepAnalysis: (symbol) => api.get(`/analysis/${encodeURIComponent(symbol)}`).then(r => r.data),
    postAnalysisChat: (formData) => api.post('/analysis/chat', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    }).then(r => r.data),
    getFuturesLongShort: (params) => api.get('/futures/top-long-short', { params }).then(r => r.data),
    getJournalTrades: (params) => api.get('/journal/trades', { params }).then(r => r.data),
    getJournalSummary: () => api.get('/journal/summary').then(r => r.data),
    getJournalCoins: () => api.get('/journal/coins').then(r => r.data),
    getJournalMistakes: () => api.get('/journal/mistakes').then(r => r.data),
    refreshJournal: () => api.post('/journal/refresh').then(r => r.data),
    getJournalCalendar: () => api.get('/journal/calendar').then(r => r.data),
    evaluateSignalWithAI: (id, severity = 'BALANCED') => api.post(`/signals/evaluate/${id}`, { severity }).then(r => r.data),
}
