import React, { useState, useRef, useEffect, memo, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { 
    Search, Zap, TrendingUp, Brain, ImageIcon,
    Loader2, ChevronRight, Sparkles, Plus, Send
} from 'lucide-react'
import { API } from '../lib/api'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'

// --- HELPERS ---
const getRecommendationColor = (rec) => {
    if (rec?.includes('STRONG BUY')) return 'var(--green)'
    if (rec?.includes('BUY')) return 'var(--green-dim)'
    if (rec?.includes('STRONG SELL')) return 'var(--red)'
    if (rec?.includes('SELL')) return 'var(--red-dim)'
    if (rec?.includes('LONG')) return 'var(--green-dim)'
    if (rec?.includes('SHORT')) return 'var(--red-dim)'
    return 'var(--text-dim)'
}

const formatPrice = (p) => typeof p === 'number' ? p.toFixed(p < 1 ? 6 : 2) : p

// --- COMPONENTS ---

const ChatMessage = memo(({ msg }) => {
    const isAssistant = msg.role === 'assistant'
    return (
        <div className="ai-fade-in" style={{ display: 'flex', flexDirection: 'column', alignItems: isAssistant ? 'flex-start' : 'flex-end', gap: 8, marginBottom: 24, width: '100%' }}>
            <div style={{ maxWidth: '85%', padding: '16px 20px', borderRadius: 20, background: isAssistant ? 'rgba(255,255,255,0.03)' : 'var(--cyan)', color: isAssistant ? 'var(--text-primary)' : 'black', border: isAssistant ? '1px solid rgba(255,255,255,0.05)' : 'none', fontSize: 15, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                {!isAssistant && msg.image && <img src={msg.image} alt="Chart" style={{ maxWidth: '100%', borderRadius: 12, marginBottom: 12, display: 'block' }} />}
                {msg.content}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', fontWeight: 700, margin: '0 10px' }}>{isAssistant ? 'CRYPTOEDGE AI' : 'YOU'}</div>
        </div>
    )
})

const AnalysisRichCard = memo(({ data }) => {
    if (!data) return null
    const tech = data.technical_framework
    return (
        <div className="card ai-fade-in" style={{ width: '100%', padding: 0, overflow: 'hidden', border: '1px solid rgba(0, 229, 255, 0.2)', background: 'rgba(0,0,0,0.4)', marginBottom: 30 }}>
            <div style={{ padding: '16px 24px', background: 'linear-gradient(90deg, rgba(0, 229, 255, 0.1) 0%, transparent 100%)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Zap size={18} color="var(--cyan)" />
                    <span style={{ fontWeight: 800, fontSize: 16 }}>{data.symbol} DEEP SCAN</span>
                </div>
                <div style={{ padding: '4px 12px', background: getRecommendationColor(data.recommendation) + '22', color: getRecommendationColor(data.recommendation), borderRadius: 8, fontSize: 12, fontWeight: 900 }}>{data.recommendation}</div>
            </div>
            <div style={{ padding: 24 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20, marginBottom: 24 }}>
                    <div style={{ padding: 16, background: 'rgba(255,255,255,0.02)', borderRadius: 12, textAlign: 'center' }}>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', fontWeight: 800, marginBottom: 4 }}>CONFIDENCE</div>
                        <div style={{ fontSize: 24, fontWeight: 900, color: 'var(--cyan)' }}>{data.confidence}%</div>
                    </div>
                    <div style={{ padding: 16, background: 'rgba(255,255,255,0.02)', borderRadius: 12, textAlign: 'center' }}>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', fontWeight: 800, marginBottom: 4 }}>RSI</div>
                        <div style={{ fontSize: 24, fontWeight: 900, color: tech?.metrics?.rsi?.value > 50 ? 'var(--green)' : 'var(--red)' }}>{tech?.metrics?.rsi?.value}</div>
                    </div>
                    <div style={{ padding: 16, background: 'rgba(255,255,255,0.02)', borderRadius: 12, textAlign: 'center' }}>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', fontWeight: 800, marginBottom: 4 }}>TREND</div>
                        <div style={{ fontSize: 14, fontWeight: 900 }}>{tech?.metrics?.ema?.stack}</div>
                    </div>
                </div>
                <div style={{ marginBottom: 24 }}>
                    <div style={{ fontSize: 11, color: 'var(--cyan)', fontWeight: 800, marginBottom: 8, letterSpacing: '0.1em' }}>AI INSIGHT</div>
                    <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6 }}>{data.ai_analysis?.insight}</p>
                </div>
            </div>
        </div>
    )
})

// CRITICAL: Local state input to prevent entire page re-rendering while typing
const SearchBar = memo(({ onSubmit, onFileClick, initialValue = '' }) => {
    const [localQuery, setLocalQuery] = useState(initialValue)
    
    const handleSubmit = (e) => {
        e.preventDefault()
        onSubmit(localQuery)
        setLocalQuery('')
    }

    return (
        <form onSubmit={handleSubmit} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 24, padding: '8px 20px', display: 'flex', alignItems: 'center', gap: 15, boxShadow: '0 10px 40px rgba(0,0,0,0.2)' }}>
            <Search size={20} color="var(--text-dim)" />
            <input 
                type="text" 
                placeholder="Analyze coin or ask AI..." 
                style={{ flex: 1, background: 'transparent', border: 'none', color: 'white', fontSize: 18, outline: 'none', padding: '12px 0' }}
                value={localQuery}
                onChange={(e) => setLocalQuery(e.target.value)}
            />
            <div style={{ display: 'flex', gap: 10 }}>
                <button type="button" onClick={onFileClick} className="hover-bright" style={{ background: 'rgba(255,255,255,0.05)', border: 'none', padding: 10, borderRadius: 12, cursor: 'pointer', color: 'var(--text-dim)' }}>
                    <ImageIcon size={20} />
                </button>
                <button type="submit" style={{ background: 'var(--cyan)', color: 'black', border: 'none', padding: '10px 20px', borderRadius: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Sparkles size={18} /> Analyze
                </button>
            </div>
        </form>
    )
})

const ChatInput = memo(({ onSubmit, onFileClick }) => {
    const [localQuery, setLocalQuery] = useState('')
    
    const handleSubmit = (e) => {
        e.preventDefault()
        if (!localQuery.trim()) return
        onSubmit(localQuery)
        setLocalQuery('')
    }

    return (
        <form onSubmit={handleSubmit} style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 16, padding: '6px 16px' }}>
            <button type="button" onClick={onFileClick} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}><Plus size={20} /></button>
            <input type="text" placeholder="Ask AI..." style={{ flex: 1, background: 'transparent', border: 'none', color: 'white', padding: '12px 0', outline: 'none' }} value={localQuery} onChange={(e) => setLocalQuery(e.target.value)} />
            <button type="submit" style={{ background: localQuery.trim() ? 'var(--cyan)' : 'transparent', color: localQuery.trim() ? 'black' : 'var(--text-dim)', border: 'none', width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}><Send size={16} /></button>
        </form>
    )
})

export default function DeepAnalysis() {
    const [searchParams] = useSearchParams()
    const urlCoin = searchParams.get('coin')

    const [view, setView] = useState(urlCoin ? 'results' : 'landing')
    const [messages, setMessages] = useState([])
    const [isTyping, setIsTyping] = useState(false)
    const [selectedImage, setSelectedImage] = useState(null)
    const [imagePreview, setImagePreview] = useState(null)
    const fileInputRef = useRef(null)
    const chatEndRef = useRef(null)
    const [activeCoin, setActiveCoin] = useState(urlCoin || '')

    const { data: analysis, isLoading: isAnalyzing } = useQuery({
        queryKey: ['deepAnalysis', activeCoin],
        queryFn: () => API.getDeepAnalysis(activeCoin),
        enabled: !!activeCoin && view === 'results',
        retry: false
    })

    useEffect(() => {
        if (chatEndRef.current) chatEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }, [messages, isTyping])

    const handleImageChange = (e) => {
        const file = e.target.files[0]
        if (file) {
            setSelectedImage(file)
            const reader = new FileReader()
            reader.onloadend = () => setImagePreview(reader.result)
            reader.readAsDataURL(file)
            setView('results')
        }
    }

    const triggerDeepScan = useCallback((symbol) => {
        const cleanSymbol = symbol.trim().toUpperCase()
        setActiveCoin(cleanSymbol)
        setView('results')
        setMessages(prev => [...prev, { role: 'user', content: `Analyze ${cleanSymbol}` }])
    }, [])

    const handleAnalysisSubmit = async (query) => {
        const currentImage = selectedImage
        setSelectedImage(null)
        setImagePreview(null)

        const isSymbolOnly = /^[A-Z1-9]{2,10}$/.test(query.trim().toUpperCase())
        if (isSymbolOnly && !currentImage) {
            triggerDeepScan(query)
            return
        }

        setMessages(prev => [...prev, { role: 'user', content: query, image: imagePreview }])
        setView('results')
        setIsTyping(true)

        try {
            const formData = new FormData()
            formData.append('query', query)
            if (currentImage) formData.append('image', currentImage)
            const res = await API.postAnalysisChat(formData)
            setMessages(prev => [...prev, { role: 'assistant', content: res.response, type: res.type }])
        } catch (err) {
            toast.error("AI Error")
        } finally {
            setIsTyping(false)
        }
    }

    return (
        <div style={{ maxWidth: 1000, margin: '0 auto', height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
            {view === 'landing' ? (
                <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 40 }}>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 15, marginBottom: 10 }}>
                            <div style={{ width: 60, height: 60, borderRadius: '22%', background: 'linear-gradient(135deg, var(--cyan) 0%, var(--purple) 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 30px rgba(0, 229, 255, 0.2)' }}>
                                <Brain size={32} color="white" />
                            </div>
                            <h1 style={{ fontSize: 48, fontWeight: 900, margin: 0, letterSpacing: '-0.02em' }}>CryptoEdge <span style={{ color: 'var(--cyan)' }}>AI</span></h1>
                        </div>
                        <p style={{ color: 'var(--text-dim)', fontSize: 18 }}>Deep technical analysis & real-time chart vision.</p>
                    </div>
                    <div style={{ width: '100%', maxWidth: 700 }}>
                        <SearchBar onSubmit={handleAnalysisSubmit} onFileClick={() => fileInputRef.current?.click()} />
                    </div>
                    <div style={{ display: 'flex', gap: 15, flexWrap: 'wrap', justifyContent: 'center' }}>
                        {['BTC', 'ETH', 'SOL', 'XRP'].map(coin => (
                            <button key={coin} onClick={() => triggerDeepScan(coin)} className="hover-bright" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)', padding: '8px 16px', borderRadius: 12, color: 'var(--text-dim)', fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>{coin} Analysis</button>
                        ))}
                    </div>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div style={{ padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <button onClick={() => { setView('landing'); setMessages([]); setActiveCoin(''); }} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}>
                                <ChevronRight size={18} style={{ transform: 'rotate(180deg)' }} />
                            </button>
                            <h2 style={{ fontSize: 16, fontWeight: 800, margin: 0 }}>AI Analysis Hub</h2>
                        </div>
                        {activeCoin && <span style={{ fontSize: 11, fontWeight: 800, color: 'var(--cyan)', background: 'rgba(0,229,255,0.1)', padding: '4px 10px', borderRadius: 8 }}>{activeCoin}</span>}
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', padding: '20px 0' }} className="custom-scrollbar">
                        {messages.map((m, i) => <ChatMessage key={i} msg={m} />)}
                        {activeCoin && isAnalyzing && <div style={{ padding: 20, textAlign: 'center' }}><Loader2 className="animate-spin" size={24} color="var(--cyan)" style={{ margin: '0 auto 10px' }} /><div style={{ fontSize: 13, color: 'var(--text-dim)' }}>Scanning Market Data...</div></div>}
                        {activeCoin && analysis && !isAnalyzing && <AnalysisRichCard data={analysis} />}
                        {isTyping && <div className="ai-fade-in" style={{ display: 'flex', gap: 6, padding: 10 }}>
                            <div className="typing-dot" />
                            <div className="typing-dot" />
                            <div className="typing-dot" />
                        </div>}
                        <div ref={chatEndRef} />
                    </div>
                    <div style={{ padding: '20px 0' }}>
                        {imagePreview && (
                            <div style={{ padding: 10, background: 'rgba(255,255,255,0.05)', borderRadius: '16px 16px 0 0', border: '1px solid rgba(255,255,255,0.1)', borderBottom: 'none', display: 'flex', alignItems: 'center', gap: 10 }}>
                                <div style={{ position: 'relative' }}>
                                    <img src={imagePreview} style={{ width: 60, height: 40, objectFit: 'cover', borderRadius: 6 }} />
                                    <button onClick={() => { setSelectedImage(null); setImagePreview(null); }} style={{ position: 'absolute', top: -5, right: -5, background: 'var(--red)', color: 'white', border: 'none', borderRadius: '50%', width: 16, height: 16, fontSize: 10, cursor: 'pointer' }}>×</button>
                                </div>
                                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-dim)' }}>Chart Ready...</span>
                            </div>
                        )}
                        <ChatInput onSubmit={handleAnalysisSubmit} onFileClick={() => fileInputRef.current?.click()} />
                    </div>
                </div>
            )}
            <input type="file" ref={fileInputRef} hidden accept="image/*" onChange={handleImageChange} />
        </div>
    )
}