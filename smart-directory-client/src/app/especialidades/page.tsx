'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Script from 'next/script'
import TabEspecialidades from '@/components/TabEspecialidades'
import TabICHI from '@/components/TabICHI'
import { Stethoscope, Activity, LogOut } from 'lucide-react'

export default function EspecialidadesPage() {
  const router = useRouter()
  const [partnerName, setPartnerName] = useState('')
  const [activeTab, setActiveTab] = useState<'cie11' | 'ichi'>('cie11')

  useEffect(() => {
    fetch('/api/auth/me')
      .then(r => r.json())
      .then(data => setPartnerName(data.partner_name || 'PARTNER'))
  }, [])

  const handleLogout = async () => {
    await fetch('/api/auth', { method: 'DELETE' })
    router.push('/login')
    router.refresh()
  }

  return (
    <div className="min-h-screen bg-pearl text-dark">
      <header className="border-b border-navy/10 px-8 py-4 flex items-center gap-4 bg-pearl shadow-sm">
        <div className="w-8 h-8 bg-violet rounded-sm flex items-center justify-center">
          <span className="font-display text-xs text-pearl font-bold">ASD</span>
        </div>
        <h1 className="font-display text-sm text-navy tracking-widest uppercase">
          AGEXPORT Smart Directory
        </h1>
        <div className="ml-auto flex items-center gap-4">
          {partnerName && (
            <span className="text-xs text-pearl font-display font-bold bg-violet px-3 py-1.5 rounded-lg tracking-wide">
              {partnerName}
            </span>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-xs text-dark/30 hover:text-dark/60 font-display transition-colors border border-navy/10 hover:border-navy/25 px-3 py-1.5 rounded"
          >
            <LogOut size={11} />
            SALIR
          </button>
        </div>
      </header>

      <nav className="px-8 pt-6 flex gap-1 border-b border-navy/10 bg-pearl">
        <button
          onClick={() => setActiveTab('cie11')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-display tracking-wide rounded-t-md border-b-2 transition-colors ${
            activeTab === 'cie11'
              ? 'bg-violet text-pearl border-b-violet'
              : 'bg-transparent text-dark/40 border-b-transparent hover:text-dark/60'
          }`}
        >
          <Stethoscope size={14} />
          Especialidades CIE-11
        </button>
        <button
          onClick={() => setActiveTab('ichi')}
          className={`flex items-center gap-2 px-5 py-3 text-sm font-display tracking-wide rounded-t-md border-b-2 transition-colors ${
            activeTab === 'ichi'
              ? 'bg-violet text-pearl border-b-violet'
              : 'bg-transparent text-dark/40 border-b-transparent hover:text-dark/60'
          }`}
        >
          <Activity size={14} />
          Intervenciones ICHI
        </button>
      </nav>

      <main className="p-8 bg-pearl min-h-[calc(100vh-120px)]">
        {activeTab === 'cie11' && <TabEspecialidades />}
        {activeTab === 'ichi' && <TabICHI />}
      </main>
    </div>
  )
}