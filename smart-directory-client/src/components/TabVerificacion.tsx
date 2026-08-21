'use client'
import { useState, useEffect, useMemo } from 'react'
import { RefreshCw, Search, X, Send, Phone, CheckCircle, XCircle, AlertTriangle, ChevronDown, ChevronRight, Loader, Eye } from 'lucide-react'

//const API_BASE = process.env.NEXT_PUBLIC_API_URL
const API_BASE = 'https://agexport-smart-directory.onrender.com'

// ─────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────
type Partner = {
  _id: string
  partner_name: string
  partner_category: string
  partner_whatsapp: string[]
  whatsapp_e164: string[]
  verified_phones: string[]
  verified_at: string | null
}

type SendResult = {
  partner: string
  phone: string
  success: boolean
  status_code?: number
  error?: string
}

type BlastResult = {
  sent: number
  failed: number
  total: number
  results: SendResult[]
}

// ─────────────────────────────────────────────────────────────────
// TemplatePreview — replica visual de la plantilla aprobada
// ─────────────────────────────────────────────────────────────────
function TemplatePreview() {
  return (
    <div className="bg-[#ECE5DD] rounded-2xl p-4 max-w-sm mx-auto shadow-inner">
      {/* WhatsApp top bar */}
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-black/10">
        <div className="w-7 h-7 rounded-full bg-forest/60 flex items-center justify-center">
          <Phone size={12} className="text-white" />
        </div>
        <div>
          <p className="text-xs font-semibold text-dark/80">Agexport Smart Directory</p>
          <p className="text-[10px] text-dark/40">Business Account</p>
        </div>
      </div>

      {/* Bubble */}
      <div className="bg-white rounded-xl rounded-tl-sm shadow-sm max-w-[92%] overflow-hidden">
        {/* Header */}
        <div className="bg-navy/5 border-b border-navy/8 px-4 py-2.5">
          <p className="text-xs font-bold text-dark/80">Verificación de WhatsApp</p>
        </div>

        {/* Body */}
        <div className="px-4 py-3 space-y-2">
          <p className="text-xs text-dark/70 leading-relaxed">
            Estimado socio <span className="font-semibold text-violet/70">{'{{partner_name}}'}</span>, le informamos
            que estamos realizando una prueba de verificación del Smart Directory de AGEXPORT para
            confirmar que el número de WhatsApp registrado en nuestra plataforma se encuentra activo
            y funcionando correctamente.
          </p>
          <p className="text-xs text-dark/70 leading-relaxed">
            Para confirmar la recepción de este mensaje, por favor presione el botón a continuación.
          </p>
        </div>

        {/* Quick reply button */}
        <div className="border-t border-navy/10 px-4 py-2.5 flex items-center justify-center gap-1.5 text-sky-500">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="9 17 4 12 9 7"/><line x1="20" y1="12" x2="4" y2="12"/>
          </svg>
          <span className="text-xs font-medium">Verificar</span>
        </div>
      </div>

      <p className="text-[10px] text-dark/30 text-center mt-3 font-display tracking-wide">
        PLANTILLA: {'{'}partners_whatsapp_verification{'}'}
      </p>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// PreviewModal — solo muestra la plantilla
// ─────────────────────────────────────────────────────────────────
function PreviewModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-navy/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-pearl border border-navy/10 rounded-2xl w-full max-w-md shadow-2xl">
        <div className="flex justify-between items-center px-6 pt-6 pb-4 border-b border-navy/8">
          <div>
            <h3 className="font-display text-navy text-sm tracking-widest">PREVIEW DE PLANTILLA</h3>
            <p className="text-xs text-dark/35 mt-0.5">Vista previa del mensaje que recibirán los socios</p>
          </div>
          <button onClick={onClose} className="text-dark/25 hover:text-dark/60 transition-colors p-1">
            <X size={16} />
          </button>
        </div>

        <div className="px-6 py-6">
          <TemplatePreview />
        </div>

        <div className="px-6 py-4 border-t border-navy/8">
          <button
            onClick={onClose}
            className="w-full border border-navy/20 text-dark/50 py-2.5 rounded-lg text-sm font-display hover:bg-navy/5 transition-colors"
          >
            CERRAR
          </button>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// ConfirmModal — advertencia + conteos, sin preview
// ─────────────────────────────────────────────────────────────────
function ConfirmModal({ partnerCount, phoneCount, onConfirm, onCancel, sending }: {
  partnerCount: number
  phoneCount: number
  onConfirm: () => void
  onCancel: () => void
  sending: boolean
}) {
  return (
    <div className="fixed inset-0 bg-navy/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-pearl border border-navy/10 rounded-2xl w-full max-w-md shadow-2xl">

        {/* Warning header */}
        <div className="flex items-center gap-3 px-6 pt-6 pb-4">
          <div className="w-10 h-10 rounded-full bg-amber-100 border border-amber-200 flex items-center justify-center shrink-0">
            <AlertTriangle size={18} className="text-amber-500" />
          </div>
          <div>
            <h3 className="font-display text-dark text-sm tracking-wide">CONFIRMAR ENVÍO MASIVO</h3>
            <p className="text-xs text-dark/40 mt-0.5">Esta acción enviará mensajes reales de WhatsApp</p>
          </div>
        </div>

        <div className="px-6 pb-6 space-y-3">
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-3">
            <p className="text-xs text-amber-700 font-display tracking-wide">⚠️ ADVERTENCIA</p>
            <p className="text-sm text-amber-800 leading-relaxed">
              Se enviará la plantilla <strong>partners_whatsapp_verification</strong> a los
              números de WhatsApp de los socios seleccionados.
            </p>
            <div className="flex gap-6 pt-1">
              <div className="text-center">
                <p className="text-2xl font-display text-amber-700 font-bold">{partnerCount}</p>
                <p className="text-xs text-amber-600">socios</p>
              </div>
              <div className="w-px bg-amber-200" />
              <div className="text-center">
                <p className="text-2xl font-display text-amber-700 font-bold">{phoneCount}</p>
                <p className="text-xs text-amber-600">mensajes a enviar</p>
              </div>
            </div>
          </div>

          <p className="text-xs text-dark/40 leading-relaxed">
            ¿Estás seguro de que deseas continuar? Los mensajes se enviarán inmediatamente y no se puede deshacer.
          </p>
        </div>

        <div className="flex gap-3 px-6 py-4 border-t border-navy/8">
          <button
            onClick={onCancel}
            disabled={sending}
            className="flex-1 border border-navy/20 text-dark/50 py-2.5 rounded-lg text-sm font-display hover:bg-navy/5 transition-colors disabled:opacity-40"
          >
            CANCELAR
          </button>
          <button
            onClick={onConfirm}
            disabled={sending}
            className="flex-1 bg-amber-500 hover:bg-amber-600 disabled:opacity-60 text-white py-2.5 rounded-lg text-sm font-display transition-colors flex items-center justify-center gap-2"
          >
            {sending ? (
              <>
                <Loader size={14} className="animate-spin" />
                ENVIANDO...
              </>
            ) : (
              <>
                <Send size={14} />
                SÍ, ENVIAR TODO
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// ResultsPanel
// ─────────────────────────────────────────────────────────────────
function ResultsPanel({ result, expected, onClose }: {
  result: BlastResult
  expected: number
  onClose: () => void
}) {
  const [showDetails, setShowDetails] = useState(false)
  const failed    = result.results.filter(function(r) { return !r.success })
  const succeeded = result.results.filter(function(r) { return r.success })
  const overSent  = result.total > expected

  return (
    <div className="border border-navy/10 rounded-2xl overflow-hidden shadow-sm bg-pearl">
      {overSent && (
        <div className="flex items-start gap-2 px-5 py-3 bg-amber-50 border-b border-amber-200">
          <AlertTriangle size={13} className="text-amber-500 shrink-0 mt-0.5" />
          <p className="text-xs text-amber-800 leading-relaxed">
            Se enviaron <strong>{result.total}</strong> mensajes pero solo había{' '}
            <strong>{expected}</strong> seleccionados. El servidor está ignorando la selección —
            probablemente corre una versión desactualizada del backend.
          </p>
        </div>
      )}
      <div className="px-5 py-4 flex items-center gap-4 bg-navy/[0.01]">
        <div className="flex items-center gap-2">
          <CheckCircle size={16} className="text-forest" />
          <span className="font-display text-sm text-forest">{result.sent} enviados</span>
        </div>
        {result.failed > 0 && (
          <>
            <div className="w-px h-4 bg-navy/15" />
            <div className="flex items-center gap-2">
              <XCircle size={16} className="text-red-400" />
              <span className="font-display text-sm text-red-500">{result.failed} fallidos</span>
            </div>
          </>
        )}
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-dark/30 font-display">{result.total} total</span>
          <button onClick={onClose} className="text-dark/25 hover:text-dark/50 transition-colors">
            <X size={14} />
          </button>
        </div>
      </div>

      <div className="h-1.5 bg-navy/8">
        <div
          className="h-full bg-forest transition-all"
          style={{ width: result.total > 0 ? (result.sent / result.total * 100) + '%' : '0%' }}
        />
      </div>

      <button
        onClick={function() { setShowDetails(!showDetails) }}
        className="w-full flex items-center justify-between px-5 py-3 text-xs font-display text-dark/35 hover:text-dark/60 hover:bg-navy/5 transition-colors"
      >
        VER DETALLE POR NÚMERO
        {showDetails ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>

      {showDetails && (
        <div className="border-t border-navy/8 divide-y divide-navy/5 max-h-64 overflow-y-auto">
          {failed.map(function(r, i) {
            return (
              <div key={'f' + i} className="flex items-center gap-3 px-5 py-2.5 bg-red-50/50">
                <XCircle size={12} className="text-red-400 shrink-0" />
                <span className="font-mono text-xs text-dark/60 w-32 shrink-0">{r.phone}</span>
                <span className="text-xs text-dark/50 w-40 shrink-0 truncate">{r.partner}</span>
                <span className="text-xs text-red-500/80 flex-1 truncate text-right" title={r.error}>
                  {r.error || (r.status_code ? 'HTTP ' + r.status_code : 'Error desconocido')}
                </span>
                {r.status_code && (
                  <span className="text-[10px] text-red-400/60 font-display shrink-0">
                    {r.status_code}
                  </span>
                )}
              </div>
            )
          })}
          {succeeded.map(function(r, i) {
            return (
              <div key={'s' + i} className="flex items-center gap-3 px-5 py-2.5">
                <CheckCircle size={12} className="text-forest shrink-0" />
                <span className="font-mono text-xs text-dark/60 w-32 shrink-0">{r.phone}</span>
                <span className="text-xs text-dark/50 flex-1 truncate">{r.partner}</span>
                <span className="text-xs text-forest font-display shrink-0">OK</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// PartnerRow
// ─────────────────────────────────────────────────────────────────
function PartnerRow({ partner, resultMap, selected, onToggle }: {
  partner: Partner
  resultMap: Map<string, SendResult>
  selected: boolean
  onToggle: (id: string) => void
}) {
  const hasNumbers        = partner.whatsapp_e164.length > 0
  const verifiedPhones    = partner.verified_phones ?? []
  const isFullyVerified   = hasNumbers && partner.whatsapp_e164.every(function(p) {
    return verifiedPhones.includes(p)
  })
  const isPartialVerified = !isFullyVerified && verifiedPhones.length > 0

  const verifiedDate = partner.verified_at
    ? new Date(partner.verified_at).toLocaleString('es-GT', {
        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
      })
    : null

  return (
    <div className={
      'flex items-center gap-4 px-5 py-3.5 border rounded-xl bg-pearl shadow-sm transition-colors ' +
      (!hasNumbers        ? 'opacity-50 border-navy/10'          :
       isFullyVerified    ? 'border-forest/30 bg-forest/[0.02]'  :
       isPartialVerified  ? 'border-amber-300/40 bg-amber-50/30' :
                            'border-navy/10') +
      (hasNumbers && !selected ? ' opacity-60' : '')
    }>
      {/* Checkbox */}
      <input
        type="checkbox"
        checked={selected}
        disabled={!hasNumbers}
        onChange={function() { onToggle(partner._id) }}
        title={hasNumbers ? 'Incluir en el envío' : 'Sin número de WhatsApp'}
        className="w-4 h-4 shrink-0 accent-violet cursor-pointer disabled:cursor-not-allowed"
      />

      {/* Avatar */}
      <div className="w-9 h-9 rounded-xl bg-violet/10 border border-violet/20 flex items-center justify-center shrink-0 font-display text-violet font-bold text-sm">
        {(partner.partner_name || '?')[0].toUpperCase()}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="font-display text-sm text-dark tracking-wide truncate">{partner.partner_name}</p>
          {isFullyVerified && (
            <span className="flex items-center gap-1 text-[10px] font-display text-forest bg-forest/10 px-1.5 py-0.5 rounded-full shrink-0">
              <CheckCircle size={9} />
              VERIFICADO
            </span>
          )}
          {isPartialVerified && (
            <span className="flex items-center gap-1 text-[10px] font-display text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded-full shrink-0">
              <AlertTriangle size={9} />
              PARCIAL
            </span>
          )}
        </div>
        <p className="text-xs text-dark/35 mt-0.5 truncate">{partner.partner_category}</p>
        {verifiedDate && (
          <p className="text-[10px] text-forest/60 mt-0.5">
            Confirmado {verifiedDate}
          </p>
        )}
      </div>

      {/* Números */}
      <div className="flex flex-col gap-1 items-end shrink-0">
        {hasNumbers ? partner.whatsapp_e164.map(function(phone, i) {
          const sendResult  = resultMap.get(phone)
          const wasVerified = verifiedPhones.includes(phone)
          return (
            <div key={i} className="flex items-center gap-2">
              {/* Ícono de envío (solo si se hizo blast en esta sesión) */}
              {sendResult && (
                <span title={sendResult.success ? 'Enviado correctamente' : (sendResult.error || 'Error al enviar')}>
                  {sendResult.success
                    ? <CheckCircle size={12} className="text-forest" />
                    : <XCircle     size={12} className="text-red-400" />
                  }
                </span>
              )}
              {/* Ícono de confirmación del botón */}
              {wasVerified
                ? <span title="Presionó Verificar"><CheckCircle size={12} className="text-forest" /></span>
                : <div className="w-3 h-3 rounded-full border border-navy/20" title="Sin confirmar" />
              }
              <div className="text-right">
                <span className="font-mono text-xs text-violet/70">{partner.partner_whatsapp[i]}</span>
                <span className="text-xs text-dark/25 ml-1">→ {phone}</span>
              </div>
            </div>
          )
        }) : (
          <span className="text-xs text-dark/25 italic font-display">SIN WHATSAPP</span>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────
export default function TabVerificacion() {
  const [partners,     setPartners]     = useState<Partner[]>([])
  const [loading,      setLoading]      = useState(true)
  const [search,       setSearch]       = useState('')
  const [showConfirm,  setShowConfirm]  = useState(false)
  const [showPreview,  setShowPreview]  = useState(false)
  const [sending,      setSending]      = useState(false)
  const [blastResult,  setBlastResult]  = useState<BlastResult | null>(null)
  const [selected,     setSelected]     = useState<Set<string>>(new Set())
  const [expectedSent, setExpectedSent] = useState(0)

  const load = async () => {
    setLoading(true)
    try {
      const res  = await fetch(API_BASE + '/verification/partners')
      const json = await res.json()
      const list: Partner[] = json.partners ?? []
      setPartners(list)
      // por defecto se seleccionan todos los que tienen WhatsApp
      setSelected(new Set(
        list.filter(function(p) { return p.whatsapp_e164.length > 0 })
            .map(function(p) { return p._id })
      ))
    } catch {
      setPartners([])
      setSelected(new Set())
    }
    setLoading(false)
  }

  useEffect(function() { load() }, [])

  const filtered = useMemo(function() {
    if (!search.trim()) return partners
    const s = search.toLowerCase()
    return partners.filter(function(p) {
      return p.partner_name.toLowerCase().includes(s) ||
        p.partner_category.toLowerCase().includes(s) ||
        p.partner_whatsapp.some(function(n) { return n.includes(s) })
    })
  }, [partners, search])

  const totalPhones = useMemo(function() {
    return partners.reduce(function(acc, p) { return acc + p.whatsapp_e164.length }, 0)
  }, [partners])

  const partnersWithPhone = useMemo(function() {
    return partners.filter(function(p) { return p.whatsapp_e164.length > 0 }).length
  }, [partners])

  const verifiedCount = useMemo(function() {
    return partners.filter(function(p) { return (p.verified_phones ?? []).length > 0 }).length
  }, [partners])

  // ── Selección ──────────────────────────────────────────────────
  const selectedPartners = useMemo(function() {
    return partners.filter(function(p) {
      return p.whatsapp_e164.length > 0 && selected.has(p._id)
    })
  }, [partners, selected])

  const selectedPhones = useMemo(function() {
    return selectedPartners.reduce(function(acc, p) { return acc + p.whatsapp_e164.length }, 0)
  }, [selectedPartners])

  // socios seleccionables dentro del filtro actual
  const selectableFiltered = useMemo(function() {
    return filtered.filter(function(p) { return p.whatsapp_e164.length > 0 })
  }, [filtered])

  const allFilteredSelected = selectableFiltered.length > 0 &&
    selectableFiltered.every(function(p) { return selected.has(p._id) })

  const toggleOne = function(id: string) {
    setSelected(function(prev) {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAllFiltered = function() {
    setSelected(function(prev) {
      const next = new Set(prev)
      if (allFilteredSelected) {
        selectableFiltered.forEach(function(p) { next.delete(p._id) })
      } else {
        selectableFiltered.forEach(function(p) { next.add(p._id) })
      }
      return next
    })
  }

  const resultMap = useMemo(function() {
    const map = new Map<string, SendResult>()
    if (blastResult) {
      blastResult.results.forEach(function(r) { map.set(r.phone, r) })
    }
    return map
  }, [blastResult])

  const handleSend = async () => {
    setSending(true)
    setExpectedSent(selectedPhones)
    try {
      const res = await fetch(API_BASE + '/verification/send', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          partner_ids: selectedPartners.map(function(p) { return p._id })
        }),
      })
      const json = await res.json()
      setBlastResult(json)
    } catch {
      setBlastResult({ sent: 0, failed: selectedPhones, total: selectedPhones, results: [] })
    }
    setSending(false)
    setShowConfirm(false)
  }

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-2">
        <div>
          <h2 className="font-display text-navy text-lg">VERIFICACIÓN</h2>
          <p className="text-xs text-dark/35 mt-0.5">Envío masivo de plantilla de verificación de números</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="flex items-center gap-1.5 border border-navy/15 text-dark/40 hover:text-dark/70 px-3 py-1.5 rounded text-xs font-display transition-colors hover:bg-navy/5"
          >
            <RefreshCw size={12} />
            ACTUALIZAR
          </button>
          <button
            onClick={function() { setShowPreview(true) }}
            className="flex items-center gap-2 border border-violet/30 text-violet/70 hover:text-violet hover:bg-violet/5 px-4 py-1.5 rounded text-xs font-display transition-colors"
          >
            <Eye size={12} />
            VISUALIZAR PLANTILLA
          </button>
          <button
            onClick={function() { setShowConfirm(true) }}
            disabled={loading || sending || selectedPhones === 0}
            className="flex items-center gap-2 bg-violet hover:bg-violet/80 disabled:opacity-40 disabled:cursor-not-allowed text-pearl px-4 py-1.5 rounded text-xs font-display transition-colors"
          >
            <Send size={12} />
            ENVIAR VERIFICACIÓN{selectedPhones > 0 ? ' (' + selectedPhones + ')' : ''}
          </button>
        </div>
      </div>

      {/* Stats */}
      {!loading && (
        <div className="flex items-center gap-6 mb-6 px-1">
          <div className="flex items-center gap-1.5 text-xs text-dark/40">
            <span className="font-display text-dark/70 text-sm">{partners.length}</span>
            socios totales
          </div>
          <div className="w-px h-4 bg-navy/10" />
          <div className="flex items-center gap-1.5 text-xs text-dark/40">
            <span className="font-display text-dark/70 text-sm">{partnersWithPhone}</span>
            con WhatsApp
          </div>
          <div className="w-px h-4 bg-navy/10" />
          <div className="flex items-center gap-1.5 text-xs text-dark/40">
            <span className="font-display text-dark/70 text-sm">{totalPhones}</span>
            números totales
          </div>
          <div className="w-px h-4 bg-navy/10" />
          <div className="flex items-center gap-1.5 text-xs text-dark/40">
            <span className="font-display text-violet text-sm font-bold">{selectedPhones}</span>
            mensajes a enviar
          </div>
          <div className="w-px h-4 bg-navy/10" />
          <div className="flex items-center gap-1.5 text-xs text-dark/40">
            <span className="font-display text-forest text-sm font-bold">{verifiedCount}</span>
            confirmados
          </div>
        </div>
      )}

      {/* Blast results */}
      {blastResult && (
        <div className="mb-5">
          <ResultsPanel
            result={blastResult}
            expected={expectedSent}
            onClose={function() { setBlastResult(null) }}
          />
        </div>
      )}

      {/* Search + selección */}
      {!loading && (
        <div className="flex items-center gap-4 mb-4">
          <div className="relative max-w-sm flex-1">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-dark/30" />
            <input
              type="text"
              placeholder="Buscar socio o número..."
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

          <label className="flex items-center gap-2 text-xs font-display text-dark/40 hover:text-dark/70 transition-colors cursor-pointer select-none">
            <input
              type="checkbox"
              checked={allFilteredSelected}
              disabled={selectableFiltered.length === 0}
              onChange={toggleAllFiltered}
              className="w-4 h-4 accent-violet cursor-pointer disabled:cursor-not-allowed"
            />
            {allFilteredSelected ? 'DESELECCIONAR TODOS' : 'SELECCIONAR TODOS'}
            {search && selectableFiltered.length > 0 && (
              <span className="text-dark/25">({selectableFiltered.length} en la búsqueda)</span>
            )}
          </label>

          <span className="ml-auto text-xs text-dark/35">
            <span className="font-display text-violet font-bold">{selectedPartners.length}</span>
            {' '}de {partnersWithPhone} socios seleccionados
          </span>
        </div>
      )}

      {/* Partner list */}
      {loading ? (
        <div className="text-center py-16">
          <p className="text-dark/25 font-display text-xs tracking-widest">CARGANDO...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-navy/15 rounded-xl">
          <p className="text-dark/20 font-display text-xs tracking-widest">SIN RESULTADOS</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(function(p) {
            return (
              <PartnerRow
                key={p._id}
                partner={p}
                resultMap={resultMap}
                selected={selected.has(p._id)}
                onToggle={toggleOne}
              />
            )
          })}
        </div>
      )}

      {/* Preview modal */}
      {showPreview && (
        <PreviewModal onClose={function() { setShowPreview(false) }} />
      )}

      {/* Confirm modal */}
      {showConfirm && (
        <ConfirmModal
          partnerCount={selectedPartners.length}
          phoneCount={selectedPhones}
          onConfirm={handleSend}
          onCancel={function() { setShowConfirm(false) }}
          sending={sending}
        />
      )}
    </div>
  )
}