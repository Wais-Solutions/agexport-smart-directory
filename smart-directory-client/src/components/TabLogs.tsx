'use client'
import { useState, useEffect } from 'react'
import { RefreshCw, Trash2, ChevronDown, ChevronRight, ChevronLeft, AlertCircle, Info, AlertTriangle, Bug, Search, X } from 'lucide-react'

const API_BASE = 'https://agexport-smart-directory.onrender.com/db'
const PAGE_SIZE = 25

type Log = {
  _id: string
  timestamp: string
  level: string
  message: string
  sender_id?: string
  extra_data?: Record<string, any>
}

// ── Helpers ────────────────────────────────────────────────────────────────
function formatTimestamp(ts: string): string {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleDateString('es-GT', { day: '2-digit', month: '2-digit', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('es-GT', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

type LevelConfig = { bg: string; text: string; border: string; icon: React.ReactNode; label: string }

function getLevelConfig(level: string): LevelConfig {
  switch (level?.toUpperCase()) {
    case 'ERROR':
      return { bg: 'bg-red-50', text: 'text-red-600', border: 'border-red-200', icon: <AlertCircle size={12} />, label: 'ERROR' }
    case 'WARNING':
    case 'WARN':
      return { bg: 'bg-amber-50', text: 'text-amber-600', border: 'border-amber-200', icon: <AlertTriangle size={12} />, label: 'WARN' }
    case 'DEBUG':
      return { bg: 'bg-navy/5', text: 'text-dark/40', border: 'border-navy/10', icon: <Bug size={12} />, label: 'DEBUG' }
    default: // INFO
      return { bg: 'bg-forest/5', text: 'text-forest', border: 'border-forest/20', icon: <Info size={12} />, label: 'INFO' }
  }
}

function hasExtraData(extra: Record<string, any> | undefined): boolean {
  if (!extra) return false
  return Object.keys(extra).length > 0 && Object.values(extra).some(v => v !== null && v !== undefined && v !== '')
}

// ── JsonValue: renderiza valores de extra_data con pretty-print para JSON strings ──
function JsonValue({ value }: { value: any }) {
  if (value === null || value === undefined) return <span className="text-dark/25 italic">null</span>

  // Intenta parsear strings que parezcan JSON
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if ((trimmed.startsWith('{') || trimmed.startsWith('[')) && trimmed.length > 2) {
      try {
        const parsed = JSON.parse(trimmed)
        return (
          <pre className="text-dark/55 font-mono text-xs break-all whitespace-pre-wrap bg-navy/[0.03] border border-navy/8 rounded p-2 mt-1 leading-relaxed">
            {JSON.stringify(parsed, null, 2)}
          </pre>
        )
      } catch { /* not json, fall through */ }
    }
    return <span className="text-dark/55 font-mono break-all leading-relaxed">{value}</span>
  }

  if (typeof value === 'object') {
    return (
      <pre className="text-dark/55 font-mono text-xs break-all whitespace-pre-wrap bg-navy/[0.03] border border-navy/8 rounded p-2 mt-1 leading-relaxed">
        {JSON.stringify(value, null, 2)}
      </pre>
    )
  }

  return <span className="text-dark/55 font-mono">{String(value)}</span>
}

// ── LogRow ─────────────────────────────────────────────────────────────────
function LogRow({ log }: { log: Log }) {
  const [expanded, setExpanded] = useState(false)
  const lvl = getLevelConfig(log.level)
  const hasExtra = hasExtraData(log.extra_data)
  const isClickable = hasExtra || !!log.sender_id

  return (
    <div className={'border rounded-lg overflow-hidden transition-shadow hover:shadow-sm ' + lvl.border}>

      {/* Main row */}
      <div
        className={'flex items-start gap-3 px-4 py-3 transition-colors ' + (isClickable ? 'cursor-pointer hover:bg-navy/[0.02]' : '')}
        onClick={function() { if (isClickable) setExpanded(!expanded) }}
      >
        {/* Level badge */}
        <span className={'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-display shrink-0 mt-0.5 border ' + lvl.bg + ' ' + lvl.text + ' ' + lvl.border}>
          {lvl.icon}
          {lvl.label}
        </span>

        {/* Timestamp */}
        <span className="text-xs text-dark/30 font-display shrink-0 mt-0.5 w-36">
          {formatTimestamp(log.timestamp)}
        </span>

        {/* sender_id pill (si existe en raíz) */}
        {log.sender_id && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-display shrink-0 mt-0.5 bg-violet/8 text-violet/70 border border-violet/15">
            📱 {log.sender_id}
          </span>
        )}

        {/* Message */}
        <span className="text-sm text-dark/70 flex-1 leading-relaxed">
          {log.message}
        </span>

        {/* Expand toggle */}
        {isClickable && (
          <span className="shrink-0 mt-0.5">
            {expanded
              ? <ChevronDown size={13} className="text-violet/50" />
              : <ChevronRight size={13} className="text-dark/20" />
            }
          </span>
        )}
      </div>

      {/* Expanded: extra_data */}
      {expanded && (hasExtra || log.sender_id) && (
        <div className="border-t border-navy/8 bg-navy/[0.015] px-4 py-3 space-y-3">

          {/* sender_id si no está en extra_data ya */}
          {log.sender_id && !(log.extra_data && 'sender_id' in log.extra_data) && (
            <div className="flex items-start gap-3 text-xs">
              <span className="font-display text-violet/50 shrink-0 w-32 pt-0.5">sender_id</span>
              <span className="text-dark/60 font-mono">{log.sender_id}</span>
            </div>
          )}

          {/* extra_data fields */}
          {hasExtra && (
            <>
              <p className="font-display text-xs text-dark/25 tracking-widest">EXTRA DATA</p>
              <div className="space-y-2">
                {Object.entries(log.extra_data!).map(function([key, value]) {
                  if (value === null || value === undefined || value === '') return null
                  return (
                    <div key={key} className="flex items-start gap-3 text-xs">
                      <span className="font-display text-violet/50 shrink-0 w-32 pt-0.5 truncate">{key}</span>
                      <div className="flex-1 min-w-0">
                        <JsonValue value={value} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          )}

        </div>
      )}

    </div>
  )
}

// ── Filter tabs ────────────────────────────────────────────────────────────
const LEVELS = ['ALL', 'INFO', 'ERROR', 'WARNING', 'DEBUG'] as const
type LevelFilter = typeof LEVELS[number]

// ── Main ───────────────────────────────────────────────────────────────────
export default function TabLogs() {
  const [logs, setLogs] = useState<Log[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [filter, setFilter] = useState<LevelFilter>('ALL')
  const [senderSearch, setSenderSearch] = useState('')

  const load = async (pageIndex: number, levelFilter: LevelFilter) => {
    setLoading(true)
    try {
      const skip = pageIndex * PAGE_SIZE
      const res = await fetch(API_BASE + '/debugging-logs?limit=' + PAGE_SIZE + '&skip=' + skip)
      const json = await res.json()
      const allLogs: Log[] = json.data ?? []

      if (levelFilter === 'ALL') {
        setLogs(allLogs)
        setTotal(json.total ?? 0)
      } else {
        // Filter client-side within the page
        const filtered = allLogs.filter(function(l) {
          return l.level?.toUpperCase() === levelFilter ||
            (levelFilter === 'WARNING' && l.level?.toUpperCase() === 'WARN')
        })
        setLogs(filtered)
        setTotal(json.total ?? 0)
      }
    } catch {
      setLogs([])
      setTotal(0)
    }
    setLoading(false)
  }

  useEffect(function() { load(page, filter) }, [page, filter])

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const canPrev = page > 0
  const canNext = page < totalPages - 1

  // Filtro client-side por sender_id (busca en raíz y en extra_data)
  const displayLogs = senderSearch.trim()
    ? logs.filter(function(l) {
        const s = senderSearch.trim().toLowerCase()
        const inRoot = (l.sender_id || '').toLowerCase().includes(s)
        const inExtra = l.extra_data && (l.extra_data.sender_id || '').toString().toLowerCase().includes(s)
        return inRoot || inExtra
      })
    : logs

  function handleFilter(lvl: LevelFilter) {
    setFilter(lvl)
    setPage(0)
  }

  function handleClearLogs() {
    if (!confirm('¿Limpiar TODOS los logs? Esta acción no se puede deshacer.')) return
    fetch(API_BASE + '/debugging-logs', { method: 'DELETE' })
      .then(function() { setPage(0); load(0, filter) })
  }

  const levelTabStyle = function(lvl: LevelFilter) {
    const base = 'px-3 py-1.5 text-xs font-display rounded transition-colors '
    if (filter === lvl) {
      const active: Record<LevelFilter, string> = {
        ALL:     'bg-violet text-pearl',
        INFO:    'bg-forest/15 text-forest border border-forest/25',
        ERROR:   'bg-red-100 text-red-600 border border-red-200',
        WARNING: 'bg-amber-100 text-amber-600 border border-amber-200',
        DEBUG:   'bg-navy/10 text-dark/60 border border-navy/20',
      }
      return base + active[lvl]
    }
    return base + 'border border-navy/15 text-dark/35 hover:text-dark/60 hover:bg-navy/5'
  }

  return (
    <div>

      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <h2 className="font-display text-navy text-lg">LOGS</h2>

        {/* Level filters */}
        <div className="flex items-center gap-1.5 ml-4">
          {LEVELS.map(function(lvl) {
            return (
              <button key={lvl} onClick={function() { handleFilter(lvl) }} className={levelTabStyle(lvl)}>
                {lvl}
              </button>
            )
          })}
        </div>

        <div className="ml-auto flex items-center gap-2">
          {/* Buscar por sender */}
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-dark/30" />
            <input
              type="text"
              placeholder="Buscar número..."
              value={senderSearch}
              onChange={function(e) { setSenderSearch(e.target.value) }}
              className="pl-7 pr-7 py-1.5 text-xs border border-navy/15 rounded bg-pearl text-dark/70 w-40 focus:outline-none focus:border-violet transition-colors font-body placeholder:text-dark/25"
            />
            {senderSearch && (
              <button
                onClick={function() { setSenderSearch('') }}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-dark/25 hover:text-dark/50"
              >
                <X size={11} />
              </button>
            )}
          </div>
          <button
            onClick={function() { load(page, filter) }}
            className="flex items-center gap-1.5 border border-navy/15 text-dark/40 hover:text-dark/70 px-3 py-1.5 rounded text-xs font-display transition-colors hover:bg-navy/5"
          >
            <RefreshCw size={12} />
            ACTUALIZAR
          </button>
          <button
            onClick={handleClearLogs}
            className="flex items-center gap-1.5 border border-red-200 text-red-300 hover:text-red-500 hover:bg-red-50 px-3 py-1.5 rounded text-xs font-display transition-colors"
          >
            <Trash2 size={12} />
            LIMPIAR
          </button>
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-4 mb-4 px-1">
        <span className="text-xs text-dark/30 font-display">
          {total} logs en total
          {filter !== 'ALL' && (' · ' + filter)}
          {senderSearch && (' · número: ' + senderSearch)}
          {senderSearch && displayLogs.length !== logs.length && (' → ' + displayLogs.length + ' resultados')}
        </span>
        {totalPages > 1 && (
          <span className="text-xs text-dark/25 font-display ml-auto">
            {'Página ' + (page + 1) + ' de ' + totalPages}
          </span>
        )}
      </div>

      {/* Log list */}
      {loading ? (
        <div className="text-center py-16">
          <p className="text-dark/25 font-display text-xs tracking-widest">CARGANDO...</p>
        </div>
      ) : displayLogs.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-navy/15 rounded-xl">
          <p className="text-dark/20 font-display text-xs tracking-widest">
            {senderSearch ? 'SIN RESULTADOS PARA ESTE NÚMERO' : 'SIN LOGS'}
          </p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {displayLogs.map(function(log) {
            return <LogRow key={log._id} log={log} />
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-6">
          <button
            onClick={function() { setPage(page - 1) }}
            disabled={!canPrev}
            className="flex items-center gap-1.5 px-4 py-2 rounded border text-xs font-display transition-colors disabled:opacity-30 disabled:cursor-not-allowed border-navy/15 text-dark/50 hover:bg-navy/5 hover:text-dark/70"
          >
            <ChevronLeft size={13} />
            ANTERIOR
          </button>

          {/* Page numbers */}
          <div className="flex items-center gap-1">
            {Array.from({ length: totalPages }, function(_, i) { return i }).map(function(i) {
              if (totalPages > 7 && Math.abs(i - page) > 2 && i !== 0 && i !== totalPages - 1) {
                if (i === 1 && page > 3) return <span key={i} className="text-dark/20 text-xs px-1">…</span>
                if (i === totalPages - 2 && page < totalPages - 4) return <span key={i} className="text-dark/20 text-xs px-1">…</span>
                if (Math.abs(i - page) > 2) return null
              }
              return (
                <button
                  key={i}
                  onClick={function() { setPage(i) }}
                  className={'w-8 h-8 rounded text-xs font-display transition-colors ' +
                    (i === page
                      ? 'bg-violet text-pearl'
                      : 'text-dark/40 hover:bg-navy/5 hover:text-dark/70'
                    )
                  }
                >
                  {i + 1}
                </button>
              )
            })}
          </div>

          <button
            onClick={function() { setPage(page + 1) }}
            disabled={!canNext}
            className="flex items-center gap-1.5 px-4 py-2 rounded border text-xs font-display transition-colors disabled:opacity-30 disabled:cursor-not-allowed border-navy/15 text-dark/50 hover:bg-navy/5 hover:text-dark/70"
          >
            SIGUIENTE
            <ChevronRight size={13} />
          </button>
        </div>
      )}

    </div>
  )
}