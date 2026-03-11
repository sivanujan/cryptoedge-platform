export default function LoadingSpinner({ size = 32, text = 'Loading...' }) {
    return (
        <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', gap: 16, padding: 40,
        }}>
            <div style={{
                width: size, height: size,
                border: `2px solid var(--border)`,
                borderTop: `2px solid var(--cyan)`,
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
                boxShadow: '0 0 12px var(--cyan-glow)',
            }} />
            {text && (
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-dim)', letterSpacing: '0.08em' }}>
                    {text}
                </span>
            )}
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    )
}
