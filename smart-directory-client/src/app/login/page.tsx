'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Eye, EyeOff, LogIn } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass]   = useState(false)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')

  const handleLogin = async () => {
    if (!username || !password) { setError('Completa todos los campos'); return }
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (res.ok) {
        router.push('/')
        router.refresh()
      } else {
        const data = await res.json()
        setError(data.error || 'Credenciales incorrectas')
      }
    } catch {
      setError('Error de conexión. Intenta de nuevo.')
    }
    setLoading(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleLogin()
  }

  return (
    <div className="min-h-screen bg-pearl flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-violet rounded-xl flex items-center justify-center mb-4 shadow-lg">
            <span className="font-display text-sm text-pearl font-bold tracking-wider">ASD</span>
          </div>
          <h1 className="font-display text-navy text-sm tracking-widest uppercase">
            Agexport Smart Directory
          </h1>
          <p className="text-xs text-dark/35 mt-1">Panel de Administración</p>
        </div>

        {/* Card */}
        <div className="bg-pearl border border-navy/10 rounded-2xl shadow-xl p-6 space-y-4">

          {/* Usuario */}
          <div>
            <label className="block text-xs font-display text-dark/40 tracking-widest mb-1.5">
              USUARIO
            </label>
            <input
              type="text"
              value={username}
              onChange={function(e) { setUsername(e.target.value) }}
              onKeyDown={handleKeyDown}
              placeholder="admin"
              autoComplete="username"
              className="w-full bg-navy/5 border border-navy/10 rounded-lg px-3 py-2.5 text-dark text-sm focus:outline-none focus:border-violet transition-colors placeholder:text-dark/20"
            />
          </div>

          {/* Contraseña */}
          <div>
            <label className="block text-xs font-display text-dark/40 tracking-widest mb-1.5">
              CONTRASEÑA
            </label>
            <div className="relative">
              <input
                type={showPass ? 'text' : 'password'}
                value={password}
                onChange={function(e) { setPassword(e.target.value) }}
                onKeyDown={handleKeyDown}
                placeholder="••••••••"
                autoComplete="current-password"
                className="w-full bg-navy/5 border border-navy/10 rounded-lg px-3 py-2.5 pr-10 text-dark text-sm focus:outline-none focus:border-violet transition-colors placeholder:text-dark/25"
              />
              <button
                type="button"
                onClick={function() { setShowPass(!showPass) }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-dark/25 hover:text-dark/60 transition-colors"
              >
                {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <p className="text-xs text-red-500 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          {/* Submit */}
          <button
            onClick={handleLogin}
            disabled={loading}
            className="w-full bg-violet hover:bg-violet/80 disabled:opacity-60 text-pearl py-2.5 rounded-lg text-sm font-display tracking-wide transition-colors flex items-center justify-center gap-2 mt-2"
          >
            {loading ? (
              <span className="animate-pulse">VERIFICANDO...</span>
            ) : (
              <>
                <LogIn size={14} />
                INGRESAR
              </>
            )}
          </button>
        </div>

        <p className="text-center text-xs text-dark/20 mt-6 font-display">
          Wais Solutions © {new Date().getFullYear()}
        </p>
      </div>
    </div>
  )
}