'use client'
import { useState } from 'react'
import TabSocios from '@/components/TabSocios'
import TabRecomendaciones from '@/components/TabRecomendaciones'
import TabConversaciones from '@/components/TabConversaciones'
import TabLogs from '@/components/TabLogs'
import { Users, GitBranch, MessageSquare, Terminal } from 'lucide-react'

const tabs = [
  { id: 'socios', label: 'Socios', icon: Users },
  { id: 'recomendaciones', label: 'Recomendaciones', icon: GitBranch },
  { id: 'conversaciones', label: 'Conversaciones', icon: MessageSquare },
  { id: 'logs', label: 'Logs', icon: Terminal },
]

export default function Home() {
  const [active, setActive] = useState('socios')

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
        <div className="ml-auto flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-forest animate-pulse" />
          <span className="text-xs text-dark/40 font-display">LIVE</span>
        </div>
      </header>

      {/* Tabs */}
      <nav className="px-8 pt-6 flex gap-1 border-b border-navy/10 bg-pearl">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActive(id)}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-display tracking-wide transition-all rounded-t-md
              ${active === id
                ? 'bg-violet text-pearl border-b-2 border-violet'
                : 'text-dark/40 hover:text-dark/70 hover:bg-navy/5'
              }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </nav>

      {/* Content */}
      <main className="p-8 bg-pearl min-h-[calc(100vh-120px)]">
        {active === 'socios' && <TabSocios />}
        {active === 'recomendaciones' && <TabRecomendaciones />}
        {active === 'conversaciones' && <TabConversaciones />}
        {active === 'logs' && <TabLogs />}
      </main>
    </div>
  )
}