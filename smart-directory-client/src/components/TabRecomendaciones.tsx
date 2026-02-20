'use client'
import { useState, useEffect } from 'react'
import { Trash2 } from 'lucide-react'

type Rec = { _id: string; paciente: string; socio: string; sintomas: string; fecha: string; estado: string }

export default function TabRecomendaciones() {
  const [data, setData] = useState<Rec[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    const res = await fetch('/api/recomendaciones')
    setData(await res.json())
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const remove = async (id: string) => {
    if (!confirm('¿Eliminar?')) return
    await fetch(`/api/recomendaciones/${id}`, { method: 'DELETE' })
    load()
  }

  const statusColor: Record<string, string> = {
    pendiente: 'bg-yellow-50 text-yellow-600',
    aceptado: 'bg-forest/10 text-forest',
    rechazado: 'bg-red-50 text-red-500',
  }

  return (
    <div>
      <h2 className="font-display text-navy text-lg mb-6">HISTORIAL DE RECOMENDACIONES</h2>
      {loading ? (
        <div className="text-dark/30 font-display text-sm text-center py-20">CARGANDO...</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-navy/10 shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-navy/10 bg-navy/5">
                {['Paciente', 'Socio', 'Síntomas', 'Fecha', 'Estado', ''].map((h, i) => (
                  <th key={i} className="text-left px-4 py-3 font-display text-xs text-violet tracking-widest">{h.toUpperCase()}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((r, i) => (
                <tr key={r._id} className={`border-b border-navy/5 hover:bg-violet/5 transition-colors ${i % 2 === 0 ? 'bg-pearl' : 'bg-navy/[0.02]'}`}>
                  <td className="px-4 py-3 text-dark font-medium">{r.paciente}</td>
                  <td className="px-4 py-3 text-dark/60">{r.socio}</td>
                  <td className="px-4 py-3 text-dark/60 max-w-xs truncate">{r.sintomas}</td>
                  <td className="px-4 py-3 text-dark/40 text-xs font-display">{new Date(r.fecha).toLocaleDateString('es-GT')}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-display uppercase ${statusColor[r.estado] || 'bg-navy/10 text-dark/50'}`}>{r.estado}</span>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => remove(r._id)} className="p-1.5 hover:bg-red-100 rounded text-red-400 transition-colors"><Trash2 size={13} /></button>
                  </td>
                </tr>
              ))}
              {data.length === 0 && <tr><td colSpan={6} className="text-center py-12 text-dark/20 font-display text-xs">SIN REGISTROS</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}