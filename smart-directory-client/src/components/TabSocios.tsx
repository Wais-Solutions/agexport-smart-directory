'use client'
import { useState, useEffect, useMemo } from 'react'
import { Pencil, Trash2, X, Check, Search, ChevronDown, ChevronRight, Phone, MapPin, RefreshCw, Plus, SlidersHorizontal } from 'lucide-react'

//const API_BASE = process.env.NEXT_PUBLIC_API_URL + '/db'
const API_BASE = 'https://agexport-smart-directory.onrender.com/db'

// ─────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────
type GeoLocation = {
  query?: string
  name?: string
  address?: string
  lat?: number
  lon?: number
  place_id?: string
  maps_url?: string
}

type Partner = {
  _id: string
  partner_name: string
  partner_category: string
  partner_services: string[]
  partner_phone_number?: string[]
  partner_whatsapp?: string[]
  partner_locations?: string[]
  partner_geo_locations?: GeoLocation[]
}

type EditForm = {
  partner_name: string
  partner_category: string
  partner_services: string[]
}

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────
function getUniqueCategories(partners: Partner[]): string[] {
  const set = new Set<string>()
  partners.forEach(function(p) { if (p.partner_category) set.add(p.partner_category) })
  return Array.from(set).sort()
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
      className="inline-flex items-center gap-1 text-xs text-violet hover:underline"
      onClick={function(e) { e.stopPropagation() }}
    >
      <MapPin size={10} />
      {label}
    </a>
  )
}

// ─────────────────────────────────────────────────────────────────
// EditModal
// ─────────────────────────────────────────────────────────────────
function EditModal({ partner, onClose, onSaved }: {
  partner: Partner
  onClose: () => void
  onSaved: (updated: Partner) => void
}) {
  const [form, setForm] = useState<EditForm>({
    partner_name: partner.partner_name,
    partner_category: partner.partner_category,
    partner_services: [...(partner.partner_services ?? [])],
  })
  const [saving, setSaving] = useState(false)
  const [newService, setNewService] = useState('')
  const [error, setError] = useState('')

  const save = async () => {
    if (!form.partner_name.trim()) { setError('El nombre es requerido'); return }
    if (!form.partner_category.trim()) { setError('La categoría es requerida'); return }
    setSaving(true)
    setError('')
    try {
      const res = await fetch(API_BASE + '/partners/' + partner._id, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error('Error al guardar')
      const updated = await res.json()
      onSaved(updated)
    } catch {
      setError('Error al guardar. Intenta de nuevo.')
    }
    setSaving(false)
  }

  const addService = () => {
    const s = newService.trim().toLowerCase()
    if (!s) return
    if (form.partner_services.includes(s)) { setNewService(''); return }
    setForm({ ...form, partner_services: [...form.partner_services, s] })
    setNewService('')
  }

  const removeService = (i: number) => {
    setForm({ ...form, partner_services: form.partner_services.filter(function(_, idx) { return idx !== i }) })
  }

  return (
    <div className="fixed inset-0 bg-navy/30 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-pearl border border-navy/10 rounded-2xl w-full max-w-lg shadow-2xl max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex justify-between items-center px-6 pt-6 pb-4 border-b border-navy/8 shrink-0">
          <div>
            <h3 className="font-display text-violet text-sm tracking-widest">EDITAR SOCIO</h3>
            <p className="text-xs text-dark/35 mt-0.5">{partner._id}</p>
          </div>
          <button onClick={onClose} className="text-dark/30 hover:text-dark transition-colors p-1">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4 space-y-4 overflow-y-auto flex-1">

          {/* Nombre */}
          <div>
            <label className="block text-xs font-display text-dark/40 mb-1.5 tracking-widest">NOMBRE</label>
            <input
              value={form.partner_name}
              onChange={function(e) { setForm({ ...form, partner_name: e.target.value }) }}
              className="w-full bg-navy/5 border border-navy/10 rounded-lg px-3 py-2 text-dark text-sm focus:outline-none focus:border-violet transition-colors"
            />
          </div>

          {/* Categoría */}
          <div>
            <label className="block text-xs font-display text-dark/40 mb-1.5 tracking-widest">CATEGORÍA</label>
            <input
              value={form.partner_category}
              onChange={function(e) { setForm({ ...form, partner_category: e.target.value }) }}
              className="w-full bg-navy/5 border border-navy/10 rounded-lg px-3 py-2 text-dark text-sm focus:outline-none focus:border-violet transition-colors"
            />
          </div>

          {/* Servicios */}
          <div>
            <label className="block text-xs font-display text-dark/40 mb-1.5 tracking-widest">
              SERVICIOS <span className="text-dark/25">({form.partner_services.length})</span>
            </label>

            {/* Add service */}
            <div className="flex gap-2 mb-3">
              <input
                value={newService}
                onChange={function(e) { setNewService(e.target.value) }}
                onKeyDown={function(e) { if (e.key === 'Enter') { e.preventDefault(); addService() } }}
                placeholder="Agregar servicio..."
                className="flex-1 bg-navy/5 border border-navy/10 rounded-lg px-3 py-2 text-dark text-xs focus:outline-none focus:border-violet transition-colors placeholder:text-dark/25"
              />
              <button
                onClick={addService}
                className="px-3 py-2 bg-violet hover:bg-violet/80 text-pearl rounded-lg text-xs font-display transition-colors"
              >
                <Plus size={13} />
              </button>
            </div>

            {/* Service chips */}
            <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto p-1">
              {form.partner_services.map(function(s, i) {
                return (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1.5 bg-navy/8 text-dark/60 border border-navy/12 text-xs px-2.5 py-1 rounded-full"
                  >
                    {s}
                    <button
                      onClick={function() { removeService(i) }}
                      className="text-dark/30 hover:text-red-400 transition-colors"
                    >
                      <X size={10} />
                    </button>
                  </span>
                )
              })}
              {form.partner_services.length === 0 && (
                <p className="text-xs text-dark/25 italic px-1">Sin servicios</p>
              )}
            </div>
          </div>

          {error && (
            <p className="text-xs text-red-500 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 px-6 py-4 border-t border-navy/8 shrink-0">
          <button
            onClick={onClose}
            className="flex-1 border border-navy/20 text-dark/50 py-2.5 rounded-lg text-sm font-display hover:bg-navy/5 transition-colors"
          >
            CANCELAR
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="flex-1 bg-violet hover:bg-violet/80 disabled:opacity-60 text-pearl py-2.5 rounded-lg text-sm font-display transition-colors flex items-center justify-center gap-2"
          >
            <Check size={14} />
            {saving ? 'GUARDANDO...' : 'GUARDAR'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// PartnerCard
// ─────────────────────────────────────────────────────────────────
function PartnerCard({ partner, onEdit, onDelete }: {
  partner: Partner
  onEdit: (p: Partner) => void
  onDelete: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const geo = partner.partner_geo_locations?.[0]

  return (
    <div className="border border-navy/10 rounded-xl overflow-hidden shadow-sm bg-pearl hover:shadow-md transition-shadow">

      {/* Header */}
      <div
        className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-violet/[0.02] transition-colors"
        onClick={function() { setExpanded(!expanded) }}
      >
        {/* Avatar inicial */}
        <div className="w-10 h-10 rounded-xl bg-violet/10 border border-violet/20 flex items-center justify-center shrink-0 font-display text-violet font-bold text-sm">
          {(partner.partner_name || '?')[0].toUpperCase()}
        </div>

        <div className="flex-1 min-w-0">
          <p className="font-display text-sm text-dark tracking-wide truncate">{partner.partner_name}</p>
          <p className="text-xs text-dark/40 mt-0.5">{partner.partner_category}</p>
        </div>

        {/* Phones */}
        <div className="hidden md:flex items-center gap-3 shrink-0">
          {partner.partner_phone_number && partner.partner_phone_number.length > 0 && (
            <span className="inline-flex items-center gap-1 text-xs text-dark/40">
              <Phone size={10} className="text-violet/50" />
              {partner.partner_phone_number[0]}
            </span>
          )}
          <span className="text-xs bg-navy/8 text-dark/50 border border-navy/12 px-2 py-0.5 rounded-full font-display">
            {(partner.partner_services ?? []).length} servicios
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 ml-2">
          <button
            onClick={function(e) { e.stopPropagation(); onEdit(partner) }}
            className="p-2 hover:bg-violet/10 rounded-lg text-violet/60 hover:text-violet transition-colors"
            title="Editar"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={function(e) { e.stopPropagation(); onDelete(partner._id) }}
            className="p-2 hover:bg-red-50 rounded-lg text-red-300 hover:text-red-400 transition-colors"
            title="Eliminar"
          >
            <Trash2 size={13} />
          </button>
          {expanded
            ? <ChevronDown size={14} className="text-violet ml-1" />
            : <ChevronRight size={14} className="text-dark/25 ml-1" />
          }
        </div>
      </div>

      {/* Expanded */}
      {expanded && (
        <div className="border-t border-navy/8 bg-navy/[0.012]">
          <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-navy/8">

            {/* Left: contact + location */}
            <div className="px-5 py-4 space-y-3">

              {/* Teléfonos */}
              {partner.partner_phone_number && partner.partner_phone_number.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-display text-dark/30 tracking-widest">TELÉFONO</p>
                  {partner.partner_phone_number.map(function(p, i) {
                    return (
                      <p key={i} className="text-xs text-dark/60 flex items-center gap-1.5 font-mono">
                        <Phone size={10} className="text-dark/25" />
                        {p}
                      </p>
                    )
                  })}
                </div>
              )}

              {/* WhatsApp */}
              {partner.partner_whatsapp && partner.partner_whatsapp.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-display text-dark/30 tracking-widest">WHATSAPP</p>
                  {partner.partner_whatsapp.map(function(p, i) {
                    const waUrl = 'https://wa.me/' + p.replace(/\D/g, '')
                    return (
                      <a key={i} href={waUrl} target="_blank" rel="noopener noreferrer"
                        onClick={function(e) { e.stopPropagation() }}
                        className="text-xs text-forest hover:underline flex items-center gap-1.5 font-mono">
                        <Phone size={10} className="text-forest/50" />
                        {p}
                      </a>
                    )
                  })}
                </div>
              )}

              {/* Ubicación */}
              {geo && (
                <div className="space-y-1">
                  <p className="text-xs font-display text-dark/30 tracking-widest">UBICACIÓN</p>
                  {geo.address && <p className="text-xs text-dark/55 leading-relaxed">{geo.address}</p>}
                  {geo.maps_url && <MapsLink url={geo.maps_url} label="Ver en Google Maps" />}
                </div>
              )}

              {/* Dirección texto si no hay geo */}
              {!geo && partner.partner_locations && partner.partner_locations.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-display text-dark/30 tracking-widest">DIRECCIÓN</p>
                  {partner.partner_locations.map(function(l, i) {
                    return <p key={i} className="text-xs text-dark/55 leading-relaxed">{l}</p>
                  })}
                </div>
              )}
            </div>

            {/* Right: services */}
            <div className="px-5 py-4">
              <p className="text-xs font-display text-dark/30 tracking-widest mb-2">
                SERVICIOS <span className="text-dark/20">({(partner.partner_services ?? []).length})</span>
              </p>
              <div className="flex flex-wrap gap-1.5">
                {(partner.partner_services ?? []).map(function(s, i) {
                  return (
                    <span key={i} className="bg-navy/6 text-dark/55 border border-navy/10 text-xs px-2 py-0.5 rounded-full">
                      {s}
                    </span>
                  )
                })}
                {(partner.partner_services ?? []).length === 0 && (
                  <p className="text-xs text-dark/20 italic">Sin servicios registrados</p>
                )}
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────
export default function TabSocios() {
  const [partners, setPartners] = useState<Partner[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [editingPartner, setEditingPartner] = useState<Partner | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await fetch(API_BASE + '/partners?limit=500')
      const json = await res.json()
      setPartners(json.data ?? [])
    } catch { setPartners([]) }
    setLoading(false)
  }

  useEffect(function() { load() }, [])

  const handleDelete = async (id: string) => {
    if (!confirm('¿Eliminar este socio? Esta acción no se puede deshacer.')) return
    await fetch(API_BASE + '/partners/' + id, { method: 'DELETE' })
    setPartners(function(prev) { return prev.filter(function(p) { return p._id !== id }) })
  }

  const handleSaved = (updated: Partner) => {
    setPartners(function(prev) {
      return prev.map(function(p) { return p._id === updated._id ? updated : p })
    })
    setEditingPartner(null)
  }

  const categories = useMemo(function() { return getUniqueCategories(partners) }, [partners])

  const filtered = useMemo(function() {
    return partners.filter(function(p) {
      const s = search.toLowerCase()
      if (s) {
        const inName = p.partner_name.toLowerCase().includes(s)
        const inCat = p.partner_category.toLowerCase().includes(s)
        const inServices = (p.partner_services ?? []).some(function(sv) { return sv.toLowerCase().includes(s) })
        if (!inName && !inCat && !inServices) return false
      }
      if (categoryFilter && p.partner_category !== categoryFilter) return false
      return true
    })
  }, [partners, search, categoryFilter])

  const activeFilters = (search ? 1 : 0) + (categoryFilter ? 1 : 0)

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="font-display text-navy text-lg">SOCIOS</h2>
          <p className="text-xs text-dark/35 mt-0.5">Partners registrados en el directorio</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 border border-navy/15 text-dark/40 hover:text-dark/70 px-3 py-1.5 rounded text-xs font-display transition-colors hover:bg-navy/5"
        >
          <RefreshCw size={12} />
          ACTUALIZAR
        </button>
      </div>

      {/* Filters */}
      {!loading && (
        <div className="mb-5 space-y-2">
          <div className="flex items-center gap-2">

            {/* Search */}
            <div className="relative flex-1 max-w-sm">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-dark/30" />
              <input
                type="text"
                placeholder="Buscar por nombre, categoría o servicio..."
                value={search}
                onChange={function(e) { setSearch(e.target.value) }}
                className="w-full pl-7 pr-7 py-1.5 text-xs border border-navy/15 rounded bg-pearl text-dark/70 focus:outline-none focus:border-violet transition-colors font-body placeholder:text-dark/25"
              />
              {search && (
                <button onClick={function() { setSearch('') }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-dark/25 hover:text-dark/50">
                  <X size={11} />
                </button>
              )}
            </div>

            {/* Filters toggle */}
            <button
              onClick={function() { setShowFilters(!showFilters) }}
              className={
                'flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-display border transition-colors ' +
                (showFilters || categoryFilter
                  ? 'bg-violet text-pearl border-violet'
                  : 'border-navy/15 text-dark/40 hover:text-dark/70 hover:bg-navy/5'
                )
              }
            >
              <SlidersHorizontal size={12} />
              FILTROS
              {categoryFilter && (
                <span className={'w-4 h-4 rounded-full text-xs flex items-center justify-center font-display ' +
                  (showFilters ? 'bg-pearl text-violet' : 'bg-white/20 text-pearl')}>
                  1
                </span>
              )}
            </button>

            {activeFilters > 0 && (
              <button
                onClick={function() { setSearch(''); setCategoryFilter('') }}
                className="flex items-center gap-1 text-xs text-dark/30 hover:text-dark/60 transition-colors font-display"
              >
                <X size={11} />
                LIMPIAR
              </button>
            )}

            {/* Count */}
            <div className="ml-auto flex items-center gap-2">
              {filtered.length !== partners.length && (
                <span className="text-xs text-dark/30 font-display">{filtered.length} de {partners.length}</span>
              )}
              <span className="px-2.5 py-0.5 rounded-full text-xs font-display bg-violet/10 text-violet border border-violet/20">
                {filtered.length}
              </span>
            </div>
          </div>

          {/* Category filter */}
          {showFilters && (
            <div className="p-4 bg-navy/[0.02] border border-navy/10 rounded-xl">
              <label className="block text-xs font-display text-dark/35 tracking-widest mb-2">CATEGORÍA</label>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={function() { setCategoryFilter('') }}
                  className={
                    'px-3 py-1.5 rounded-full text-xs font-display border transition-colors ' +
                    (!categoryFilter
                      ? 'bg-violet text-pearl border-violet'
                      : 'border-navy/15 text-dark/40 hover:bg-navy/5'
                    )
                  }
                >
                  Todas
                </button>
                {categories.map(function(cat) {
                  return (
                    <button
                      key={cat}
                      onClick={function() { setCategoryFilter(cat === categoryFilter ? '' : cat) }}
                      className={
                        'px-3 py-1.5 rounded-full text-xs font-display border transition-colors ' +
                        (categoryFilter === cat
                          ? 'bg-violet text-pearl border-violet'
                          : 'border-navy/15 text-dark/40 hover:bg-navy/5 hover:text-dark/60'
                        )
                      }
                    >
                      {cat}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="text-center py-16">
          <p className="text-dark/25 font-display text-xs tracking-widest">CARGANDO...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-navy/15 rounded-xl">
          <p className="text-dark/20 font-display text-xs tracking-widest">
            {activeFilters > 0 ? 'SIN RESULTADOS PARA ESTOS FILTROS' : 'SIN SOCIOS REGISTRADOS'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(function(p) {
            return (
              <PartnerCard
                key={p._id}
                partner={p}
                onEdit={setEditingPartner}
                onDelete={handleDelete}
              />
            )
          })}
        </div>
      )}

      {/* Edit modal */}
      {editingPartner && (
        <EditModal
          partner={editingPartner}
          onClose={function() { setEditingPartner(null) }}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}