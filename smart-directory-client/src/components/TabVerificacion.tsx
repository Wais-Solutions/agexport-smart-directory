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
// TemplatePreview — replica visual de la plantilla real
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
          <p className="text-xs font-bold text-dark/80">Verificación de Número</p>
        </div>

        {/* Body */}
        <div className="px-4 py-3 space-y-2">
          <p className="text-xs text-dark/70 leading-relaxed">Estimado socio,</p>
          <p className="text-xs text-dark/70 leading-relaxed">
            Le informamos que estamos realizando una prueba de verificación del Smart Directory de AGEXPORT para confirmar que el número de WhatsApp registrado en nuestra plataforma se encuentra activo y funcionando correctamente.
          </p>
          <p className="text-xs text-dark/70 leading-relaxed">
            Si recibió este mensaje, su número ha sido verificado exitosamente. No es necesario realizar ninguna acción adicional.
          </p>
        </div>

        {/* Footer */}
        <div className="border-t border-navy/8 px-4 py-2 flex items-center justify-between">
          <p className="text-[10px] text-dark/30 leading-relaxed flex-1">
            AGEXPORT Smart Directory | Este es un mensaje automático.
          </p>
          <p className="text-[10px] text-dark/25 ml-3 shrink-0">
            {new Date().toLocaleTimeString('es-GT', { hour: '2-digit', minute: '2-digit' })}
          </p>
        </div>
      </div>

      <p className="text-[10px] text-dark/30 text-center mt-3 font-display tracking-wide">
        PLANTILLA: partners_number_verification
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
// ConfirmModal — solo advertencia + conteos, sin preview
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
              Se enviará la plantilla <strong>partners_number_verification</strong> a todos los
              números de WhatsApp registrados en el directorio.
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
function ResultsPanel({ result, onClose }: { result: BlastResult; onClose: () => void }) {
  const [showDetails, setShowDetails] = useState(false)
  const failed = result.results.filter(function(r) { return !r.success })
  const succeeded = result.results.filter(function(r) { return r.success })

  return (
    <div className="border border-navy/10 rounded-2xl overflow-hidden shadow-sm bg-pearl">
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
                <span className="text-xs text-dark/50 flex-1 truncate">{r.partner}</span>
                <span className="text-xs text-red-400 font-display shrink-0">
                  {r.status_code ? 'HTTP ' + r.status_code : r.error?.slice(0, 30)}
                </span>
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
function PartnerRow({ partner, resultMap }: {
  partner: Partner
  resultMap: Map<string, SendResult>
}) {
  const hasNumbers = partner.whatsapp_e164.length > 0

  return (
    <div className={'flex items-center gap-4 px-5 py-3.5 border border-navy/10 rounded-xl bg-pearl shadow-sm ' +
      (!hasNumbers ? 'opacity-50' : '')}>
      <div className="w-9 h-9 rounded-xl bg-violet/10 border border-violet/20 flex items-center justify-center shrink-0 font-display text-violet font-bold text-sm">
        {(partner.partner_name || '?')[0].toUpperCase()}
      </div>

      <div className="flex-1 min-w-0">
        <p className="font-display text-sm text-dark tracking-wide truncate">{partner.partner_name}</p>
        <p className="text-xs text-dark/35 mt-0.5 truncate">{partner.partner_category}</p>
      </div>

      <div className="flex flex-col gap-1 items-end shrink-0">
        {hasNumbers ? partner.whatsapp_e164.map(function(phone, i) {
          const result = resultMap.get(phone)
          return (
            <div key={i} className="flex items-center gap-2">
              {result && (
                result.success
                  ? <CheckCircle size={12} className="text-forest" />
                  : <XCircle size={12} className="text-red-400" />
              )}
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
  const [partners, setPartners] = useState<Partner[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showConfirm, setShowConfirm] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [sending, setSending] = useState(false)
  const [blastResult, setBlastResult] = useState<BlastResult | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await fetch(API_BASE + '/verification/partners')
      const json = await res.json()
      setPartners(json.partners ?? [])
    } catch { setPartners([]) }
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

  const resultMap = useMemo(function() {
    const map = new Map<string, SendResult>()
    if (blastResult) {
      blastResult.results.forEach(function(r) { map.set(r.phone, r) })
    }
    return map
  }, [blastResult])

  const handleSend = async () => {
    setSending(true)
    try {
      const res = await fetch(API_BASE + '/verification/send', { method: 'POST' })
      const json = await res.json()
      setBlastResult(json)
    } catch {
      setBlastResult({ sent: 0, failed: totalPhones, total: totalPhones, results: [] })
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
            disabled={loading || sending || totalPhones === 0}
            className="flex items-center gap-2 bg-violet hover:bg-violet/80 disabled:opacity-40 disabled:cursor-not-allowed text-pearl px-4 py-1.5 rounded text-xs font-display transition-colors"
          >
            <Send size={12} />
            ENVIAR VERIFICACIÓN
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
            <span className="font-display text-violet text-sm font-bold">{totalPhones}</span>
            mensajes a enviar
          </div>
        </div>
      )}

      {/* Blast results */}
      {blastResult && (
        <div className="mb-5">
          <ResultsPanel result={blastResult} onClose={function() { setBlastResult(null) }} />
        </div>
      )}

      {/* Search */}
      {!loading && (
        <div className="relative max-w-sm mb-4">
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
            return <PartnerRow key={p._id} partner={p} resultMap={resultMap} />
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
          partnerCount={partnersWithPhone}
          phoneCount={totalPhones}
          onConfirm={handleSend}
          onCancel={function() { setShowConfirm(false) }}
          sending={sending}
        />
      )}
    </div>
  )
}