'use client'
import { useEffect, useRef, useState } from 'react'
import { Save, X, Stethoscope, Loader2, Search, Sparkles, CheckCircle2 } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Specialty {
  code: string
  title: string
}

interface PartnerInfo {
  partner_id: string
  partner_name: string
  username: string
}

export default function TabEspecialidades() {
  const [partner, setPartner]             = useState<PartnerInfo | null>(null)
  const [specialties, setSpecialties]     = useState<Specialty[]>([])
  const [suggestions, setSuggestions]     = useState<Specialty[]>([])
  const [basedOn, setBasedOn]             = useState<string[]>([])
  const [query, setQuery]                 = useState('')
  const [results, setResults]             = useState<Specialty[]>([])
  const [searching, setSearching]         = useState(false)
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [saving, setSaving]               = useState(false)
  const [saved, setSaved]                 = useState(false)
  const [loadingData, setLoadingData]     = useState(true)
  const searchTimeout                     = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── 1. Cargar datos ──────────────────────────────────────────────────
  useEffect(() => {
    async function loadData() {
      try {
        const meRes  = await fetch('/api/auth/me')
        const me     = await meRes.json()
        const info   = { partner_id: me.partner_id, partner_name: me.partner_name, username: me.username }
        setPartner(info)

        const [specRes, suggRes] = await Promise.all([
          fetch(`${API_URL}/specialties/${me.partner_id}`),
          fetch(`${API_URL}/specialties/suggestions/${me.partner_id}`).then(r => { setLoadingSuggestions(true); return r }),
        ])

        const specData = await specRes.json()
        setSpecialties(specData.specialties || [])

        const suggData = await suggRes.json()
        setSuggestions(suggData.suggestions || [])
        setBasedOn(suggData.based_on || [])
      } catch (err) {
        console.error('Error cargando datos:', err)
      } finally {
        setLoadingData(false)
        setLoadingSuggestions(false)
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
    <div className="space-y-6">

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-sm tracking-widest uppercase text-navy">
            Especialidades
          </h2>
          <p className="text-xs text-dark/40 mt-1">
            Selecciona las especialidades médicas que ofrece tu institución.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-violet hover:bg-violet/80 disabled:opacity-60 text-pearl px-5 py-2.5 rounded-lg text-xs font-display tracking-wide transition-colors shadow-sm"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
          {saved ? 'GUARDADO ✓' : 'GUARDAR CAMBIOS'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ── Columna izquierda: Búsqueda + Sugeridas ── */}
        <div className="space-y-5">

          {/* Buscador */}
          <div className="bg-white border border-navy/10 rounded-2xl p-5 shadow-sm space-y-3">
            <div className="flex items-center gap-2">
              <Search size={14} className="text-violet" />
              <p className="text-xs font-display tracking-widest text-navy uppercase font-bold">
                Buscar en CIE-11
              </p>
            </div>
            <div className="relative">
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Ej: diabetes, hipertensión, fractura..."
                className="w-full bg-navy/5 border border-navy/10 rounded-xl px-4 py-3 text-dark text-sm focus:outline-none focus:border-violet focus:bg-white transition-all placeholder:text-dark/25"
              />
              {searching && (
                <Loader2 size={13} className="absolute right-4 top-1/2 -translate-y-1/2 animate-spin text-violet" />
              )}
            </div>

            {results.length > 0 && (
              <div className="border border-navy/10 rounded-xl divide-y divide-navy/5 max-h-80 overflow-y-auto">
                {results.map(r => {
                  const selected = isSelected(r.code)
                  return (
                    <label
                      key={r.code}
                      className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${selected ? 'bg-violet/5' : 'hover:bg-navy/3'}`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleSpecialty(r)}
                        className="accent-violet shrink-0"
                      />
                      <span className="text-xs font-display text-violet bg-violet/10 px-2 py-0.5 rounded-md font-bold shrink-0">
                        {r.code}
                      </span>
                      <span className="text-sm text-dark leading-snug">{r.title}</span>
                      {selected && <CheckCircle2 size={13} className="text-violet ml-auto shrink-0" />}
                    </label>
                  )
                })}
              </div>
            )}

            {query.length >= 2 && !searching && results.length === 0 && (
              <p className="text-xs text-dark/30 text-center py-3">
                No se encontraron resultados para &ldquo;{query}&rdquo;
              </p>
            )}

            {!query && (
              <p className="text-xs text-dark/25 text-center py-1">
                Escribe al menos 2 caracteres para buscar
              </p>
            )}
          </div>

          {/* Sugeridas */}
          <div className="bg-white border border-violet/20 rounded-2xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-violet" />
                <p className="text-xs font-display tracking-widest text-navy uppercase font-bold">
                  Especialidades sugeridas
                </p>
              </div>
              {basedOn.length > 0 && (
                <span className="text-xs text-dark/30 italic">
                  basado en tus servicios
                </span>
              )}
            </div>

            {basedOn.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {basedOn.map(s => (
                  <span key={s} className="text-xs bg-violet/10 text-violet px-2 py-0.5 rounded-full font-display">
                    {s}
                  </span>
                ))}
              </div>
            )}

            {loadingSuggestions ? (
              <div className="flex justify-center py-4">
                <Loader2 size={16} className="animate-spin text-violet/40" />
              </div>
            ) : suggestions.length === 0 ? (
              <p className="text-xs text-dark/30 text-center py-3">
                No hay sugerencias disponibles.
              </p>
            ) : (
              <div className="space-y-2">
                {suggestions.map(s => {
                  const selected = isSelected(s.code)
                  return (
                    <label
                      key={s.code}
                      className={`flex items-center gap-3 px-4 py-3 rounded-xl cursor-pointer border transition-all ${
                        selected
                          ? 'bg-violet/8 border-violet/30'
                          : 'bg-navy/3 border-transparent hover:border-violet/20 hover:bg-violet/5'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleSpecialty(s)}
                        className="accent-violet shrink-0"
                      />
                      <span className="text-xs font-display text-violet bg-violet/10 px-2 py-0.5 rounded-md font-bold shrink-0">
                        {s.code}
                      </span>
                      <span className="text-sm text-dark leading-snug">{s.title}</span>
                      {selected && <CheckCircle2 size={13} className="text-violet ml-auto shrink-0" />}
                    </label>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* ── Columna derecha: Seleccionadas ── */}
        <div className="bg-white border border-navy/10 rounded-2xl p-5 shadow-sm space-y-3 h-fit sticky top-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Stethoscope size={14} className="text-violet" />
              <p className="text-xs font-display tracking-widest text-navy uppercase font-bold">
                Seleccionadas
              </p>
            </div>
            <span className={`text-xs font-display font-bold px-2.5 py-0.5 rounded-full ${
              specialties.length > 0 ? 'bg-violet text-pearl' : 'bg-navy/5 text-dark/30'
            }`}>
              {specialties.length}
            </span>
          </div>

          {specialties.length === 0 ? (
            <div className="flex flex-col items-center py-12 gap-3">
              <div className="w-12 h-12 bg-navy/5 rounded-full flex items-center justify-center">
                <Stethoscope size={20} className="text-dark/20" />
              </div>
              <p className="text-xs text-dark/30 text-center">
                Usa el buscador o las sugerencias<br />para agregar especialidades.
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
              {specialties.map(s => (
                <div
                  key={s.code}
                  className="flex items-center justify-between bg-navy/3 border border-navy/8 rounded-xl px-3 py-2.5 group hover:border-red-200 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-xs font-display text-violet bg-violet/10 px-2 py-0.5 rounded-md font-bold shrink-0">
                      {s.code}
                    </span>
                    <span className="text-sm text-dark truncate">{s.title}</span>
                  </div>
                  <button
                    onClick={() => toggleSpecialty(s)}
                    className="text-dark/20 hover:text-red-400 transition-colors ml-2 shrink-0 opacity-0 group-hover:opacity-100"
                    title="Eliminar"
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}