'use client'
import { useEffect, useRef, useState } from 'react'
import { Save, X, Stethoscope, Loader2, Search } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Specialty {
  code: string
  title: string
  uri?: string
}

interface PartnerInfo {
  partner_id: string
  partner_name: string
  username: string
}

export default function TabEspecialidades() {
  const [partner, setPartner]           = useState<PartnerInfo | null>(null)
  const [specialties, setSpecialties]   = useState<Specialty[]>([])
  const [query, setQuery]               = useState('')
  const [results, setResults]           = useState<Specialty[]>([])
  const [searching, setSearching]       = useState(false)
  const [saving, setSaving]             = useState(false)
  const [saved, setSaved]               = useState(false)
  const [loadingData, setLoadingData]   = useState(true)
  const searchTimeout                   = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── 1. Cargar datos del partner ──────────────────────────────────────
  useEffect(() => {
    async function loadData() {
      try {
        const meRes  = await fetch('/api/auth/me')
        const me     = await meRes.json()
        setPartner({ partner_id: me.partner_id, partner_name: me.partner_name, username: me.username })

        const specRes  = await fetch(`${API_URL}/specialties/${me.partner_id}`)
        const specData = await specRes.json()
        setSpecialties(specData.specialties || [])
      } catch (err) {
        console.error('Error cargando datos:', err)
      } finally {
        setLoadingData(false)
      }
    }
    loadData()
  }, [])

  // ── 2. Búsqueda con debounce ─────────────────────────────────────────
  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    if (!query || query.trim().length < 2) { setResults([]); return }

    searchTimeout.current = setTimeout(async () => {
      setSearching(true)
      try {
        const res  = await fetch(`${API_URL}/specialties/search?q=${encodeURIComponent(query)}`)
        const data = await res.json()
        setResults(data.results || [])
      } catch (err) {
        console.error('Error buscando:', err)
      } finally {
        setSearching(false)
      }
    }, 400)
  }, [query])

  // ── 3. Toggle selección ──────────────────────────────────────────────
  const toggleSpecialty = (spec: Specialty) => {
    setSpecialties(prev => {
      const exists = prev.some(s => s.code === spec.code)
      if (exists) return prev.filter(s => s.code !== spec.code)
      return [...prev, { code: spec.code, title: spec.title }]
    })
  }

  const isSelected = (code: string) => specialties.some(s => s.code === code)

  // ── 4. Guardar ───────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!partner) return
    setSaving(true)
    try {
      await fetch(`${API_URL}/specialties/${partner.partner_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          partner_id:   partner.partner_id,
          partner_name: partner.partner_name,
          username:     partner.username,
          specialties,
        }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      console.error('Error guardando:', err)
    } finally {
      setSaving(false)
    }
  }

  if (loadingData) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 size={20} className="animate-spin text-violet" />
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-sm tracking-widest uppercase text-navy">
            Especialidades
          </h2>
          <p className="text-xs text-dark/40 mt-1">
            Busca y selecciona las especialidades médicas que ofrece tu institución.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-violet hover:bg-violet/80 disabled:opacity-60 text-pearl px-4 py-2 rounded-lg text-xs font-display tracking-wide transition-colors"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
          {saved ? 'GUARDADO ✓' : 'GUARDAR CAMBIOS'}
        </button>
      </div>

      {/* Buscador */}
      <div className="bg-white border border-navy/10 rounded-xl p-4 space-y-3">
        <p className="text-xs font-display tracking-widest text-dark/40 uppercase">
          Buscar en CIE-11
        </p>
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-dark/30" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Escribe una enfermedad o especialidad..."
            className="w-full bg-navy/5 border border-navy/10 rounded-lg pl-9 pr-3 py-2.5 text-dark text-sm focus:outline-none focus:border-violet transition-colors placeholder:text-dark/20"
          />
          {searching && (
            <Loader2 size={13} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-violet" />
          )}
        </div>

        {/* Resultados */}
        {results.length > 0 && (
          <div className="border border-navy/10 rounded-lg divide-y divide-navy/5 max-h-72 overflow-y-auto">
            {results.map(r => (
              <label
                key={r.code}
                className="flex items-center gap-3 px-3 py-2.5 hover:bg-navy/3 cursor-pointer transition-colors"
              >
                <input
                  type="checkbox"
                  checked={isSelected(r.code)}
                  onChange={() => toggleSpecialty(r)}
                  className="accent-violet"
                />
                <span className="text-xs font-display text-violet bg-violet/10 px-1.5 py-0.5 rounded font-bold shrink-0">
                  {r.code}
                </span>
                <span className="text-sm text-dark">{r.title}</span>
              </label>
            ))}
          </div>
        )}

        {query.length >= 2 && !searching && results.length === 0 && (
          <p className="text-xs text-dark/30 text-center py-2">
            No se encontraron resultados para "{query}"
          </p>
        )}
      </div>

      {/* Seleccionadas */}
      <div className="bg-white border border-navy/10 rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-display tracking-widest text-dark/40 uppercase">
            Especialidades seleccionadas
          </p>
          <span className="text-xs text-dark/30 bg-navy/5 px-2 py-0.5 rounded-full">
            {specialties.length}
          </span>
        </div>

        {specialties.length === 0 ? (
          <div className="flex flex-col items-center py-8 gap-2">
            <Stethoscope size={20} className="text-dark/20" />
            <p className="text-xs text-dark/30">Aún no hay especialidades seleccionadas.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {specialties.map(s => (
              <div
                key={s.code}
                className="flex items-center justify-between bg-navy/3 border border-navy/8 rounded-lg px-3 py-2.5 group"
              >
                <div className="flex items-center gap-3">
                  <span className="text-xs font-display text-violet bg-violet/10 px-2 py-0.5 rounded font-bold">
                    {s.code}
                  </span>
                  <span className="text-sm text-dark">{s.title}</span>
                </div>
                <button
                  onClick={() => toggleSpecialty(s)}
                  className="text-dark/20 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}