'use client';

import { useEffect, useState } from 'react';

export default function FlowsPage() {
  const [rules, setRules] = useState<any[]>([]);
  const [transforms, setTransforms] = useState<any[]>([]);

  useEffect(() => {
    fetch('/api/v1/routing/rules').then(r => r.json()).then(setRules).catch(() => {});
    fetch('/api/v1/transforms').then(r => r.json()).then(setTransforms).catch(() => {});
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Productions</h1>
          <p className="text-sm text-slate-500 mt-1">Integration flows, routing rules, and transforms — equivalent to IRIS Productions</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Routing Rules */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900">Routing Rules</h3>
            <a href="/routing" className="text-xs text-cyan-600 hover:text-cyan-700 font-medium">Manage &rarr;</a>
          </div>
          <div className="p-5">
            {rules.length === 0 ? (
              <div className="text-center py-8 text-slate-400 text-sm">
                <p>No rules configured</p>
                <a href="/routing" className="text-cyan-600 hover:underline mt-1 inline-block">Add your first rule</a>
              </div>
            ) : (
              <div className="space-y-2">
                {rules.map((r, i) => (
                  <div key={i} className="bg-slate-50 px-4 py-3 rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-slate-900">{r.name}</span>
                      <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-mono">P{r.priority}</span>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-slate-500">
                      {r.conditions?.map((c: any) => c.value).join(', ')}
                      <span>&rarr;</span>
                      <span className="text-purple-600 font-medium">{r.destinations?.map((d: any) => d.name).join(', ')}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Transforms */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900">Transforms</h3>
            <a href="/agents/designer" className="text-xs text-cyan-600 hover:text-cyan-700 font-medium">AI Designer &rarr;</a>
          </div>
          <div className="p-5">
            {transforms.length === 0 ? (
              <div className="text-center py-8 text-slate-400 text-sm">
                <p>No transforms registered</p>
                <a href="/agents/designer" className="text-cyan-600 hover:underline mt-1 inline-block">Design with AI</a>
              </div>
            ) : (
              <div className="space-y-2">
                {transforms.map((t, i) => (
                  <div key={i} className="flex items-center justify-between bg-slate-50 px-4 py-3 rounded-lg">
                    <div>
                      <span className="text-sm font-medium text-slate-900">{t.name}</span>
                      <span className="text-xs text-slate-400 ml-2">v{t.version}</span>
                    </div>
                    <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full">Active</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Architecture diagram */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h3 className="font-semibold text-slate-900 mb-4">Message Pipeline</h3>
          <div className="flex items-center justify-between gap-2 overflow-x-auto pb-2">
            {['MLLP Listener', 'NATS Inbound', 'Routing Engine', 'Transform', 'NATS Outbound', 'MLLP Sender', 'ACK'].map((step, i) => (
              <div key={i} className="flex items-center gap-2 flex-shrink-0">
                <div className="bg-gradient-to-br from-cyan-50 to-blue-50 border border-cyan-200 px-4 py-3 rounded-lg text-center min-w-[120px]">
                  <div className="text-xs font-medium text-cyan-800">{step}</div>
                </div>
                {i < 6 && <svg className="w-5 h-5 text-slate-300 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
