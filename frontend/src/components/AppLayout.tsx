import { NavLink, Outlet, Link } from 'react-router-dom'
import {
  LayoutDashboard, TrendingUp, Network, Boxes, Search, SlidersHorizontal,
  History, Swords, FileCheck2, Settings, Bell, ChevronDown, Plug,
} from 'lucide-react'
import { cn } from '../lib/utils'

const NAV = [
  {
    section: 'Overview',
    items: [
      { to: '/app', end: true, icon: LayoutDashboard, label: 'Command Deck' },
      { to: '/app/risk', icon: TrendingUp, label: 'Risk & Prediction' },
    ],
  },
  {
    section: 'Ontology',
    items: [
      { to: '/app/ontology', icon: Network, label: 'Ontology Explorer' },
      { to: '/app/inventory', icon: Boxes, label: 'Attack Surface' },
    ],
  },
  {
    section: 'Operations',
    items: [
      { to: '/app/investigation', icon: Search, label: 'Investigations' },
      { to: '/app/autonomy', icon: SlidersHorizontal, label: 'Autonomy Console' },
      { to: '/app/provenance', icon: History, label: 'Provenance' },
      { to: '/app/purple-team', icon: Swords, label: 'Purple Team' },
    ],
  },
  {
    section: 'Business',
    items: [
      { to: '/app/reports', icon: FileCheck2, label: 'Compliance Center' },
      { to: '/app/onboarding', icon: Plug, label: 'Integrations' },
      { to: '/app/settings', icon: Settings, label: 'Settings' },
    ],
  },
]

function Logo() {
  return (
    <Link to="/app" className="flex items-center gap-2.5 px-1">
      <svg viewBox="0 0 32 32" className="h-7 w-7 shrink-0" aria-hidden>
        <path d="M16 2 L28 7 V15 C28 22.5 23 28 16 30 C9 28 4 22.5 4 15 V7 Z" fill="none" stroke="var(--color-accent)" strokeWidth="2" />
        <path d="M10.5 11 L16 21.5 L21.5 11" fill="none" stroke="var(--color-accent)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="font-mono text-base font-bold tracking-tight">
        Viltrum<span className="text-accent">X</span>
      </span>
    </Link>
  )
}

export default function AppLayout() {
  return (
    <div className="flex min-h-dvh bg-bg">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-border bg-surface px-3 py-4 lg:flex">
        <Logo />
        <nav className="mt-6 flex-1 space-y-5 overflow-y-auto">
          {NAV.map((group) => (
            <div key={group.section}>
              <div className="px-2 pb-1.5 font-mono text-[10px] font-semibold tracking-[0.18em] text-ink-3 uppercase">
                {group.section}
              </div>
              <ul className="space-y-0.5">
                {group.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={'end' in item && item.end}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors duration-150',
                          isActive
                            ? 'bg-accent-dim font-medium text-accent-bright'
                            : 'text-ink-2 hover:bg-surface-2 hover:text-ink',
                        )
                      }
                    >
                      <item.icon size={16} aria-hidden />
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="rounded-md border border-border-subtle bg-bg px-3 py-2.5">
          <div className="flex items-center gap-2 font-mono text-[11px] text-ink-2">
            <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-status-good" aria-hidden />
            8/8 agents nominal
          </div>
          <div className="mt-1 font-mono text-[10px] text-ink-3">last sweep 03:00 IST · passed</div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-60">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-4 border-b border-border bg-bg/90 px-5 backdrop-blur">
          <button className="flex cursor-pointer items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-ink-2 hover:text-ink">
            <span className="grid h-5 w-5 place-items-center rounded bg-accent-dim font-mono text-[10px] font-bold text-accent-bright">P</span>
            PayKraft Technologies
            <ChevronDown size={14} aria-hidden />
          </button>
          <div className="flex items-center gap-3">
            <span className="hidden font-mono text-[11px] text-ink-3 md:block">env: <span className="text-ink-2">demo-tenant</span> · ap-south-1</span>
            <button aria-label="Notifications" className="relative cursor-pointer rounded-md p-2 text-ink-2 hover:bg-surface-2 hover:text-ink">
              <Bell size={16} aria-hidden />
              <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-status-critical" aria-hidden />
            </button>
            <div className="grid h-8 w-8 place-items-center rounded-full border border-border bg-surface-2 font-mono text-xs font-semibold text-ink-2" aria-label="Arjun Mehta">
              AM
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-5 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
