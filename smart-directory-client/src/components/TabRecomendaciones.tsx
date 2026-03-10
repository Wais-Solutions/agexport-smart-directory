'use client'
import { useState, useEffect, useMemo } from 'react'
import { RefreshCw, Search, X, ChevronDown, ChevronRight, Phone, MapPin, Stethoscope, Star, Clock, SlidersHorizontal, ExternalLink, AlertTriangle } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL + '/db'
//const API_BASE = 'https://agexport-smart-directory.onrender.com/db'

// ─────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────
type PatientLocation = {
  lat?: number | null
  lon?: number | null
  text_description?: string | null
  location_type?: string
}

type MatchedLocation = {
  address?: string
  lat?: number | null
  lon?: number | null
  maps_url?: string | null
  place_id?: string | null
}

type Referral = {
  _id: string
  patient_phone_number: string
  patient_language?: string
  patient_location?: PatientLocation
  symptoms_raw?: string[]
  symptoms_extracted?: string[]
  services_extracted?: string[]
  is_emergency?: boolean
  partner_name?: string
  partner_category?: string
  partner_phone_number?: string[]
  partner_whatsapp?: string[]
  partner_services?: string[]
  location_matched?: MatchedLocation
  distance_km?: number
  service_score?: number
  distance_score?: number
  final_score?: number
  overall_similarity?: number
  is_fallback?: boolean
  referred_at?: string
  status?: string
}

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────
function formatDate(ts: string | undefined): string {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleDateString('es-GT', { day: '2-digit', month: '2-digit', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('es-GT', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtScore(n: number | undefined): string {
  if (n === undefined || n === null) return '—'
  return (n * 100).toFixed(1) + '%'
}

function fmtDist(n: number | undefined): string {
  if (n === undefined || n === null) return '—'
  return n.toFixed(2) + ' km'
}

function scoreColor(n: number | undefined): string {
  if (n === undefined || n === null) return 'text-dark/30'
  if (n >= 0.7) return 'text-forest'
  if (n >= 0.4) return 'text-amber-600'
  return 'text-red-500'
}

function statusStyle(status: string | undefined): string {
  switch (status?.toLowerCase()) {
    case 'sent':     return 'bg-forest/10 text-forest border border-forest/20'
    case 'pending':  return 'bg-amber-50 text-amber-600 border border-amber-200'
    case 'failed':   return 'bg-red-50 text-red-500 border border-red-200'
    default:         return 'bg-navy/8 text-dark/40 border border-navy/15'
  }
}

// ─────────────────────────────────────────────────────────────────
// ScoreBar
// ─────────────────────────────────────────────────────────────────
function ScoreBar({ label, value, color }: { label: string; value: number | undefined; color: string }) {
  const pct = value !== undefined && value !== null ? Math.round(value * 100) : 0
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <span className="text-xs font-display text-dark/40 tracking-wide">{label}</span>
        <span className={'text-xs font-display font-bold ' + color}>{fmtScore(value)}</span>
      </div>
      <div className="h-1.5 bg-navy/8 rounded-full overflow-hidden">
        <div
          className={'h-full rounded-full transition-all ' + (
            pct >= 70 ? 'bg-forest' : pct >= 40 ? 'bg-amber-400' : 'bg-red-400'
          )}
          style={{ width: pct + '%' }}
        />
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// MapsLink
// ─────────────────────────────────────────────────────────────────
function MapsLink({ url, label }: { url: string; label: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 text-xs text-violet hover:underline font-body"
      onClick={function(e) { e.stopPropagation() }}
    >
      <MapPin size={11} />
      {label}
      <ExternalLink size={10} className="opacity-60" />
    </a>
  )
}

// ─────────────────────────────────────────────────────────────────
// ReferralCard
// ─────────────────────────────────────────────────────────────────
function ReferralCard({ ref: referral }: { ref: Referral }) {
  const [expanded, setExpanded] = useState(false)

  const patMapsUrl = referral.patient_location?.lat && referral.patient_location?.lon
    ? 'https://www.google.com/maps?q=' + referral.patient_location.lat + ',' + referral.patient_location.lon
    : null

  return (
    <div className="border border-navy/10 rounded-xl overflow-hidden shadow-sm bg-pearl hover:shadow-md transition-shadow">

      {/* ── Header ── */}
      <div
        className="flex items-start gap-4 px-5 py-4 cursor-pointer hover:bg-violet/[0.02] transition-colors"
        onClick={function() { setExpanded(!expanded) }}
      >
        {/* Partner avatar */}
        <div className="w-10 h-10 rounded-xl bg-violet/10 border border-violet/20 flex items-center justify-center shrink-0 mt-0.5">
          <Star size={15} className="text-violet" />
        </div>

        <div className="flex-1 min-w-0">
          {/* Partner name + category */}
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-display text-sm text-dark tracking-wide">
              {referral.partner_name || '—'}
            </p>
            {referral.is_fallback && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-display bg-amber-50 text-amber-600 border border-amber-200">
                <AlertTriangle size={10} />
                FALLBACK
              </span>
            )}
            {referral.is_emergency && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-display bg-red-50 text-red-500 border border-red-200">
                EMERGENCIA
              </span>
            )}
          </div>
          <p className="text-xs text-dark/40 mt-0.5">{referral.partner_category || '—'}</p>

          {/* Patient + timestamp */}
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            <span className="inline-flex items-center gap-1 text-xs text-dark/50">
              <Phone size={10} className="text-violet/50" />
              {referral.patient_phone_number || '—'}
            </span>
            <span className="inline-flex items-center gap-1 text-xs text-dark/35">
              <Clock size={10} />
              {formatDate(referral.referred_at)}
            </span>
          </div>
        </div>

        {/* Score pill + status */}
        <div className="flex flex-col items-end gap-2 shrink-0">
          <span className={'px-2 py-0.5 rounded-full text-xs font-display ' + statusStyle(referral.status)}>
            {(referral.status || 'unknown').toUpperCase()}
          </span>
          <span className={'text-sm font-display font-bold ' + scoreColor(referral.final_score)}>
            {fmtScore(referral.final_score)}
          </span>
          <span className="text-xs text-dark/30">{fmtDist(referral.distance_km)}</span>
        </div>

        <div className="shrink-0 mt-1">
          {expanded
            ? <ChevronDown size={14} className="text-violet" />
            : <ChevronRight size={14} className="text-dark/25" />
          }
        </div>
      </div>

      {/* ── Expanded detail ── */}
      {expanded && (
        <div className="border-t border-navy/10 bg-navy/[0.012]">

          {/* Grid: left = patient/symptoms, right = partner/scores */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-y md:divide-y-0 md:divide-x divide-navy/8">

            {/* ── LEFT: Patient info ── */}
            <div className="px-5 py-4 space-y-4">
              <p className="font-display text-xs text-dark/25 tracking-widest">PACIENTE</p>

              {/* Symptoms raw */}
              {Array.isArray(referral.symptoms_raw) && referral.symptoms_raw.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs font-display text-dark/35">SÍNTOMAS ORIGINALES</p>
                  <div className="flex flex-wrap gap-1.5">
                    {referral.symptoms_raw.map(function(s, i) {
                      return (
                        <span key={i} className="bg-amber-50 text-amber-700 border border-amber-200 text-xs px-2 py-0.5 rounded-full">
                          {s}
                        </span>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Symptoms extracted */}
              {Array.isArray(referral.symptoms_extracted) && referral.symptoms_extracted.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs font-display text-dark/35">SÍNTOMAS EXTRAÍDOS</p>
                  <div className="flex flex-wrap gap-1.5">
                    {referral.symptoms_extracted.map(function(s, i) {
                      return (
                        <span key={i} className="bg-violet/8 text-violet/80 border border-violet/15 text-xs px-2 py-0.5 rounded-full">
                          {s}
                        </span>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Services extracted */}
              {Array.isArray(referral.services_extracted) && referral.services_extracted.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs font-display text-dark/35">SERVICIOS IDENTIFICADOS</p>
                  <div className="flex flex-wrap gap-1.5">
                    {referral.services_extracted.map(function(s, i) {
                      return (
                        <span key={i} className="bg-forest/8 text-forest border border-forest/15 text-xs px-2 py-0.5 rounded-full">
                          {s}
                        </span>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Patient location */}
              {referral.patient_location && (
                <div className="space-y-1">
                  <p className="text-xs font-display text-dark/35">UBICACIÓN DEL PACIENTE</p>
                  <div className="text-xs text-dark/55 space-y-0.5">
                    {referral.patient_location.text_description && (
                      <p>{referral.patient_location.text_description}</p>
                    )}
                    {patMapsUrl && (
                      <MapsLink url={patMapsUrl} label="Ver en mapa" />
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* ── RIGHT: Partner info + scores ── */}
            <div className="px-5 py-4 space-y-4">
              <p className="font-display text-xs text-dark/25 tracking-widest">PARTNER</p>

              {/* Contact */}
              <div className="space-y-2">
                {Array.isArray(referral.partner_phone_number) && referral.partner_phone_number.length > 0 && (
                  <div className="space-y-0.5">
                    <p className="text-xs font-display text-dark/35">TELÉFONO</p>
                    {referral.partner_phone_number.map(function(p, i) {
                      return (
                        <p key={i} className="text-xs text-dark/60 font-mono flex items-center gap-1.5">
                          <Phone size={10} className="text-dark/30" />
                          {p}
                        </p>
                      )
                    })}
                  </div>
                )}

                {Array.isArray(referral.partner_whatsapp) && referral.partner_whatsapp.length > 0 && (
                  <div className="space-y-0.5">
                    <p className="text-xs font-display text-dark/35">WHATSAPP</p>
                    {referral.partner_whatsapp.map(function(p, i) {
                      const waUrl = 'https://wa.me/' + p.replace(/\D/g, '')
                      return (
                        <a key={i} href={waUrl} target="_blank" rel="noopener noreferrer"
                          onClick={function(e) { e.stopPropagation() }}
                          className="text-xs text-forest hover:underline font-mono flex items-center gap-1.5">
                          <Phone size={10} className="text-forest/50" />
                          {p}
                        </a>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Maps */}
              {referral.location_matched && (
                <div className="space-y-1">
                  <p className="text-xs font-display text-dark/35">DIRECCIÓN DEL PARTNER</p>
                  {referral.location_matched.address && (
                    <p className="text-xs text-dark/55">{referral.location_matched.address}</p>
                  )}
                  {referral.location_matched.maps_url && (
                    <MapsLink url={referral.location_matched.maps_url} label="Abrir en Google Maps" />
                  )}
                  {!referral.location_matched.maps_url && referral.location_matched.lat && referral.location_matched.lon && (
                    <MapsLink
                      url={'https://www.google.com/maps?q=' + referral.location_matched.lat + ',' + referral.location_matched.lon}
                      label="Abrir en Google Maps"
                    />
                  )}
                </div>
              )}

              {/* Scores */}
              <div className="space-y-2.5 pt-1">
                <p className="text-xs font-display text-dark/35">SCORES</p>
                <ScoreBar label="SCORE FINAL" value={referral.final_score} color={scoreColor(referral.final_score)} />
                <ScoreBar label="SERVICIOS" value={referral.service_score} color={scoreColor(referral.service_score)} />
                <ScoreBar label="DISTANCIA" value={referral.distance_score} color={scoreColor(referral.distance_score)} />
                <ScoreBar label="SIMILITUD GENERAL" value={referral.overall_similarity} color={scoreColor(referral.overall_similarity)} />
                <div className="flex justify-between items-center pt-1 border-t border-navy/8">
                  <span className="text-xs font-display text-dark/35">DISTANCIA</span>
                  <span className="text-xs font-display text-dark/60">{fmtDist(referral.distance_km)}</span>
                </div>
              </div>

            </div>
          </div>

          {/* Partner services - full width */}
          {Array.isArray(referral.partner_services) && referral.partner_services.length > 0 && (
            <div className="px-5 py-4 border-t border-navy/8 space-y-2">
              <p className="text-xs font-display text-dark/35">SERVICIOS DEL PARTNER</p>
              <div className="flex flex-wrap gap-1.5">
                {referral.partner_services.map(function(s, i) {
                  const isMatch = Array.isArray(referral.services_extracted) &&
                    referral.services_extracted.some(function(se) {
                      return se.toLowerCase().includes(s.toLowerCase()) || s.toLowerCase().includes(se.toLowerCase())
                    })
                  return (
                    <span
                      key={i}
                      className={
                        'text-xs px-2 py-0.5 rounded-full border ' +
                        (isMatch
                          ? 'bg-forest/10 text-forest border-forest/25 font-display'
                          : 'bg-navy/5 text-dark/45 border-navy/12'
                        )
                      }
                    >
                      {s}
                    </span>
                  )
                })}
              </div>
              <p className="text-xs text-dark/25 font-display">Los servicios en verde coinciden con los identificados</p>
            </div>
          )}

        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Filters
// ─────────────────────────────────────────────────────────────────
type Filters = {
  search: string        // por patient_phone o partner_name
  status: string
  isEmergency: 'all' | 'yes' | 'no'
  isFallback: 'all' | 'yes' | 'no'
  minScore: string      // '0' | '40' | '70'
}

const defaultFilters: Filters = {
  search: '',
  status: '',
  isEmergency: 'all',
  isFallback: 'all',
  minScore: '0',
}

function applyFilters(refs: Referral[], f: Filters): Referral[] {
  return refs.filter(function(r) {
    if (f.search) {
      const s = f.search.toLowerCase()
      const inPhone = (r.patient_phone_number || '').toLowerCase().includes(s)
      const inPartner = (r.partner_name || '').toLowerCase().includes(s)
      if (!inPhone && !inPartner) return false
    }
    if (f.status && (r.status || '').toLowerCase() !== f.status.toLowerCase()) return false
    if (f.isEmergency === 'yes' && !r.is_emergency) return false
    if (f.isEmergency === 'no' && !!r.is_emergency) return false
    if (f.isFallback === 'yes' && !r.is_fallback) return false
    if (f.isFallback === 'no' && !!r.is_fallback) return false
    if (f.minScore !== '0') {
      const min = parseInt(f.minScore) / 100
      if ((r.final_score ?? 0) < min) return false
    }
    return true
  })
}

function countActiveFilters(f: Filters): number {
  let n = 0
  if (f.search) n++
  if (f.status) n++
  if (f.isEmergency !== 'all') n++
  if (f.isFallback !== 'all') n++
  if (f.minScore !== '0') n++
  return n
}

function getUniqueStatuses(refs: Referral[]): string[] {
  const set = new Set<string>()
  refs.forEach(function(r) { if (r.status) set.add(r.status) })
  return Array.from(set).sort()
}

function FilterSelect({ label, value, onChange, options }: {
  label: string; value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-display text-dark/35 tracking-widest">{label}</label>
      <select
        value={value}
        onChange={function(e) { onChange(e.target.value) }}
        className="bg-pearl border border-navy/15 rounded px-2.5 py-1.5 text-xs text-dark/70 font-body focus:outline-none focus:border-violet transition-colors cursor-pointer"
      >
        {options.map(function(o) {
          return <option key={o.value} value={o.value}>{o.label}</option>
        })}
      </select>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────
export default function TabRecomendaciones() {
  const [referrals, setReferrals] = useState<Referral[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState<Filters>(defaultFilters)
  const [showFilters, setShowFilters] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await fetch(API_BASE + '/referrals?limit=200')
      const json = await res.json()
      setReferrals(json.data ?? [])
    } catch { setReferrals([]) }
    setLoading(false)
  }

  useEffect(function() { load() }, [])

  const filtered = useMemo(function() { return applyFilters(referrals, filters) }, [referrals, filters])
  const statuses = useMemo(function() { return getUniqueStatuses(referrals) }, [referrals])
  const activeCount = useMemo(function() { return countActiveFilters(filters) }, [filters])

  // Sort: newest first
  const sorted = useMemo(function() {
    return [...filtered].sort(function(a, b) {
      return new Date(b.referred_at || 0).getTime() - new Date(a.referred_at || 0).getTime()
    })
  }, [filtered])

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="font-display text-navy text-lg">RECOMENDACIONES</h2>
          <p className="text-xs text-dark/35 mt-0.5">Historial de referidos a partners</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 border border-navy/15 text-dark/40 hover:text-dark/70 px-3 py-1.5 rounded text-xs font-display transition-colors hover:bg-navy/5"
        >
          <RefreshCw size={12} />
          ACTUALIZAR
        </button>
      </div>

      {/* Filters bar */}
      {!loading && (
        <div className="mb-5 space-y-2">
          <div className="flex items-center gap-2">
            {/* Search */}
            <div className="relative flex-1 max-w-sm">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-dark/30" />
              <input
                type="text"
                placeholder="Buscar por número o partner..."
                value={filters.search}
                onChange={function(e) { setFilters({ ...filters, search: e.target.value }) }}
                className="w-full pl-7 pr-7 py-1.5 text-xs border border-navy/15 rounded bg-pearl text-dark/70 focus:outline-none focus:border-violet transition-colors font-body placeholder:text-dark/25"
              />
              {filters.search && (
                <button onClick={function() { setFilters({ ...filters, search: '' }) }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-dark/25 hover:text-dark/50">
                  <X size={11} />
                </button>
              )}
            </div>

            {/* Toggle filters */}
            <button
              onClick={function() { setShowFilters(!showFilters) }}
              className={
                'flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-display border transition-colors ' +
                (showFilters || activeCount > 0
                  ? 'bg-violet text-pearl border-violet'
                  : 'border-navy/15 text-dark/40 hover:text-dark/70 hover:bg-navy/5'
                )
              }
            >
              <SlidersHorizontal size={12} />
              FILTROS
              {activeCount > 0 && (
                <span className={'w-4 h-4 rounded-full text-xs flex items-center justify-center font-display ' +
                  (showFilters ? 'bg-pearl text-violet' : 'bg-white/20 text-pearl')}>
                  {activeCount}
                </span>
              )}
            </button>

            {activeCount > 0 && (
              <button onClick={function() { setFilters(defaultFilters) }}
                className="flex items-center gap-1 text-xs text-dark/30 hover:text-dark/60 transition-colors font-display">
                <X size={11} />
                LIMPIAR
              </button>
            )}

            {/* Count */}
            <div className="ml-auto flex items-center gap-2">
              {filtered.length !== referrals.length && (
                <span className="text-xs text-dark/30 font-display">{filtered.length} de {referrals.length}</span>
              )}
              <span className="px-2.5 py-0.5 rounded-full text-xs font-display bg-violet/10 text-violet border border-violet/20">
                {filtered.length}
              </span>
            </div>
          </div>

          {/* Advanced filters */}
          {showFilters && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-4 bg-navy/[0.02] border border-navy/10 rounded-xl">
              <FilterSelect
                label="ESTADO"
                value={filters.status}
                onChange={function(v) { setFilters({ ...filters, status: v }) }}
                options={[
                  { value: '', label: 'Todos los estados' },
                  ...statuses.map(function(s) { return { value: s, label: s.toUpperCase() } }),
                ]}
              />
              <FilterSelect
                label="SCORE MÍNIMO"
                value={filters.minScore}
                onChange={function(v) { setFilters({ ...filters, minScore: v }) }}
                options={[
                  { value: '0',  label: 'Cualquier score' },
                  { value: '40', label: '≥ 40%' },
                  { value: '70', label: '≥ 70%' },
                ]}
              />
              <FilterSelect
                label="EMERGENCIA"
                value={filters.isEmergency}
                onChange={function(v) { setFilters({ ...filters, isEmergency: v as Filters['isEmergency'] }) }}
                options={[
                  { value: 'all', label: 'Todas' },
                  { value: 'yes', label: 'Solo emergencias' },
                  { value: 'no',  label: 'Sin emergencias' },
                ]}
              />
              <FilterSelect
                label="FALLBACK"
                value={filters.isFallback}
                onChange={function(v) { setFilters({ ...filters, isFallback: v as Filters['isFallback'] }) }}
                options={[
                  { value: 'all', label: 'Todos' },
                  { value: 'yes', label: 'Solo fallback' },
                  { value: 'no',  label: 'Sin fallback' },
                ]}
              />
            </div>
          )}
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="text-center py-16">
          <p className="text-dark/25 font-display text-xs tracking-widest">CARGANDO...</p>
        </div>
      ) : sorted.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-navy/15 rounded-xl">
          <p className="text-dark/20 font-display text-xs tracking-widest">
            {activeCount > 0 ? 'SIN RESULTADOS PARA ESTOS FILTROS' : 'SIN RECOMENDACIONES'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {sorted.map(function(r) { return <ReferralCard key={r._id} ref={r} /> })}
        </div>
      )}
    </div>
  )
}