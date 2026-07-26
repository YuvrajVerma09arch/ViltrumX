import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, Link, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, TrendingUp, Network, Boxes, Search, SlidersHorizontal,
  History, Swords, FileCheck2, Settings, Bell, Plug, LogOut } from 'lucide-react'
import { endpoints, logout } from '../lib/api'
import { useApi } from '../lib/hooks'
import type { Action } from '../data/mock'
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
  const navigate = useNavigate()
  const [bellOpen, setBellOpen] = useState(false)
  const bellRef = useRef<HTMLElement>(null)

  // Notifications are the real L4 queue, not a decorative dot: an action the
  // dial refused to auto-execute is precisely the thing a human must see.
  const actions = useApi<Action[]>(() => endpoints.actions(), [])
  const pending = actions.data.filter((a) => a.status === 'proposed')

  // Close the panel on outside click / Escape.
  useEffect(() => {
    if (!bellOpen) return
    function onDown(e: MouseEvent) {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) setBellOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setBellOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [bellOpen])

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
          {/* Single-tenant demo: this is a label, not a switcher. Rendering it
              as a dead <button> invited clicks that did nothing. */}
          <div className="flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-ink-2">
            <span className="grid h-5 w-5 place-items-center rounded bg-accent-dim font-mono text-[10px] font-bold text-accent-bright">P</span>
            PayKraft Technologies
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden font-mono text-[11px] text-ink-3 md:block">env: <span className="text-ink-2">demo-tenant</span> · ap-south-1</span>

            {/* Notifications — real pending L4 decisions + recent agent activity.
                The dot only shows when something actually needs the human. */}
            <div className="relative" ref={bellRef as React.RefObject<HTMLDivElement>}>
              <button
                aria-label="Notifications"
                aria-expanded={bellOpen}
                onClick={() => setBellOpen((v) => !v)}
                className="relative cursor-pointer rounded-md p-2 text-ink-2 hover:bg-surface-2 hover:text-ink"
              >
                <Bell size={16} aria-hidden />
                {pending.length > 0 && (
                  <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-status-critical" aria-hidden />
                )}
              </button>

              {bellOpen && (
                <div
                  role="dialog"
                  aria-label="Notifications"
                  className="absolute right-0 z-50 mt-2 w-80 rounded-lg border border-border bg-surface shadow-xl"
                >
                  <div className="border-b border-border-subtle px-4 py-2.5 font-mono text-[11px] font-semibold tracking-widest text-ink-2 uppercase">
                    Needs your decision
                  </div>
                  {pending.length === 0 ? (
                    <p className="px-4 py-4 text-sm text-ink-3">
                      Nothing waiting — every action so far was inside the autonomy dial.
                    </p>
                  ) : (
                    <ul className="divide-y divide-border-subtle">
                      {pending.slice(0, 5).map((a) => (
                        <li key={a.id}>
                          <Link
                            to="/app/provenance"
                            onClick={() => setBellOpen(false)}
                            className="block px-4 py-3 hover:bg-surface-2"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono text-xs font-semibold">{a.id}</span>
                              <span className="font-mono text-[10px] font-bold text-status-warning">{a.level}</span>
                            </div>
                            <p className="mt-1 font-mono text-[11px] text-ink-2">
                              {a.type} → {a.target}
                            </p>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                  <Link
                    to="/app/provenance"
                    onClick={() => setBellOpen(false)}
                    className="block border-t border-border-subtle px-4 py-2.5 text-xs text-accent hover:text-accent-bright"
                  >
                    Open Provenance viewer →
                  </Link>
                </div>
              )}
            </div>

            <div className="grid h-8 w-8 place-items-center rounded-full border border-border bg-surface-2 font-mono text-xs font-semibold text-ink-2" aria-label="Arjun Mehta">
              AM
            </div>
            <button
              onClick={() => { logout(); navigate('/login') }}
              aria-label="Sign out"
              title="Sign out"
              className="cursor-pointer rounded-md p-2 text-ink-2 hover:bg-surface-2 hover:text-ink"
            >
              <LogOut size={16} aria-hidden />
            </button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-5 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
