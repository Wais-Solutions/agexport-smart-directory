'use client'
import { useEffect, useRef, useState } from 'react'
import { Save, X, Stethoscope, Loader2 } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Specialty {
  code: string
  title: string
  uri: string
}

interface PartnerInfo {
  partner_id: string
  partner_name: string
  username: string
}

export default function TabEspecialidades() {
  const [partner, setPartner]         = useState<PartnerInfo | null>(null)
  const [specialties, setSpecialties] = useState<Specialty[]>([])
  const [saving, setSaving]           = useState(false)
  const [saved, setSaved]             = useState(false)
  const [loadingData, setLoadingData] = useState(true)
  const icdInitialized                = useRef(false)

  // ── 1. Cargar info del partner y especialidades guardadas ──────────────
  useEffect(() => {
    async function loadData() {
      try {
        const meRes = await fetch('/api/auth/me')
        const me = await meRes.json()
        console.log('ME response:', me)
        setPartner({
          partner_id:   me.partner_id,
          partner_name: me.partner_name,
          username:     me.username,
        })

        const specRes = await fetch(`${API_URL}/specialties/${me.partner_id}`)
        const specData = await specRes.json()
        console.log('Specialties response:', specData)
        setSpecialties(specData.specialties || [])
      } catch (err) {
        console.error('Error cargando datos:', err)
      } finally {
        setLoadingData(false)
      }
    }
    loadData()
  }, [])

  // ── 2. Inicializar widget ECT cuando el partner esté listo ─────────────
  useEffect(() => {
    if (!partner || icdInitialized.current) return

    async function initECT() {
      try {
        // Esperar a que el input esté en el DOM
        const waitForInput = () => new Promise<void>((resolve) => {
          const check = () => {
            const input = document.querySelector('[data-ctw-ino="1"]')
            if (input) {
              resolve()
            } else {
              setTimeout(check, 100)
            }
          }
          check()
        })

        await waitForInput()
        console.log('Input found in DOM')

        const tokenRes = await fetch(`${API_URL}/auth/icd-token`)
        const tokenData = await tokenRes.json()
        console.log('Token response ok:', !!tokenData.access_token)
        const { access_token } = tokenData

        console.log('Loading ECT module...')
        const ECT = await import('@whoicd/icd11ect')
        console.log('ECT module loaded:', Object.keys(ECT))

        // Cargar CSS via link tag en lugar de import dinámico
        if (!document.querySelector('link[data-ect-styles]')) {
          const link = document.createElement('link')
          link.rel = 'stylesheet'
          link.href = 'https://icdcdn.who.int/embeddedct/icd11ect-1.7.1.css'
          link.setAttribute('data-ect-styles', 'true')
          document.head.appendChild(link)
          console.log('ECT styles loaded via CDN')
        }

        const settings = {
          apiServerUrl:  'https://id.who.int',
          apiSecuredUrl: 'https://id.who.int',
          language:      'es',
          sourceApp:     'asd_partner_panel',
          autoBind:      false,
        }

        const callbacks = {
          selectedEntityFunction: (entity: { code: string; selectedText: string; uri: string }) => {
            console.log('ENTITY SELECTED:', entity)
            const newSpec: Specialty = {
              code:  entity.code,
              title: entity.selectedText,
              uri:   entity.uri,
            }
            setSpecialties(prev => {
              if (prev.some(s => s.code === newSpec.code)) return prev
              return [...prev, newSpec]
            })
          },
        }

        ECT.Handler.configure(settings, callbacks)
        console.log('ECT configured')
        ECT.Handler.bind('1', access_token)
        console.log('ECT bound')
        icdInitialized.current = true
      } catch (err) {
        console.error('Error inicializando ECT:', err)
      }
    }

    initECT()
  }, [partner])

  // ── 3. Guardar especialidades ──────────────────────────────────────────
  const handleSave = async () => {
    if (!partner) return
    setSaving(true)
    try {
      await fetch(`${API_URL}/specialties/${partner.partner_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          partner_id:   partner.partner_id,
          partner_name: partner.partner_name,
          username:     partner.username,
          specialties,
        }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      console.error('Error guardando:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleRemove = (code: string) => {
    setSpecialties(prev => prev.filter(s => s.code !== code))
  }

  // ── Render ─────────────────────────────────────────────────────────────
  if (loadingData) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 size={20} className="animate-spin text-violet" />
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">

      {/* Header de sección */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-sm tracking-widest uppercase text-navy">
            Especialidades
          </h2>
          <p className="text-xs text-dark/40 mt-1">
            Busca y selecciona las especialidades médicas que ofrece tu institución.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-violet hover:bg-violet/80 disabled:opacity-60 text-pearl px-4 py-2 rounded-lg text-xs font-display tracking-wide transition-colors"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
          {saved ? 'GUARDADO ✓' : 'GUARDAR CAMBIOS'}
        </button>
      </div>

      {/* Widget de búsqueda ECT */}
      <div className="bg-white border border-navy/10 rounded-xl p-4 space-y-3">
        <p className="text-xs font-display tracking-widests text-dark/40 uppercase">
          Buscar en CIE-11
        </p>
        <input
          type="text"
          data-ctw-ino="1"
          placeholder="Escribe una enfermedad o especialidad..."
          className="w-full bg-navy/5 border border-navy/10 rounded-lg px-3 py-2.5 text-dark text-sm focus:outline-none focus:border-violet transition-colors placeholder:text-dark/20"
        />
      </div>

      {/* Lista de especialidades seleccionadas */}
      <div className="bg-white border border-navy/10 rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-display tracking-widest text-dark/40 uppercase">
            Especialidades seleccionadas
          </p>
          <span className="text-xs text-dark/30 bg-navy/5 px-2 py-0.5 rounded-full">
            {specialties.length}
          </span>
        </div>

        {specialties.length === 0 ? (
          <div className="flex flex-col items-center py-8 gap-2">
            <Stethoscope size={20} className="text-dark/20" />
            <p className="text-xs text-dark/30">
              Aún no hay especialidades seleccionadas.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {specialties.map(s => (
              <div
                key={s.code}
                className="flex items-center justify-between bg-navy/3 border border-navy/8 rounded-lg px-3 py-2.5 group"
              >
                <div className="flex items-center gap-3">
                  <span className="text-xs font-display text-violet bg-violet/10 px-2 py-0.5 rounded font-bold">
                    {s.code}
                  </span>
                  <span className="text-sm text-dark">{s.title}</span>
                </div>
                <button
                  onClick={() => handleRemove(s.code)}
                  className="text-dark/20 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}