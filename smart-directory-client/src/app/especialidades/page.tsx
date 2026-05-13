'use client'
import { useRouter } from 'next/navigation'
import { Stethoscope, LogOut } from 'lucide-react'

export default function EspecialidadesPage() {
  const router = useRouter()

  const handleLogout = async () => {
    await fetch('/api/auth', { method: 'DELETE' })
    router.push('/login')
    router.refresh()
  }

  return (
    <div className="min-h-screen bg-pearl text-dark">
      {/* Header */}
      <header className="border-b border-navy/10 px-8 py-4 flex items-center gap-4 bg-pearl shadow-sm">
        <div className="w-8 h-8 bg-violet rounded-sm flex items-center justify-center">
          <span className="font-display text-xs text-pearl font-bold">ASD</span>
        </div>
        <h1 className="font-display text-sm text-navy tracking-widest uppercase">
          AGEXPORT Smart Directory
        </h1>
        <div className="ml-auto flex items-center gap-4">
          <div className="w-16 h-7 bg-violet rounded-sm flex items-center justify-center">
            <span className="font-display text-xs text-pearl font-bold">
              PARTNER
            </span>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-xs text-dark/30 hover:text-dark/60 font-display transition-colors border border-navy/10 hover:border-navy/25 px-3 py-1.5 rounded"
          >
            <LogOut size={11} />
            SALIR
          </button>
        </div>
      </header>

      {/* Tab bar */}
      <nav className="px-8 pt-6 flex gap-1 border-b border-navy/10 bg-pearl">
        <button className="flex items-center gap-2 px-5 py-3 text-sm font-display tracking-wide rounded-t-md bg-violet text-pearl border-b-2 border-violet">
          <Stethoscope size={14} />
          Especialidades
        </button>
      </nav>

      {/* Placeholder */}
      <main className="p-8 bg-pearl min-h-[calc(100vh-120px)] flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-12 h-12 bg-violet/10 rounded-xl flex items-center justify-center mx-auto">
            <Stethoscope size={22} className="text-violet" />
          </div>
          <p className="font-display text-sm text-dark/40 tracking-widest uppercase">
            Especialidades
          </p>
          <p className="text-xs text-dark/25">
            Esta sección está en construcción.
          </p>
        </div>
      </main>
    </div>
  )
}