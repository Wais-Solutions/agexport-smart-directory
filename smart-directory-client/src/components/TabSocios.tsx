'use client'
import { useState, useEffect } from 'react'
import { Plus, Pencil, Trash2, X, Check } from 'lucide-react'

type Socio = { _id?: string; nombre: string; telefono: string; especialidad: string; ubicacion: string; activo: boolean }

const empty: Socio = { nombre: '', telefono: '', especialidad: '', ubicacion: '', activo: true }

export default function TabSocios() {
  const [socios, setSocios] = useState<Socio[]>([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState<Socio>(empty)
  const [editing, setEditing] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    const res = await fetch('/api/socios')
    const data = await res.json()
    setSocios(data)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const save = async () => {
    if (editing) {
      await fetch(`/api/socios/${editing}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) })
    } else {
      await fetch('/api/socios', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) })
    }
    setModal(false); setForm(empty); setEditing(null); load()
  }

  const remove = async (id: string) => {
    if (!confirm('¿Eliminar socio?')) return
    await fetch(`/api/socios/${id}`, { method: 'DELETE' })
    load()
  }

  const openEdit = (s: Socio) => { setForm(s); setEditing(s._id!); setModal(true) }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="font-display text-navy text-lg">SOCIOS</h2>
        <button
          onClick={() => { setForm(empty); setEditing(null); setModal(true) }}
          className="flex items-center gap-2 bg-violet hover:bg-violet/80 text-pearl px-4 py-2 rounded text-sm font-display transition-colors"
        >
          <Plus size={14} /> NUEVO
        </button>
      </div>

      {loading ? (
        <div className="text-dark/30 font-display text-sm text-center py-20">CARGANDO...</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-navy/10 shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-navy/10 bg-navy/5">
                {['Nombre', 'Teléfono', 'Especialidad', 'Ubicación', 'Estado', 'Acciones'].map(h => (
                  <th key={h} className="text-left px-4 py-3 font-display text-xs text-violet tracking-widest">{h.toUpperCase()}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {socios.map((s, i) => (
                <tr key={s._id} className={`border-b border-navy/5 hover:bg-violet/5 transition-colors ${i % 2 === 0 ? 'bg-pearl' : 'bg-navy/[0.02]'}`}>
                  <td className="px-4 py-3 text-dark font-medium">{s.nombre}</td>
                  <td className="px-4 py-3 text-dark/60">{s.telefono}</td>
                  <td className="px-4 py-3 text-dark/60">{s.especialidad}</td>
                  <td className="px-4 py-3 text-dark/60">{s.ubicacion}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-display ${s.activo ? 'bg-forest/15 text-forest' : 'bg-red-100 text-red-500'}`}>
                      {s.activo ? 'ACTIVO' : 'INACTIVO'}
                    </span>
                  </td>
                  <td className="px-4 py-3 flex gap-2">
                    <button onClick={() => openEdit(s)} className="p-1.5 hover:bg-violet/10 rounded text-violet transition-colors"><Pencil size={13} /></button>
                    <button onClick={() => remove(s._id!)} className="p-1.5 hover:bg-red-100 rounded text-red-400 transition-colors"><Trash2 size={13} /></button>
                  </td>
                </tr>
              ))}
              {socios.length === 0 && (
                <tr><td colSpan={6} className="text-center py-12 text-dark/20 font-display text-xs">SIN REGISTROS</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {modal && (
        <div className="fixed inset-0 bg-navy/30 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-pearl border border-navy/10 rounded-xl p-6 w-full max-w-md shadow-2xl">
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-display text-violet text-sm tracking-widest">{editing ? 'EDITAR SOCIO' : 'NUEVO SOCIO'}</h3>
              <button onClick={() => setModal(false)} className="text-dark/30 hover:text-dark transition-colors"><X size={16} /></button>
            </div>
            <div className="space-y-3">
              {(['nombre', 'telefono', 'especialidad', 'ubicacion'] as const).map(field => (
                <div key={field}>
                  <label className="block text-xs font-display text-dark/40 mb-1 tracking-widest uppercase">{field}</label>
                  <input
                    value={form[field]}
                    onChange={e => setForm({ ...form, [field]: e.target.value })}
                    className="w-full bg-navy/5 border border-navy/10 rounded px-3 py-2 text-dark text-sm focus:outline-none focus:border-violet transition-colors"
                  />
                </div>
              ))}
              <label className="flex items-center gap-3 cursor-pointer">
                <div
                  onClick={() => setForm({ ...form, activo: !form.activo })}
                  className={`w-10 h-5 rounded-full transition-colors ${form.activo ? 'bg-forest' : 'bg-navy/20'} relative`}
                >
                  <div className={`w-4 h-4 bg-pearl rounded-full absolute top-0.5 transition-all shadow-sm ${form.activo ? 'left-5' : 'left-0.5'}`} />
                </div>
                <span className="text-sm text-dark/60">Activo</span>
              </label>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setModal(false)} className="flex-1 border border-navy/20 text-dark/50 py-2 rounded text-sm font-display hover:bg-navy/5 transition-colors">CANCELAR</button>
              <button onClick={save} className="flex-1 bg-violet hover:bg-violet/80 text-pearl py-2 rounded text-sm font-display transition-colors flex items-center justify-center gap-2"><Check size={14} /> GUARDAR</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}