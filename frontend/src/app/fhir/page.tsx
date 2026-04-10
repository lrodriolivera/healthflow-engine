'use client';

import { useEffect, useState } from 'react';

export default function FHIRPage() {
  const [smartConfig, setSmartConfig] = useState<any>(null);
  const [resourceType, setResourceType] = useState('Patient');
  const [resources, setResources] = useState<any>(null);

  useEffect(() => {
    fetch('/fhir/.well-known/smart-configuration').then(r => r.json()).then(setSmartConfig).catch(() => {});
  }, []);

  const handleSearch = async () => {
    const res = await fetch(`/fhir/${resourceType}`);
    setResources(await res.json());
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">FHIR R4 Server</h1>
        <p className="text-sm text-slate-500 mt-1">RESTful FHIR server with SMART on FHIR auth and Bulk Data export</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Server Info */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h3 className="font-semibold text-slate-900 mb-4">Server</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between"><span className="text-slate-500">Base URL</span><span className="font-mono">/fhir</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Version</span><span>R4 (4.0.1)</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Auth</span><span>SMART on FHIR</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Bulk Data</span><span className="text-green-600">$export</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Subscriptions</span><span className="text-green-600">R5 topic-based</span></div>
          </div>
          <h4 className="font-semibold text-slate-900 mt-5 mb-2 text-xs uppercase tracking-wider text-slate-500">v2 &rarr; FHIR Mappings</h4>
          <div className="space-y-1 text-xs">
            <div className="bg-slate-50 px-3 py-2 rounded">ADT &rarr; Patient + Encounter</div>
            <div className="bg-slate-50 px-3 py-2 rounded">ORM/OML &rarr; ServiceRequest</div>
            <div className="bg-slate-50 px-3 py-2 rounded">ORU &rarr; DiagnosticReport + Observation</div>
          </div>
        </div>

        {/* Resource Browser */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-3">
            <select value={resourceType} onChange={e => setResourceType(e.target.value)}
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm">
              {['Patient', 'Encounter', 'Observation', 'DiagnosticReport', 'ServiceRequest', 'Condition', 'Practitioner', 'Organization'].map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <button onClick={handleSearch}
              className="bg-cyan-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-cyan-700">
              Search
            </button>
          </div>
          <div className="p-5">
            {resources ? (
              <div>
                <div className="text-xs text-slate-500 mb-3">{resources.total || 0} results</div>
                {resources.entry?.length > 0 ? (
                  resources.entry.map((e: any, i: number) => (
                    <details key={i} className="mb-2">
                      <summary className="bg-slate-50 px-4 py-2.5 rounded-lg cursor-pointer hover:bg-slate-100 text-sm font-medium">
                        {e.resource?.resourceType}/{e.resource?.id?.slice(0, 8)}
                      </summary>
                      <pre className="mt-1 text-xs font-mono bg-slate-900 text-slate-100 p-4 rounded-lg overflow-x-auto">
                        {JSON.stringify(e.resource, null, 2)}
                      </pre>
                    </details>
                  ))
                ) : (
                  <div className="text-center py-8 text-slate-400 text-sm">No {resourceType} resources found</div>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-slate-400 text-sm">Select a resource type and click Search</div>
            )}
          </div>
        </div>
      </div>

      {/* SMART Config */}
      {smartConfig && (
        <div className="mt-6 bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h3 className="font-semibold text-slate-900 mb-3">SMART on FHIR Configuration</h3>
          <pre className="text-xs font-mono bg-slate-50 p-4 rounded-lg overflow-x-auto max-h-48">
            {JSON.stringify(smartConfig, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
