'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';

const NAV_ITEMS = [
  {
    section: 'Overview',
    items: [
      { href: '/', label: 'Dashboard', icon: DashboardIcon },
    ],
  },
  {
    section: 'Integration',
    items: [
      { href: '/flows', label: 'Productions', icon: FlowsIcon },
      { href: '/messages', label: 'Message Viewer', icon: MessagesIcon },
      { href: '/routing', label: 'Routing Rules', icon: RoutingIcon },
      { href: '/transforms', label: 'Transforms', icon: TransformIcon },
    ],
  },
  {
    section: 'AI Agents',
    items: [
      { href: '/agents', label: 'ChatOps', icon: AgentIcon },
      { href: '/agents/designer', label: 'Transform Designer', icon: DesignerIcon },
    ],
  },
  {
    section: 'Standards',
    items: [
      { href: '/fhir', label: 'FHIR Server', icon: FHIRIcon },
    ],
  },
  {
    section: 'System',
    items: [
      { href: '/settings', label: 'Settings', icon: SettingsIcon },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[260px] bg-slate-900 text-white flex flex-col z-50">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-700/50">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-gradient-to-br from-cyan-400 to-blue-600 rounded-lg flex items-center justify-center font-bold text-sm">
            HF
          </div>
          <div>
            <div className="font-semibold text-sm">HealthFlow Engine</div>
            <div className="text-[10px] text-slate-400">AI-native integration</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-3">
        {NAV_ITEMS.map((section) => (
          <div key={section.section} className="mb-4">
            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider px-3 mb-1">
              {section.section}
            </div>
            {section.items.map((item) => {
              const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all ${
                    isActive
                      ? 'bg-cyan-600/20 text-cyan-400 font-medium'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <item.icon active={isActive} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Status footer */}
      <div className="px-5 py-4 border-t border-slate-700/50">
        <div className="flex items-center gap-2 text-xs">
          <div className="w-2 h-2 bg-green-500 rounded-full pulse-green" />
          <span className="text-slate-400">Engine running</span>
        </div>
        <div className="text-[10px] text-slate-500 mt-1">v0.1.0 &middot; Bedrock</div>
      </div>
    </aside>
  );
}

// --- Icons (inline SVG for zero dependencies) ---

function DashboardIcon({ active }: { active: boolean }) {
  return (
    <svg className={`w-4 h-4 ${active ? 'text-cyan-400' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
    </svg>
  );
}

function FlowsIcon({ active }: { active: boolean }) {
  return (
    <svg className={`w-4 h-4 ${active ? 'text-cyan-400' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  );
}

function MessagesIcon({ active }: { active: boolean }) {
  return (
    <svg className={`w-4 h-4 ${active ? 'text-cyan-400' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
    </svg>
  );
}

function RoutingIcon({ active }: { active: boolean }) {
  return (
    <svg className={`w-4 h-4 ${active ? 'text-cyan-400' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
    </svg>
  );
}

function TransformIcon({ active }: { active: boolean }) {
  return (
    <svg className={`w-4 h-4 ${active ? 'text-cyan-400' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  );
}

function AgentIcon({ active }: { active: boolean }) {
  return (
    <svg className={`w-4 h-4 ${active ? 'text-cyan-400' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714a2.25 2.25 0 00.659 1.591L19 14.5M14.25 3.104c.251.023.501.05.75.082M19 14.5l-1.5 4.5H6.5L5 14.5m14 0H5" />
    </svg>
  );
}

function DesignerIcon({ active }: { active: boolean }) {
  return (
    <svg className={`w-4 h-4 ${active ? 'text-cyan-400' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
    </svg>
  );
}

function FHIRIcon({ active }: { active: boolean }) {
  return (
    <svg className={`w-4 h-4 ${active ? 'text-cyan-400' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
    </svg>
  );
}

function SettingsIcon({ active }: { active: boolean }) {
  return (
    <svg className={`w-4 h-4 ${active ? 'text-cyan-400' : 'text-slate-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}
