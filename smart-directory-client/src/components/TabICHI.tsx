'use client'
import { useEffect, useRef, useState } from 'react'
import { Save, X, Activity, Loader2, Search, Sparkles, CheckCircle2, Upload, AlertCircle, Download } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ICHIClass { code: string; title: string }
interface PartnerInfo { partner_id: string; partner_name: string; username: string }

interface ImportState {
  active:    boolean
  phase:     'reading' | 'fetching' | 'done' | 'error'
  total:     number
  current:   number
  imported:  ICHIClass[]
  notFound:  string[]
  error?:    string
}

const IMPORT_IDLE: ImportState = {
  active: false, phase: 'reading', total: 0, current: 0, imported: [], notFound: []
}

export default function TabICHI() {
  const [partner, setPartner]           = useState<PartnerInfo | null>(null)
  const [ichiClasses, setICHIClasses]   = useState<ICHIClass[]>([])
  const [suggestions, setSuggestions]   = useState<ICHIClass[]>([])
  const [basedOn, setBasedOn]           = useState<string[]>([])
  const [query, setQuery]               = useState('')
  const [results, setResults]           = useState<ICHIClass[]>([])
  const [searching, setSearching]       = useState(false)
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [saving, setSaving]             = useState(false)
  const [saved, setSaved]               = useState(false)
  const [loadingData, setLoadingData]   = useState(true)
  const [importState, setImportState]   = useState<ImportState>(IMPORT_IDLE)

  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const fileInputRef  = useRef<HTMLInputElement>(null)

  // ── 6. Descargar plantilla de Excel ──────────────────────────────────────────────
  const handleDownloadTemplate = () => {
    const a    = document.createElement('a')
    a.href     = '/ichi_template.xlsx'
    a.download = 'ichi_template.xlsx'
    a.click()
  }

  // ── 1. Cargar datos ──────────────────────────────────────────────────
  useEffect(() => {
    async function loadData() {
      try {
        const meRes = await fetch('/api/auth/me')
        const me    = await meRes.json()
        setPartner({ partner_id: me.partner_id, partner_name: me.partner_name, username: me.username })
        setLoadingSuggestions(true)

        const [ichiRes, suggRes] = await Promise.all([
          fetch(`${API_URL}/ichi/${me.partner_id}`),
          fetch(`${API_URL}/ichi/suggestions/${me.partner_id}`),
        ])
        const ichiData = await ichiRes.json()
        setICHIClasses(ichiData.ichi_classes || [])
        const suggData = await suggRes.json()
        setSuggestions(suggData.suggestions || [])
        setBasedOn(suggData.based_on || [])
      } catch (err) {
        console.error('Error cargando datos ICHI:', err)
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
        const res  = await fetch(`${API_URL}/ichi/search?q=${encodeURIComponent(query)}`)
        const data = await res.json()
        setResults(data.results || [])
      } catch { /* silent */ } finally { setSearching(false) }
    }, 400)
  }, [query])

  // ── 3. Toggle ────────────────────────────────────────────────────────
  const toggleICHIClass = (ichiClass: ICHIClass) => {
    setICHIClasses(prev =>
      prev.some(s => s.code === ichiClass.code)
        ? prev.filter(s => s.code !== ichiClass.code)
        : [...prev, { code: ichiClass.code, title: ichiClass.title }]
    )
  }
  const isSelected = (code: string) => ichiClasses.some(s => s.code === code)

  // ── 4. Guardar ───────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!partner) return
    setSaving(true)
    try {
      await fetch(`${API_URL}/ichi/${partner.partner_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ partner_id: partner.partner_id, partner_name: partner.partner_name, username: partner.username, ichi_classes: ichiClasses }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch { /* silent */ } finally { setSaving(false) }
  }

  // ── 5. Importar Excel ────────────────────────────────────────────────
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !partner) return
    e.target.value = ''

    setImportState({ active: true, phase: 'reading', total: 0, current: 0, imported: [], notFound: [] })

    try {
      const formData = new FormData()
      formData.append('file', file)

      setImportState(s => ({ ...s, phase: 'fetching' }))

      const res  = await fetch(`${API_URL}/ichi/import/${partner.partner_id}`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json()
        setImportState(s => ({ ...s, phase: 'error', error: err.detail || 'Error al procesar el archivo' }))
        return
      }

      const data = await res.json()

      // Simular progreso visual mientras se procesa
      const total = data.total
      for (let i = 1; i <= total; i++) {
        await new Promise(r => setTimeout(r, 30))
        setImportState(s => ({ ...s, total, current: i }))
      }

      // Agregar importadas sin duplicar
      setICHIClasses(prev => {
        const existing = new Set(prev.map(s => s.code))
        const newOnes  = data.imported.filter((s: ICHIClass) => !existing.has(s.code))
        return [...prev, ...newOnes]
      })

      setImportState(s => ({
        ...s,
        phase:    'done',
        total,
        current:  total,
        imported: data.imported,
        notFound: data.not_found,
      }))
    } catch {
      setImportState(s => ({ ...s, phase: 'error', error: 'Error de conexión al importar' }))
    }
  }

  const progress = importState.total > 0 ? Math.round((importState.current / importState.total) * 100) : 0

  if (loadingData) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 size={20} className="animate-spin text-violet" />
      </div>
    )
  }

  return (
    <div className="space-y-6">

      {/* ── Modal de importación ── */}
      {importState.active && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-dark/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md mx-4 space-y-5">

            {/* Icono de estado */}
            <div className="flex justify-center">
              {importState.phase === 'error' ? (
                <div className="w-14 h-14 bg-red-50 rounded-full flex items-center justify-center">
                  <AlertCircle size={28} className="text-red-400" />
                </div>
              ) : importState.phase === 'done' ? (
                <div className="w-14 h-14 bg-violet/10 rounded-full flex items-center justify-center">
                  <CheckCircle2 size={28} className="text-violet" />
                </div>
              ) : (
                <div className="w-14 h-14 bg-violet/10 rounded-full flex items-center justify-center">
                  <Loader2 size={28} className="animate-spin text-violet" />
                </div>
              )}
            </div>

            {/* Título */}
            <div className="text-center space-y-1">
              <p className="font-display text-sm tracking-widest uppercase text-navy font-bold">
                {importState.phase === 'reading'  && 'Leyendo archivo...'}
                {importState.phase === 'fetching' && 'Verificando códigos ICHI...'}
                {importState.phase === 'done'     && '¡Importación completada!'}
                {importState.phase === 'error'    && 'Error en la importación'}
              </p>
              <p className="text-xs text-dark/40">
                {importState.phase === 'fetching' && `Procesando ${importState.total} código${importState.total !== 1 ? 's' : ''}...`}
                {importState.phase === 'done'     && `${importState.imported.length} intervención${importState.imported.length !== 1 ? 'es' : ''} importadas correctamente`}
                {importState.phase === 'error'    && importState.error}
              </p>
            </div>

            {/* Barra de progreso */}
            {(importState.phase === 'fetching' || importState.phase === 'done') && (
              <div className="space-y-2">
                <div className="w-full bg-navy/10 rounded-full h-2 overflow-hidden">
                  <div
                    className="h-full bg-violet rounded-full transition-all duration-100"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-dark/30">
                  <span>{importState.current} de {importState.total}</span>
                  <span>{progress}%</span>
                </div>
              </div>
            )}

            {/* Resultado detallado */}
            {importState.phase === 'done' && (
              <div className="space-y-2">
                {importState.imported.length > 0 && (
                  <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 flex items-center gap-2">
                    <CheckCircle2 size={14} className="text-green-500 shrink-0" />
                    <span className="text-xs text-green-700">
                      {importState.imported.length} código{importState.imported.length !== 1 ? 's' : ''} importado{importState.imported.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                )}
                {importState.notFound.length > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 space-y-1">
                    <div className="flex items-center gap-2">
                      <AlertCircle size={14} className="text-amber-500 shrink-0" />
                      <span className="text-xs text-amber-700 font-bold">
                        {importState.notFound.length} código{importState.notFound.length !== 1 ? 's' : ''} no encontrado{importState.notFound.length !== 1 ? 's' : ''}
                      </span>
                    </div>
                    <p className="text-xs text-amber-600 font-display pl-5">
                      {importState.notFound.join(', ')}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Botón cerrar */}
            {(importState.phase === 'done' || importState.phase === 'error') && (
              <button
                onClick={() => setImportState(IMPORT_IDLE)}
                className="w-full bg-violet hover:bg-violet/80 text-pearl py-2.5 rounded-xl text-xs font-display tracking-wide transition-colors"
              >
                {importState.phase === 'done' ? 'ACEPTAR' : 'CERRAR'}
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-sm tracking-widest uppercase text-navy font-bold">
            Intervenciones ICHI
          </h2>
          <p className="text-xs text-dark/40 mt-1">
            Selecciona las intervenciones y procedimientos que ofrece tu institución.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Input oculto */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            disabled
            className="flex items-center gap-2 border border-navy/20 text-dark/30 px-4 py-2.5 rounded-lg text-xs font-display tracking-wide cursor-not-allowed opacity-50"
          >
            <Download size={13} />
            DESCARGAR PLANTILLA
          </button>
          <button
            disabled
            className="flex items-center gap-2 border border-navy/20 text-dark/30 px-4 py-2.5 rounded-lg text-xs font-display tracking-wide cursor-not-allowed opacity-50"
          >
            <Upload size={13} />
            IMPORTAR EXCEL
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 bg-violet hover:bg-violet/80 disabled:opacity-60 text-pearl px-5 py-2.5 rounded-lg text-xs font-display tracking-wide transition-colors shadow-sm"
          >
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            {saved ? 'GUARDADO ✓' : 'GUARDAR CAMBIOS'}
          </button>
        </div>
      </div>

      {/* ── Leyenda ICHI ── */}
      <div className="bg-violet/5 border border-violet/15 rounded-2xl px-5 py-4 flex gap-4 items-start">
        <div className="w-8 h-8 bg-violet/15 rounded-lg flex items-center justify-center shrink-0 mt-0.5">
          <Activity size={15} className="text-violet" />
        </div>
        <div className="space-y-1">
          <p className="text-xs font-display font-bold text-navy tracking-wide uppercase">
            ¿Qué es ICHI?
          </p>
          <p className="text-xs text-dark/60 leading-relaxed">
            La <span className="font-bold text-dark/80">Clasificación Internacional de Intervenciones en Salud (ICHI)</span> es
            el estándar global de la OMS para clasificar intervenciones médicas y procedimientos.
            Selecciona las <span className="font-bold text-violet">intervenciones y procedimientos que tu institución
            puede realizar</span> — esto ayuda a los pacientes a identificar el centro adecuado
            para sus necesidades de tratamiento.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ── Columna izquierda ── */}
        <div className="space-y-5">

          {/* Buscador */}
          <div className="bg-white border border-navy/10 rounded-2xl p-5 shadow-sm space-y-3">
            <div className="flex items-center gap-2">
              <Search size={14} className="text-violet" />
              <p className="text-xs font-display tracking-widest text-navy uppercase font-bold">
                Buscar en ICHI
              </p>
            </div>
            <div className="relative">
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Ej: cirugía, fisioterapia, radioterapia..."
                className="w-full bg-navy/5 border border-navy/10 rounded-xl px-4 py-3 text-dark text-sm focus:outline-none focus:border-violet focus:bg-white transition-all placeholder:text-dark/25"
              />
              {searching && <Loader2 size={13} className="absolute right-4 top-1/2 -translate-y-1/2 animate-spin text-violet" />}
            </div>

            {results.length > 0 && (
              <div className="border border-navy/10 rounded-xl divide-y divide-navy/5 max-h-80 overflow-y-auto">
                {results.map(r => {
                  const selected = isSelected(r.code)
                  return (
                    <label key={r.code} className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${selected ? 'bg-violet/5' : 'hover:bg-navy/3'}`}>
                      <input type="checkbox" checked={selected} onChange={() => toggleICHIClass(r)} className="accent-violet shrink-0" />
                      <span className="text-xs font-display text-violet bg-violet/10 px-2 py-0.5 rounded-md font-bold shrink-0">{r.code}</span>
                      <span className="text-sm text-dark leading-snug">{r.title}</span>
                      {selected && <CheckCircle2 size={13} className="text-violet ml-auto shrink-0" />}
                    </label>
                  )
                })}
              </div>
            )}
            {query.length >= 2 && !searching && results.length === 0 && (
              <p className="text-xs text-dark/30 text-center py-3">No se encontraron resultados para &ldquo;{query}&rdquo;</p>
            )}
            {!query && <p className="text-xs text-dark/25 text-center py-1">Escribe al menos 2 caracteres para buscar</p>}
          </div>

          {/* Sugeridas */}
          <div className="bg-white border border-violet/20 rounded-2xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-violet" />
                <p className="text-xs font-display tracking-widest text-navy uppercase font-bold">Intervenciones sugeridas</p>
              </div>
              {basedOn.length > 0 && <span className="text-xs text-dark/30 italic">basado en tus servicios</span>}
            </div>
            {loadingSuggestions ? (
              <div className="flex justify-center py-4"><Loader2 size={16} className="animate-spin text-violet/40" /></div>
            ) : suggestions.length === 0 ? (
              <p className="text-xs text-dark/30 text-center py-3">No hay sugerencias disponibles.</p>
            ) : (
              <div className="space-y-2">
                {suggestions.map(s => {
                  const selected = isSelected(s.code)
                  return (
                    <label key={s.code} className={`flex items-center gap-3 px-4 py-3 rounded-xl cursor-pointer border transition-all ${selected ? 'bg-violet/8 border-violet/30' : 'bg-navy/3 border-transparent hover:border-violet/20 hover:bg-violet/5'}`}>
                      <input type="checkbox" checked={selected} onChange={() => toggleICHIClass(s)} className="accent-violet shrink-0" />
                      <span className="text-xs font-display text-violet bg-violet/10 px-2 py-0.5 rounded-md font-bold shrink-0">{s.code}</span>
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
              <Activity size={14} className="text-violet" />
              <p className="text-xs font-display tracking-widest text-navy uppercase font-bold">Seleccionadas</p>
            </div>
            <span className={`text-xs font-display font-bold px-2.5 py-0.5 rounded-full ${ichiClasses.length > 0 ? 'bg-violet text-pearl' : 'bg-navy/5 text-dark/30'}`}>
              {ichiClasses.length}
            </span>
          </div>
          {ichiClasses.length === 0 ? (
            <div className="flex flex-col items-center py-12 gap-3">
              <div className="w-12 h-12 bg-navy/5 rounded-full flex items-center justify-center">
                <Activity size={20} className="text-dark/20" />
              </div>
              <p className="text-xs text-dark/30 text-center">Usa el buscador o las sugerencias<br />para agregar intervenciones.</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
              {ichiClasses.map(s => (
                <div key={s.code} className="flex items-center justify-between bg-navy/3 border border-navy/8 rounded-xl px-3 py-2.5 group hover:border-red-200 transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-xs font-display text-violet bg-violet/10 px-2 py-0.5 rounded-md font-bold shrink-0">{s.code}</span>
                    <span className="text-sm text-dark truncate">{s.title}</span>
                  </div>
                  <button onClick={() => toggleICHIClass(s)} className="text-dark/20 hover:text-red-400 transition-colors ml-2 shrink-0 opacity-0 group-hover:opacity-100" title="Eliminar">
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