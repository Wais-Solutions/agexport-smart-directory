'use client'
import { useState, useEffect, useMemo } from 'react'
import { Phone, MapPin, Globe, MessageSquare, Stethoscope, ChevronDown, ChevronRight, Trash2, RefreshCw, Archive, Search, X, SlidersHorizontal } from 'lucide-react'

//const API_BASE = process.env.NEXT_PUBLIC_API_URL + '/db'
const API_BASE = 'https://agexport-smart-directory.onrender.com/db'

// ─────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────
type Location = {
  lat?: number | null
  lon?: number | null
  text_description?: string | null
}

type OngoingConversation = {
  _id: string
  sender_id: string
  symptoms: string[]
  location: Location
  language: string | null
  messages: any[]
  recommendation: string | null
  referral_provided: boolean
  referral_count: number
}

type HistoricalConversation = {
  _id: string
  sender_id: string
  history: any[]
}

type OngoingFilters = {
  search: string
  language: string
  hasRecommendation: 'all' | 'yes' | 'no'
  hasReferral: 'all' | 'yes' | 'no'
  hasLocation: 'all' | 'yes' | 'no'
  hasSymptoms: 'all' | 'yes' | 'no'
}

type HistoricalFilters = {
  search: string
}

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────
function formatLocation(location: Location): { text: string; isCoords: boolean } {
  if (!location) return { text: 'Sin ubicación', isCoords: false }
  if (location.lat != null && location.lon != null) {
    return {
      text: Number(location.lat).toFixed(5) + ', ' + Number(location.lon).toFixed(5),
      isCoords: true,
    }
  }
  if (location.text_description) {
    return { text: location.text_description, isCoords: false }
  }
  return { text: 'Sin ubicación', isCoords: false }
}

function formatLanguage(lang: string | null): string {
  if (!lang) return '—'
  const map: Record<string, string> = {
    es: 'Español', en: 'English',
    'es-MX': 'Español', 'es-GT': 'Español', 'en-US': 'English',
    spanish: 'Español', english: 'English', español: 'Español',
  }
  return map[lang.toLowerCase()] ?? lang
}

function normalizeLanguage(lang: string | null): string {
  if (!lang) return ''
  const map: Record<string, string> = {
    es: 'Español', en: 'English',
    'es-mx': 'Español', 'es-gt': 'Español', 'en-us': 'English',
    spanish: 'Español', english: 'English', español: 'Español',
  }
  return map[lang.toLowerCase()] ?? lang
}

function getUniqueLanguages(convs: OngoingConversation[]): string[] {
  const set = new Set<string>()
  convs.forEach(function(c) {
    const n = normalizeLanguage(c.language)
    if (n) set.add(n)
  })
  return Array.from(set).sort()
}

function applyOngoingFilters(convs: OngoingConversation[], f: OngoingFilters): OngoingConversation[] {
  return convs.filter(function(c) {
    if (f.search && !c.sender_id.toLowerCase().includes(f.search.toLowerCase())) return false
    if (f.language && normalizeLanguage(c.language) !== f.language) return false
    if (f.hasRecommendation === 'yes' && !c.recommendation) return false
    if (f.hasRecommendation === 'no' && !!c.recommendation) return false
    if (f.hasReferral === 'yes' && !c.referral_provided) return false
    if (f.hasReferral === 'no' && !!c.referral_provided) return false
    const loc = formatLocation(c.location)
    if (f.hasLocation === 'yes' && loc.text === 'Sin ubicación') return false
    if (f.hasLocation === 'no' && loc.text !== 'Sin ubicación') return false
    const hasSym = Array.isArray(c.symptoms) && c.symptoms.length > 0
    if (f.hasSymptoms === 'yes' && !hasSym) return false
    if (f.hasSymptoms === 'no' && hasSym) return false
    return true
  })
}

function applyHistoricalFilters(convs: HistoricalConversation[], f: HistoricalFilters): HistoricalConversation[] {
  return convs.filter(function(c) {
    if (f.search && !c.sender_id.toLowerCase().includes(f.search.toLowerCase())) return false
    return true
  })
}

function countActiveFilters(f: OngoingFilters): number {
  let n = 0
  if (f.search) n++
  if (f.language) n++
  if (f.hasRecommendation !== 'all') n++
  if (f.hasReferral !== 'all') n++
  if (f.hasLocation !== 'all') n++
  if (f.hasSymptoms !== 'all') n++
  return n
}

const defaultOngoingFilters: OngoingFilters = {
  search: '',
  language: '',
  hasRecommendation: 'all',
  hasReferral: 'all',
  hasLocation: 'all',
  hasSymptoms: 'all',
}

// ─────────────────────────────────────────────────────────────────
// LocationLink
// ─────────────────────────────────────────────────────────────────
function LocationLink({ lat, lon, text }: { lat: number; lon: number; text: string }) {
  const url = 'https://www.google.com/maps?q=' + lat + ',' + lon
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-violet hover:underline font-display text-xs"
      onClick={function(e) { e.stopPropagation() }}
    >
      {'📍 ' + text}
    </a>
  )
}

// ─────────────────────────────────────────────────────────────────
// Badge
// ─────────────────────────────────────────────────────────────────
function Badge({ children, color }: { children: React.ReactNode; color: 'violet' | 'forest' | 'navy' | 'amber' }) {
  const styles = {
    violet: 'bg-violet/10 text-violet border border-violet/20',
    forest: 'bg-forest/10 text-forest border border-forest/20',
    navy:   'bg-navy/10 text-navy/60 border border-navy/15',
    amber:  'bg-amber-50 text-amber-600 border border-amber-200',
  }
  return (
    <span className={'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-display tracking-wide ' + styles[color]}>
      {children}
    </span>
  )
}

// ─────────────────────────────────────────────────────────────────
// InfoRow
// ─────────────────────────────────────────────────────────────────
function InfoRow({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 text-sm">
      <span className="text-violet/50 mt-0.5 shrink-0">{icon}</span>
      <span className="text-dark/40 font-display text-xs w-24 shrink-0 pt-0.5">{label}</span>
      <span className="text-dark/70 flex-1 leading-relaxed">{children}</span>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// MessageThread
// ─────────────────────────────────────────────────────────────────
type Message = { sender?: string; text?: string; role?: string; content?: string; [key: string]: any }

function MessageThread({ messages, senderId }: { messages: Message[]; senderId: string }) {
  const [open, setOpen] = useState(false)
  const count = messages.length
  const last10 = messages.slice(-10)

  function isUser(msg: Message): boolean {
    const s = (msg.sender || msg.role || '').toLowerCase()
    return s === senderId || s === 'user' || s === 'patient'
  }

  function getMsgText(msg: Message): string {
    return msg.text || msg.content || msg.message || JSON.stringify(msg)
  }

  return (
    <div className="flex items-start gap-2 text-sm">
      <span className="text-violet/50 mt-0.5 shrink-0"><MessageSquare size={13} /></span>
      <span className="text-dark/40 font-display text-xs w-24 shrink-0 pt-0.5">MENSAJES</span>
      <div className="flex-1">
        <button
          onClick={function(e) { e.stopPropagation(); setOpen(!open) }}
          className="flex items-center gap-2 group"
        >
          <span className="text-xs text-dark/70">
            {count} {count === 1 ? 'mensaje' : 'mensajes'}
          </span>
          {count > 0 && (
            <span className="flex items-center gap-1 text-xs text-violet/60 group-hover:text-violet transition-colors font-display">
              {open ? 'ocultar' : ('ver últimos ' + Math.min(10, count))}
              {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
            </span>
          )}
        </button>

        {open && count > 0 && (
          <div className="mt-3 space-y-2 max-h-72 overflow-y-auto pr-1">
            {count > 10 && (
              <p className="text-center text-xs text-dark/25 font-display pb-1">
                {'— mostrando últimos 10 de ' + count + ' mensajes —'}
              </p>
            )}
            {last10.map(function(msg, i) {
              const user = isUser(msg)
              const text = getMsgText(msg)
              return (
                <div key={i} className={'flex ' + (user ? 'justify-end' : 'justify-start')}>
                  <div className={
                    'max-w-[75%] px-3 py-2 rounded-2xl text-xs leading-relaxed ' +
                    (user
                      ? 'bg-violet text-pearl rounded-br-sm'
                      : 'bg-navy/8 text-dark/70 border border-navy/10 rounded-bl-sm'
                    )
                  }>
                    {text}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// FilterSelect
// ─────────────────────────────────────────────────────────────────
function FilterSelect({ label, value, onChange, options }: {
  label: string
  value: string
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
// OngoingFiltersPanel
// ─────────────────────────────────────────────────────────────────
function OngoingFiltersPanel({ filters, onChange, languages, onReset, activeCount }: {
  filters: OngoingFilters
  onChange: (f: OngoingFilters) => void
  languages: string[]
  onReset: () => void
  activeCount: number
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 mb-2">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-dark/30" />
          <input
            type="text"
            placeholder="Buscar por número..."
            value={filters.search}
            onChange={function(e) { onChange({ ...filters, search: e.target.value }) }}
            className="w-full pl-7 pr-7 py-1.5 text-xs border border-navy/15 rounded bg-pearl text-dark/70 focus:outline-none focus:border-violet transition-colors font-body placeholder:text-dark/25"
          />
          {filters.search && (
            <button
              onClick={function() { onChange({ ...filters, search: '' }) }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-dark/25 hover:text-dark/50"
            >
              <X size={11} />
            </button>
          )}
        </div>

        {/* Toggle advanced */}
        <button
          onClick={function() { setOpen(!open) }}
          className={
            'flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-display border transition-colors ' +
            (open || activeCount > 0
              ? 'bg-violet text-pearl border-violet'
              : 'border-navy/15 text-dark/40 hover:text-dark/70 hover:bg-navy/5'
            )
          }
        >
          <SlidersHorizontal size={12} />
          FILTROS
          {activeCount > 0 && (
            <span className={
              'w-4 h-4 rounded-full text-xs flex items-center justify-center font-display ' +
              (open ? 'bg-pearl text-violet' : 'bg-white/20 text-pearl')
            }>
              {activeCount}
            </span>
          )}
        </button>

        {activeCount > 0 && (
          <button
            onClick={onReset}
            className="flex items-center gap-1 text-xs text-dark/30 hover:text-dark/60 transition-colors font-display"
          >
            <X size={11} />
            LIMPIAR
          </button>
        )}
      </div>

      {/* Advanced filters grid */}
      {open && (
        <div className="grid grid-cols-2 gap-3 p-4 bg-navy/[0.02] border border-navy/10 rounded-xl">
          <FilterSelect
            label="IDIOMA"
            value={filters.language}
            onChange={function(v) { onChange({ ...filters, language: v }) }}
            options={[
              { value: '', label: 'Todos los idiomas' },
              ...languages.map(function(l) { return { value: l, label: l } }),
            ]}
          />
          <FilterSelect
            label="RECOMENDACIÓN"
            value={filters.hasRecommendation}
            onChange={function(v) { onChange({ ...filters, hasRecommendation: v as OngoingFilters['hasRecommendation'] }) }}
            options={[
              { value: 'all', label: 'Todas' },
              { value: 'yes', label: 'Con recomendación' },
              { value: 'no',  label: 'Sin recomendación' },
            ]}
          />
          <FilterSelect
            label="REFERIDO"
            value={filters.hasReferral}
            onChange={function(v) { onChange({ ...filters, hasReferral: v as OngoingFilters['hasReferral'] }) }}
            options={[
              { value: 'all', label: 'Todos' },
              { value: 'yes', label: 'Con referido' },
              { value: 'no',  label: 'Sin referido' },
            ]}
          />
          <FilterSelect
            label="UBICACIÓN"
            value={filters.hasLocation}
            onChange={function(v) { onChange({ ...filters, hasLocation: v as OngoingFilters['hasLocation'] }) }}
            options={[
              { value: 'all', label: 'Todas' },
              { value: 'yes', label: 'Con ubicación' },
              { value: 'no',  label: 'Sin ubicación' },
            ]}
          />
          <FilterSelect
            label="SÍNTOMAS"
            value={filters.hasSymptoms}
            onChange={function(v) { onChange({ ...filters, hasSymptoms: v as OngoingFilters['hasSymptoms'] }) }}
            options={[
              { value: 'all', label: 'Todos' },
              { value: 'yes', label: 'Con síntomas' },
              { value: 'no',  label: 'Sin síntomas' },
            ]}
          />
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// OngoingCard
// ─────────────────────────────────────────────────────────────────
function OngoingCard({ conv, onDelete }: { conv: OngoingConversation; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const loc = formatLocation(conv.location)
  const msgCount = Array.isArray(conv.messages) ? conv.messages.length : 0

  return (
    <div className="border border-navy/10 rounded-xl overflow-hidden shadow-sm bg-pearl transition-shadow hover:shadow-md">
      <div
        className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-violet/[0.03] transition-colors"
        onClick={function() { setExpanded(!expanded) }}
      >
        <div className="w-9 h-9 rounded-full bg-violet/10 border border-violet/20 flex items-center justify-center shrink-0">
          <Phone size={14} className="text-violet" />
        </div>

        <div className="flex-1 min-w-0">
          <p className="font-display text-sm text-dark tracking-wide truncate">{conv.sender_id || '—'}</p>
          <p className="text-xs text-dark/35 mt-0.5">
            {msgCount} {msgCount === 1 ? 'mensaje' : 'mensajes'}
            {conv.referral_count > 0 && (' · ' + conv.referral_count + ' referencia' + (conv.referral_count > 1 ? 's' : ''))}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {conv.language && <Badge color="navy">{formatLanguage(conv.language)}</Badge>}
          {conv.recommendation && <Badge color="forest">Con recomendación</Badge>}
          {conv.referral_provided && <Badge color="violet">Referido</Badge>}
        </div>

        <div className="flex items-center gap-2 ml-2">
          <button
            onClick={function(e) { e.stopPropagation(); onDelete(conv._id) }}
            className="p-1.5 rounded hover:bg-red-50 text-red-300 hover:text-red-400 transition-colors"
          >
            <Trash2 size={13} />
          </button>
          {expanded
            ? <ChevronDown size={14} className="text-violet" />
            : <ChevronRight size={14} className="text-dark/25" />
          }
        </div>
      </div>

      {expanded && (
        <div className="border-t border-navy/10 px-5 py-4 bg-navy/[0.015] space-y-3">
          <InfoRow icon={<Stethoscope size={13} />} label="SÍNTOMAS">
            {Array.isArray(conv.symptoms) && conv.symptoms.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {conv.symptoms.map(function(s, i) {
                  return (
                    <span key={i} className="bg-amber-50 text-amber-700 border border-amber-200 text-xs px-2 py-0.5 rounded-full font-body">
                      {s}
                    </span>
                  )
                })}
              </div>
            ) : (
              <span className="text-dark/30 italic text-xs">Sin síntomas registrados</span>
            )}
          </InfoRow>

          <InfoRow icon={<MapPin size={13} />} label="UBICACIÓN">
            {loc.text === 'Sin ubicación' ? (
              <span className="text-dark/30 italic text-xs">Sin ubicación registrada</span>
            ) : loc.isCoords && conv.location.lat != null && conv.location.lon != null ? (
              <LocationLink lat={conv.location.lat} lon={conv.location.lon} text={loc.text} />
            ) : (
              <span className="text-xs">{loc.text}</span>
            )}
          </InfoRow>

          <InfoRow icon={<Globe size={13} />} label="IDIOMA">
            <span className="text-xs">{formatLanguage(conv.language)}</span>
          </InfoRow>

          <MessageThread messages={conv.messages} senderId={conv.sender_id} />

          <InfoRow icon={<Stethoscope size={13} />} label="RECOMEND.">
            {conv.recommendation ? (
              <p className="text-xs leading-relaxed bg-forest/5 border border-forest/15 rounded-lg px-3 py-2 text-dark/70">
                {conv.recommendation}
              </p>
            ) : (
              <span className="text-dark/30 italic text-xs">Sin recomendación aún</span>
            )}
          </InfoRow>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// HistoricalCard
// ─────────────────────────────────────────────────────────────────
function HistoricalCard({ conv, onDelete }: { conv: HistoricalConversation; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const historyCount = Array.isArray(conv.history) ? conv.history.length : 0

  return (
    <div className="border border-navy/10 rounded-xl overflow-hidden shadow-sm bg-pearl transition-shadow hover:shadow-md">
      <div
        className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-violet/[0.03] transition-colors"
        onClick={function() { setExpanded(!expanded) }}
      >
        <div className="w-9 h-9 rounded-full bg-forest/10 border border-forest/20 flex items-center justify-center shrink-0">
          <Archive size={14} className="text-forest" />
        </div>

        <div className="flex-1 min-w-0">
          <p className="font-display text-sm text-dark tracking-wide truncate">{conv.sender_id || '—'}</p>
          <p className="text-xs text-dark/35 mt-0.5">
            {historyCount} conversación{historyCount !== 1 ? 'es' : ''} archivada{historyCount !== 1 ? 's' : ''}
          </p>
        </div>

        <Badge color="forest">{historyCount} archivos</Badge>

        <div className="flex items-center gap-2 ml-2">
          <button
            onClick={function(e) { e.stopPropagation(); onDelete(conv._id) }}
            className="p-1.5 rounded hover:bg-red-50 text-red-300 hover:text-red-400 transition-colors"
          >
            <Trash2 size={13} />
          </button>
          {expanded
            ? <ChevronDown size={14} className="text-violet" />
            : <ChevronRight size={14} className="text-dark/25" />
          }
        </div>
      </div>

      {expanded && (
        <div className="border-t border-navy/10 bg-navy/[0.015]">
          {Array.isArray(conv.history) && conv.history.length > 0 ? (
            conv.history.map(function(h, i) {
              const hLoc = formatLocation(h.location)
              const hMsgCount = Array.isArray(h.messages) ? h.messages.length : 0
              return (
                <div key={i} className={'px-5 py-3 ' + (i < conv.history.length - 1 ? 'border-b border-navy/10' : '')}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-display text-xs text-violet/60 tracking-widest">{'ARCHIVO #' + (i + 1)}</span>
                    {h.archived_at && (
                      <span className="text-xs text-dark/25 font-display">
                        {'· ' + new Date(h.archived_at).toLocaleDateString('es-GT')}
                      </span>
                    )}
                    <span className="ml-auto text-xs text-dark/30">{hMsgCount} mensajes</span>
                  </div>
                  <div className="space-y-2">
                    {Array.isArray(h.symptoms) && h.symptoms.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {h.symptoms.map(function(s: string, j: number) {
                          return (
                            <span key={j} className="bg-amber-50 text-amber-700 border border-amber-200 text-xs px-2 py-0.5 rounded-full">
                              {s}
                            </span>
                          )
                        })}
                      </div>
                    )}
                    {hLoc.text !== 'Sin ubicación' && (
                      <div className="flex items-center gap-1.5 text-xs text-dark/45">
                        <MapPin size={11} className="text-violet/40" />
                        {hLoc.isCoords && h.location && h.location.lat != null && h.location.lon != null ? (
                          <LocationLink lat={h.location.lat} lon={h.location.lon} text={hLoc.text} />
                        ) : (
                          <span>{hLoc.text}</span>
                        )}
                      </div>
                    )}
                    {h.recommendation && (
                      <p className="text-xs text-dark/50 bg-forest/5 border border-forest/10 rounded px-2.5 py-1.5 leading-relaxed">
                        {h.recommendation}
                      </p>
                    )}
                  </div>
                </div>
              )
            })
          ) : (
            <p className="px-5 py-4 text-xs text-dark/25 font-display">SIN HISTORIAL</p>
          )}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Section
// ─────────────────────────────────────────────────────────────────
function Section({ title, subtitle, icon, count, total, loading, children }: {
  title: string
  subtitle: string
  icon: React.ReactNode
  count: number
  total: number
  loading: boolean
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-lg bg-violet/10 border border-violet/15 flex items-center justify-center">
          {icon}
        </div>
        <div>
          <h3 className="font-display text-sm text-navy tracking-widest uppercase">{title}</h3>
          <p className="text-xs text-dark/35">{subtitle}</p>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          {!loading && count !== total && (
            <span className="text-xs text-dark/30 font-display">{count} de {total}</span>
          )}
          <Badge color={loading ? 'navy' : 'violet'}>{loading ? '...' : count}</Badge>
        </div>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────
export default function TabConversaciones() {
  const [ongoing, setOngoing] = useState<OngoingConversation[]>([])
  const [historical, setHistorical] = useState<HistoricalConversation[]>([])
  const [loadingOngoing, setLoadingOngoing] = useState(true)
  const [loadingHistorical, setLoadingHistorical] = useState(true)
  const [ongoingFilters, setOngoingFilters] = useState<OngoingFilters>(defaultOngoingFilters)
  const [historicalFilters, setHistoricalFilters] = useState<HistoricalFilters>({ search: '' })

  const loadOngoing = async () => {
    setLoadingOngoing(true)
    try {
      const res = await fetch(API_BASE + '/ongoing_conversations?limit=200')
      const json = await res.json()
      setOngoing(json.data ?? [])
    } catch { setOngoing([]) }
    setLoadingOngoing(false)
  }

  const loadHistorical = async () => {
    setLoadingHistorical(true)
    try {
      const res = await fetch(API_BASE + '/historical_conversations?limit=200')
      const json = await res.json()
      setHistorical(json.data ?? [])
    } catch { setHistorical([]) }
    setLoadingHistorical(false)
  }

  useEffect(function() { loadOngoing(); loadHistorical() }, [])

  const deleteOngoing = async (id: string) => {
    if (!confirm('¿Eliminar esta conversación en curso?')) return
    await fetch(API_BASE + '/ongoing_conversations/' + id, { method: 'DELETE' })
    loadOngoing()
  }

  const deleteHistorical = async (id: string) => {
    if (!confirm('¿Eliminar este historial?')) return
    await fetch(API_BASE + '/historical_conversations/' + id, { method: 'DELETE' })
    loadHistorical()
  }

  const filteredOngoing = useMemo(
    function() { return applyOngoingFilters(ongoing, ongoingFilters) },
    [ongoing, ongoingFilters]
  )
  const filteredHistorical = useMemo(
    function() { return applyHistoricalFilters(historical, historicalFilters) },
    [historical, historicalFilters]
  )
  const languages = useMemo(function() { return getUniqueLanguages(ongoing) }, [ongoing])
  const activeOngoingFilters = useMemo(function() { return countActiveFilters(ongoingFilters) }, [ongoingFilters])

  const EmptyState = function({ label }: { label: string }) {
    return (
      <div className="text-center py-12 border border-dashed border-navy/15 rounded-xl">
        <p className="text-dark/20 font-display text-xs tracking-widest">{label}</p>
      </div>
    )
  }

  const LoadingState = function() {
    return (
      <div className="text-center py-12">
        <p className="text-dark/25 font-display text-xs tracking-widest">CARGANDO...</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h2 className="font-display text-navy text-lg">CONVERSACIONES</h2>
        <button
          onClick={function() { loadOngoing(); loadHistorical() }}
          className="flex items-center gap-2 border border-navy/15 text-dark/40 hover:text-dark/70 px-3 py-1.5 rounded text-xs font-display transition-colors hover:bg-navy/5"
        >
          <RefreshCw size={12} />
          ACTUALIZAR
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">

        {/* ── En Curso ── */}
        <div>
          <Section
            title="En Curso"
            subtitle="Conversaciones activas en WhatsApp"
            icon={<MessageSquare size={14} className="text-violet" />}
            count={filteredOngoing.length}
            total={ongoing.length}
            loading={loadingOngoing}
          >
            {!loadingOngoing && (
              <OngoingFiltersPanel
                filters={ongoingFilters}
                onChange={setOngoingFilters}
                languages={languages}
                onReset={function() { setOngoingFilters(defaultOngoingFilters) }}
                activeCount={activeOngoingFilters}
              />
            )}
            {loadingOngoing
              ? <LoadingState />
              : filteredOngoing.length === 0
                ? <EmptyState label={activeOngoingFilters > 0 ? 'SIN RESULTADOS PARA ESTOS FILTROS' : 'SIN CONVERSACIONES ACTIVAS'} />
                : filteredOngoing.map(function(c) { return <OngoingCard key={c._id} conv={c} onDelete={deleteOngoing} /> })
            }
          </Section>
        </div>

        {/* ── Históricas ── */}
        <div>
          <Section
            title="Históricas"
            subtitle="Conversaciones archivadas"
            icon={<Archive size={14} className="text-forest" />}
            count={filteredHistorical.length}
            total={historical.length}
            loading={loadingHistorical}
          >
            {!loadingHistorical && (
              <div className="mb-4">
                <div className="relative max-w-xs">
                  <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-dark/30" />
                  <input
                    type="text"
                    placeholder="Buscar por número..."
                    value={historicalFilters.search}
                    onChange={function(e) { setHistoricalFilters({ search: e.target.value }) }}
                    className="w-full pl-7 pr-7 py-1.5 text-xs border border-navy/15 rounded bg-pearl text-dark/70 focus:outline-none focus:border-violet transition-colors font-body placeholder:text-dark/25"
                  />
                  {historicalFilters.search && (
                    <button
                      onClick={function() { setHistoricalFilters({ search: '' }) }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-dark/25 hover:text-dark/50"
                    >
                      <X size={11} />
                    </button>
                  )}
                </div>
              </div>
            )}
            {loadingHistorical
              ? <LoadingState />
              : filteredHistorical.length === 0
                ? <EmptyState label={historicalFilters.search ? 'SIN RESULTADOS' : 'SIN HISTORIAL'} />
                : filteredHistorical.map(function(c) { return <HistoricalCard key={c._id} conv={c} onDelete={deleteHistorical} /> })
            }
          </Section>
        </div>

      </div>
    </div>
  )
}