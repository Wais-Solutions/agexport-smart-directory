'use client'
import { useState, useEffect, useMemo } from 'react'
import { Search, X, RefreshCw, Trash2, KeyRound, Check, Eye, EyeOff, ShieldCheck, User } from 'lucide-react'

const AUTH_API = process.env.NEXT_PUBLIC_API_URL + '/auth'

// ─────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────
type AppUser = {
  _id: string
  username: string
  role: 'admin' | 'partner'
  partner_name: string | null
  partner_id: string | null
}

// ─────────────────────────────────────────────────────────────────
// PasswordModal
// ─────────────────────────────────────────────────────────────────
function PasswordModal({
  user,
  onClose,
  onSaved,
}: {
  user: AppUser
  onClose: () => void
  onSaved: () => void
}) {
  const [newPassword, setNewPassword]   = useState('')
  const [showPass, setShowPass]         = useState(false)
  const [saving, setSaving]             = useState(false)
  const [error, setError]               = useState('')

  const handleSave = async () => {
    setError('')
    if (newPassword.length < 6) {
      setError('Mínimo 6 caracteres')
      return
    }
    setSaving(true)
    try {
      const res = await fetch(`${AUTH_API}/users/${user.username}/password`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_password: newPassword }),
      })
      if (!res.ok) {
        const data = await res.json()
        setError(data.detail || 'Error al actualizar')
        return
      }
      onSaved()
      onClose()
    } catch {
      setError('Error de conexión')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-dark/20 backdrop-blur-sm">
      <div className="bg-pearl border border-navy/15 rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">

        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-violet/10 border border-violet/20 flex items-center justify-center">
              <KeyRound size={14} className="text-violet" />
            </div>
            <div>
              <p className="font-display text-xs text-navy tracking-widest">NUEVA CONTRASEÑA</p>
              <p className="text-xs text-dark/40 mt-0.5">{user.username}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-dark/25 hover:text-dark/50 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Input */}
        {/* Honeypot: engaña al autofill a rellenar estos campos ocultos en vez del real */}
        <div aria-hidden="true" className="absolute w-0 h-0 overflow-hidden opacity-0 pointer-events-none">
          <input type="text" name="username_fake" tabIndex={-1} readOnly />
          <input type="password" name="password_fake" tabIndex={-1} readOnly />
        </div>
        <div className="relative">
          <input
            type={showPass ? 'text' : 'password'}
            value={newPassword}
            onChange={function(e) { setNewPassword(e.target.value) }}
            onKeyDown={function(e) { if (e.key === 'Enter') handleSave() }}
            placeholder="Nueva contraseña..."
            autoFocus
            autoComplete="new-password"
            name={`pwd-${user.username}-${Date.now()}`}
            className="w-full pr-10 pl-3 py-2.5 text-sm border border-navy/15 rounded-lg bg-pearl text-dark/80 focus:outline-none focus:border-violet transition-colors placeholder:text-dark/25 font-mono"
          />
          <button
            type="button"
            onClick={function() { setShowPass(!showPass) }}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-dark/25 hover:text-dark/50 transition-colors"
          >
            {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>

        {error && (
          <p className="text-xs text-red-400 mt-2">{error}</p>
        )}

        {/* Actions */}
        <div className="flex gap-2 mt-5">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 text-xs font-display border border-navy/15 text-dark/40 hover:text-dark/60 rounded-lg transition-colors"
          >
            CANCELAR
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !newPassword}
            className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-display bg-violet text-pearl rounded-lg hover:bg-violet/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {saving ? (
              <RefreshCw size={11} className="animate-spin" />
            ) : (
              <Check size={11} />
            )}
            {saving ? 'GUARDANDO...' : 'GUARDAR'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// UserRow
// ─────────────────────────────────────────────────────────────────
function UserRow({
  user,
  onChangePassword,
  onDelete,
}: {
  user: AppUser
  onChangePassword: (user: AppUser) => void
  onDelete: (user: AppUser) => void
}) {
  const isAdmin = user.role === 'admin'

  return (
    <div className="flex items-center gap-4 px-5 py-3.5 border border-navy/10 rounded-xl bg-pearl hover:border-navy/20 hover:bg-navy/[0.015] transition-all group">

      {/* Role icon */}
      <div className={
        'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ' +
        (isAdmin
          ? 'bg-violet/12 border border-violet/20'
          : 'bg-navy/5 border border-navy/10'
        )
      }>
        {isAdmin
          ? <ShieldCheck size={14} className="text-violet" />
          : <User size={14} className="text-dark/35" />
        }
      </div>

      {/* Username */}
      <div className="w-52 shrink-0">
        <p className="text-sm text-dark/80 font-mono">{user.username}</p>
        <span className={
          'text-xs font-display tracking-wide ' +
          (isAdmin ? 'text-violet/60' : 'text-dark/25')
        }>
          {user.role.toUpperCase()}
        </span>
      </div>

      {/* Partner name */}
      <div className="flex-1 min-w-0">
        {user.partner_name ? (
          <p className="text-xs text-dark/50 truncate">{user.partner_name}</p>
        ) : (
          <p className="text-xs text-dark/20 italic">—</p>
        )}
      </div>

      {/* Password placeholder */}
      <div className="w-32 shrink-0">
        <p className="text-xs text-dark/25 font-mono tracking-widest">••••••••••••</p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button
          onClick={function() { onChangePassword(user) }}
          title="Cambiar contraseña"
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-display border border-navy/15 text-dark/40 hover:text-violet hover:border-violet/30 hover:bg-violet/5 rounded-lg transition-colors"
        >
          <KeyRound size={11} />
          CONTRASEÑA
        </button>

        {!isAdmin && (
          <button
            onClick={function() { onDelete(user) }}
            title="Eliminar usuario"
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-display border border-navy/10 text-dark/30 hover:text-red-400 hover:border-red-200 hover:bg-red-50 rounded-lg transition-colors"
          >
            <Trash2 size={11} />
          </button>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────
export default function TabUsuarios() {
  const [users, setUsers]                       = useState<AppUser[]>([])
  const [loading, setLoading]                   = useState(true)
  const [search, setSearch]                     = useState('')
  const [roleFilter, setRoleFilter]             = useState<'' | 'admin' | 'partner'>('')
  const [editingUser, setEditingUser]           = useState<AppUser | null>(null)
  const [savedUsername, setSavedUsername]       = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${AUTH_API}/users`)
      const data = await res.json()
      // admin siempre primero, luego partners ordenados por username
      const sorted = (data as AppUser[]).sort(function(a, b) {
        if (a.role === 'admin' && b.role !== 'admin') return -1
        if (b.role === 'admin' && a.role !== 'admin') return 1
        return a.username.localeCompare(b.username)
      })
      setUsers(sorted)
    } catch {
      setUsers([])
    }
    setLoading(false)
  }

  useEffect(function() { load() }, [])

  const handleDelete = async (user: AppUser) => {
    if (!confirm(`¿Eliminar el usuario "${user.username}"? Esta acción no se puede deshacer.`)) return
    try {
      const res = await fetch(`${AUTH_API}/users/${user.username}`, { method: 'DELETE' })
      if (res.ok) {
        setUsers(function(prev) { return prev.filter(function(u) { return u._id !== user._id }) })
      }
    } catch { /* silencioso */ }
  }

  const handlePasswordSaved = () => {
    if (editingUser) {
      setSavedUsername(editingUser.username)
      setTimeout(function() { setSavedUsername(null) }, 2500)
    }
  }

  const filtered = useMemo(function() {
    return users.filter(function(u) {
      const s = search.toLowerCase()
      if (s) {
        const inUsername    = u.username.toLowerCase().includes(s)
        const inPartnerName = (u.partner_name ?? '').toLowerCase().includes(s)
        if (!inUsername && !inPartnerName) return false
      }
      if (roleFilter && u.role !== roleFilter) return false
      return true
    })
  }, [users, search, roleFilter])

  const adminCount   = users.filter(function(u) { return u.role === 'admin' }).length
  const partnerCount = users.filter(function(u) { return u.role === 'partner' }).length

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <h2 className="font-display text-navy text-lg">USUARIOS</h2>
          <p className="text-xs text-dark/35 mt-0.5">Credenciales de acceso al panel de administración</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 border border-navy/15 text-dark/40 hover:text-dark/70 px-3 py-1.5 rounded text-xs font-display transition-colors hover:bg-navy/5"
        >
          <RefreshCw size={12} />
          ACTUALIZAR
        </button>
      </div>

      {/* Stats */}
      {!loading && (
        <div className="flex gap-3 mb-5">
          <div className="flex items-center gap-2 px-3.5 py-2 bg-violet/8 border border-violet/15 rounded-lg">
            <ShieldCheck size={12} className="text-violet" />
            <span className="text-xs font-display text-violet/70">{adminCount} ADMIN</span>
          </div>
          <div className="flex items-center gap-2 px-3.5 py-2 bg-navy/5 border border-navy/10 rounded-lg">
            <User size={12} className="text-dark/40" />
            <span className="text-xs font-display text-dark/40">{partnerCount} PARTNERS</span>
          </div>
        </div>
      )}

      {/* Filters */}
      {!loading && (
        <div className="flex items-center gap-2 mb-5">

          {/* Search */}
          <div className="relative flex-1 max-w-sm">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-dark/30" />
            <input
              type="text"
              placeholder="Buscar por usuario o partner..."
              value={search}
              onChange={function(e) { setSearch(e.target.value) }}
              autoComplete="off"
              name="search-usuarios"
              className="w-full pl-7 pr-7 py-1.5 text-xs border border-navy/15 rounded bg-pearl text-dark/70 focus:outline-none focus:border-violet transition-colors font-body placeholder:text-dark/25"
            />
            {search && (
              <button
                onClick={function() { setSearch('') }}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-dark/25 hover:text-dark/50"
              >
                <X size={11} />
              </button>
            )}
          </div>

          {/* Role filter pills */}
          {(['', 'admin', 'partner'] as const).map(function(r) {
            const label = r === '' ? 'Todos' : r.charAt(0).toUpperCase() + r.slice(1)
            return (
              <button
                key={r}
                onClick={function() { setRoleFilter(r) }}
                className={
                  'px-3 py-1.5 rounded-full text-xs font-display border transition-colors ' +
                  (roleFilter === r
                    ? 'bg-violet text-pearl border-violet'
                    : 'border-navy/15 text-dark/40 hover:bg-navy/5 hover:text-dark/60'
                  )
                }
              >
                {label}
              </button>
            )
          })}

          {/* Count */}
          <div className="ml-auto">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-display bg-violet/10 text-violet border border-violet/20">
              {filtered.length}
            </span>
          </div>
        </div>
      )}

      {/* Table header */}
      {!loading && filtered.length > 0 && (
        <div className="flex items-center gap-4 px-5 py-2 mb-1">
          <div className="w-8 shrink-0" />
          <div className="w-52 shrink-0">
            <span className="text-xs font-display text-dark/25 tracking-widest">USUARIO / ROL</span>
          </div>
          <div className="flex-1">
            <span className="text-xs font-display text-dark/25 tracking-widest">PARTNER</span>
          </div>
          <div className="w-32 shrink-0">
            <span className="text-xs font-display text-dark/25 tracking-widest">CONTRASEÑA</span>
          </div>
          <div className="w-36 shrink-0" />
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="text-center py-16">
          <p className="text-dark/25 font-display text-xs tracking-widest">CARGANDO...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-navy/15 rounded-xl">
          <p className="text-dark/20 font-display text-xs tracking-widest">
            {search || roleFilter ? 'SIN RESULTADOS PARA ESTA BÚSQUEDA' : 'SIN USUARIOS REGISTRADOS'}
          </p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {filtered.map(function(u) {
            return (
              <div key={u._id} className="relative">
                <UserRow
                  user={u}
                  onChangePassword={setEditingUser}
                  onDelete={handleDelete}
                />
                {/* Feedback inline de contraseña guardada */}
                {savedUsername === u.username && (
                  <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-1.5 bg-forest/10 border border-forest/20 text-forest text-xs font-display px-2.5 py-1 rounded-lg pointer-events-none">
                    <Check size={10} />
                    GUARDADO
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Password modal */}
      {editingUser && (
        <PasswordModal
          user={editingUser}
          onClose={function() { setEditingUser(null) }}
          onSaved={handlePasswordSaved}
        />
      )}
    </div>
  )
}