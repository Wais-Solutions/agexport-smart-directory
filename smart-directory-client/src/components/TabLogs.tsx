'use client'
import { useState, useEffect, useRef } from 'react'
import { RefreshCw, Trash2 } from 'lucide-react'

type Log = { _id: string; nivel: string; mensaje: string; timestamp: string; datos?: any }

const levelStyle: Record<string, string> = {
  error: 'text-red-500',
  warn:  'text-yellow-600',
  info:  'text-forest',
  debug: 'text-dark/30',
}

const filterActive = 'bg-violet text-pearl'
const filterInactive = 'border border-navy/15 text-dark/40 hover:text-dark/60 hover:bg-navy/5'

export default function TabLogs() {
  const [logs, setLogs] = useState<Log[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const bottomRef = useRef<HTMLDivElement>(null)

  const load = async () => {
    setLoading(true)
    const res = await fetch('/api/logs')
    setLogs(await res.json())
    setLoading(false)
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
  }

  useEffect(() => { load() }, [])

  const clearAll = async () => {
    if (!confirm('¿Limpiar todos los logs?')) return
    await fetch('/api/logs', { method: 'DELETE' })
    load()
  }

  const filtered = filter === 'all' ? logs : logs.filter(l => l.nivel === filter)

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="font-display text-navy text-lg">LOGS</h2>
        <div className="flex gap-2">
          {['all', 'info', 'warn', 'error', 'debug'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded text-xs font-display transition-colors ${filter === f ? filterActive : filterInactive}`}
            >
              {f.toUpperCase()}
            </button>
          ))}
          <button onClick={load} className="p-2 hover:bg-navy/5 rounded text-dark/40 hover:text-dark transition-colors">
            <RefreshCw size={14} />
          </button>
          <button onClick={clearAll} className="p-2 hover:bg-red-100 rounded text-red-400/60 hover:text-red-400 transition-colors">
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <div className="bg-navy/[0.03] rounded-lg border border-navy/10 p-4 h-[60vh] overflow-y-auto font-display text-xs space-y-1 shadow-sm">
        {loading ? (
          <div className="text-dark/20 text-center py-12">CARGANDO...</div>
        ) : filtered.map((log, i) => (
          <div key={log._id || i} className="flex gap-3 py-1 border-b border-navy/5 hover:bg-navy/5 rounded px-1 transition-colors">
            <span className="text-dark/25 shrink-0">{new Date(log.timestamp).toLocaleTimeString('es-GT')}</span>
            <span className={`uppercase shrink-0 w-10 ${levelStyle[log.nivel] || 'text-dark/40'}`}>{log.nivel}</span>
            <span className="text-dark/55 flex-1 break-all">{log.mensaje}</span>
          </div>
        ))}
        {!loading && filtered.length === 0 && <div className="text-dark/20 text-center py-12">SIN LOGS</div>}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}