'use client';

import { useEffect, useState } from 'react';

export default function FlowsPage() {
  const [flows, setFlows] = useState<any[]>([]);
  const [rules, setRules] = useState<any[]>([]);
  const [transforms, setTransforms] = useState<any[]>([]);

  useEffect(() => {
    fetch('/api/v1/flows').then((r) => r.json()).then(setFlows).catch(() => {});
    fetch('/api/v1/routing/rules').then((r) => r.json()).then(setRules).catch(() => {});
    fetch('/api/v1/transforms').then((r) => r.json()).then(setTransforms).catch(() => {});
  }, []);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Flows & Configuration</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Flows */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold mb-3">Flows</h3>
          {flows.length === 0 ? (
            <p className="text-gray-400 text-sm">No flows configured</p>
          ) : (
            <div className="space-y-2">
              {flows.map((f: any) => (
                <div key={f.id} className="flex justify-between items-center bg-gray-50 px-3 py-2 rounded">
                  <span className="font-medium">{f.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${f.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {f.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Routing Rules */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold mb-3">Routing Rules</h3>
          {rules.length === 0 ? (
            <p className="text-gray-400 text-sm">No rules configured</p>
          ) : (
            <div className="space-y-2">
              {rules.map((r: any, i: number) => (
                <div key={i} className="bg-gray-50 px-3 py-2 rounded">
                  <div className="font-medium text-sm">{r.name}</div>
                  <div className="text-xs text-gray-500">
                    Priority: {r.priority} | Destinations: {r.destinations?.map((d: any) => d.name).join(', ')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Transforms */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold mb-3">Transforms</h3>
          {transforms.length === 0 ? (
            <p className="text-gray-400 text-sm">No transforms registered</p>
          ) : (
            <div className="space-y-2">
              {transforms.map((t: any, i: number) => (
                <div key={i} className="bg-gray-50 px-3 py-2 rounded">
                  <span className="font-medium text-sm">{t.name}</span>
                  <span className="text-xs text-gray-500 ml-2">v{t.version}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
