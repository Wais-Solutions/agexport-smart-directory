'use client'
import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight, Trash2 } from 'lucide-react'

type Conversacion = { _id: string; numero: string; idioma: string; estado: string; updatedAt: string; mensajes?: any[] }

export default function TabConversaciones() {
  const [data, setData] = useState<Conversacion[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    const res = await fetch('/api/conversaciones')
    setData(await res.json())
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const remove = async (id: string) => {
    if (!confirm('¿Eliminar conversación?')) return
    await fetch(`/api/conversaciones/${id}`, { method: 'DELETE' })
    load()
  }

  return (
    <div>
      <h2 className="font-display text-navy text-lg mb-6">CONVERSACIONES</h2>
      {loading ? (
        <div className="text-dark/30 font-display text-sm text-center py-20">CARGANDO...</div>
      ) : (
        <div className="space-y-2">
          {data.map(c => (
            <div key={c._id} className="border border-navy/10 rounded-lg overflow-hidden shadow-sm">
              <div
                className="flex items-center gap-4 px-4 py-3 hover:bg-violet/5 cursor-pointer transition-colors bg-pearl"
                onClick={() => setExpanded(expanded === c._id ? null : c._id)}
              >
                {expanded === c._id
                  ? <ChevronDown size={14} className="text-violet" />
                  : <ChevronRight size={14} className="text-dark/30" />
                }
                <span className="font-display text-sm text-dark">{c.numero}</span>
                <span className="text-xs bg-navy/10 px-2 py-0.5 rounded font-display text-dark/50">{c.idioma?.toUpperCase()}</span>
                <span className={`text-xs px-2 py-0.5 rounded font-display ml-auto ${c.estado === 'activo' ? 'bg-forest/10 text-forest' : 'bg-navy/10 text-dark/40'}`}>
                  {c.estado?.toUpperCase()}
                </span>
                <span className="text-xs text-dark/30 font-display">{new Date(c.updatedAt).toLocaleDateString('es-GT')}</span>
                <button
                  onClick={e => { e.stopPropagation(); remove(c._id) }}
                  className="p-1.5 hover:bg-red-100 rounded text-red-400 transition-colors ml-2"
                >
                  <Trash2 size={12} />
                </button>
              </div>
              {expanded === c._id && (
                <div className="border-t border-navy/10 bg-navy/[0.03] p-4">
                  <pre className="text-xs text-dark/50 font-display overflow-auto max-h-60 whitespace-pre-wrap">
                    {JSON.stringify(c, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
          {data.length === 0 && <div className="text-center py-12 text-dark/20 font-display text-xs">SIN REGISTROS</div>}
        </div>
      )}
    </div>
  )
}