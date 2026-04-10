'use client';

import { useState } from 'react';

const SAMPLES: Record<string, string> = {
  'ADT^A08': 'MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408120000||ADT^A08^ADT_A01|MSG001|P|2.5|||AL|NE\rEVN|A08|20260408120000\rPID|1||PAC123^^^MPI^MR~12345678-9^^^RUN^RUN||GONZALEZ^MARIA^TERESA||19800115|F|||AV LIBERTADOR 1234^^SANTIAGO^^8320000^CL||+56912345678\rPV1|1|I|SALA301^CAMA1^1^^^HOSP_CENTRAL||||MED001^DR.LOPEZ^JUAN',
  'OML^O21': 'MSH|^~\\&|MODULAB|LAB|IRIS|UCCHRISTUS|20260408130000||OML^O21|MSG002|P|2.5\rPID|1||PAC456^^^MPI^MR||PEREZ^CARLOS||19750320|M\rORC|NW|ORD001|SOL001||CM\rOBR|1|ORD001|SOL001|HEMO^Hemograma completo\rORC|NW|ORD002|SOL002||CM\rOBR|2|ORD002|SOL002|GLUC^Glicemia',
  'DFT^P03': 'MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408140000||DFT^P03|MSG003|P|2.5\rEVN|P03|20260408140000\rPID|1||PAC789^^^MPI^MR||SILVA^PEDRO||19901225|M\rFT1|1|E12345|E12345.PREST001|20260408|20260408|CG||100.00|||1\rPR1|1||PREST001^Radiografia Torax',
};

export default function MessagesPage() {
  const [message, setMessage] = useState(SAMPLES['ADT^A08']);
  const [parsed, setParsed] = useState<any>(null);
  const [fhir, setFhir] = useState<any>(null);
  const [routeResult, setRouteResult] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'parsed' | 'fhir' | 'routing'>('parsed');
  const [loading, setLoading] = useState(false);

  const handleParse = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/messages/parse', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      setParsed(await res.json());
      setActiveTab('parsed');
    } catch (e) {}
    setLoading(false);
  };

  const handleConvert = async () => {
    setLoading(true);
    try {
      const res = await fetch('/fhir/$convert', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      setFhir(await res.json());
      setActiveTab('fhir');
    } catch (e) {}
    setLoading(false);
  };

  const handleRoute = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/routing/test', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      setRouteResult(await res.json());
      setActiveTab('routing');
    } catch (e) {}
    setLoading(false);
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Message Viewer</h1>
        <p className="text-sm text-slate-500 mt-1">Parse, inspect, convert, and test routing for HL7 v2.x messages</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Input Panel */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900">HL7 v2.x Input</h3>
            <div className="flex gap-1">
              {Object.keys(SAMPLES).map(key => (
                <button key={key} onClick={() => setMessage(SAMPLES[key])}
                  className="text-xs px-2 py-1 bg-slate-100 hover:bg-slate-200 rounded text-slate-600 transition-colors">
                  {key}
                </button>
              ))}
            </div>
          </div>
          <div className="p-5">
            <textarea
              className="w-full h-64 font-mono text-xs border border-slate-200 rounded-lg p-4 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent resize-none"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              spellCheck={false}
            />
            <div className="flex gap-2 mt-4">
              <button onClick={handleParse} disabled={loading}
                className="flex-1 bg-cyan-600 text-white px-4 py-2.5 rounded-lg hover:bg-cyan-700 transition-colors text-sm font-medium disabled:opacity-50">
                Parse HL7
              </button>
              <button onClick={handleConvert} disabled={loading}
                className="flex-1 bg-emerald-600 text-white px-4 py-2.5 rounded-lg hover:bg-emerald-700 transition-colors text-sm font-medium disabled:opacity-50">
                HL7 &rarr; FHIR
              </button>
              <button onClick={handleRoute} disabled={loading}
                className="flex-1 bg-purple-600 text-white px-4 py-2.5 rounded-lg hover:bg-purple-700 transition-colors text-sm font-medium disabled:opacity-50">
                Test Routing
              </button>
            </div>
          </div>
        </div>

        {/* Output Panel */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100">
            <div className="flex gap-1">
              {(['parsed', 'fhir', 'routing'] as const).map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    activeTab === tab ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-100'
                  }`}>
                  {tab === 'parsed' ? 'Parsed HL7' : tab === 'fhir' ? 'FHIR Bundle' : 'Routing'}
                </button>
              ))}
            </div>
          </div>
          <div className="p-5 max-h-[500px] overflow-y-auto">
            {activeTab === 'parsed' && parsed && <ParsedView data={parsed} />}
            {activeTab === 'fhir' && fhir && <FHIRView data={fhir} />}
            {activeTab === 'routing' && routeResult && <RoutingView data={routeResult} />}
            {!parsed && !fhir && !routeResult && (
              <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
                Click a button to analyze the message
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ParsedView({ data }: { data: any }) {
  if (data.error) return <div className="text-red-600 text-sm">{data.error}</div>;
  return (
    <div>
      <div className="grid grid-cols-2 gap-3 mb-5">
        <Field label="Message Type" value={data.message_type} highlight />
        <Field label="Trigger Event" value={data.trigger_event} />
        <Field label="Control ID" value={data.message_id} />
        <Field label="Sending App" value={data.sending_app} />
        <Field label="Facility" value={data.sending_facility} />
        <Field label="Version" value={data.version} />
      </div>
      <div className="border-t border-slate-100 pt-4">
        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Segments ({data.segment_count})
        </h4>
        <div className="space-y-1">
          {data.segments?.map((seg: any, i: number) => (
            <div key={i} className="flex items-center gap-3 font-mono text-xs bg-slate-50 px-3 py-2 rounded-lg">
              <span className="hl7-segment w-10 font-bold">{seg.name}</span>
              <div className="flex-1 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${Math.min(seg.fields * 8, 100)}%` }} />
              </div>
              <span className="text-slate-400 w-16 text-right">{seg.fields} fields</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FHIRView({ data }: { data: any }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <span className="bg-emerald-50 text-emerald-700 px-2 py-1 rounded text-xs font-medium">
          {data.type} Bundle
        </span>
        <span className="text-xs text-slate-500">{data.entry?.length || 0} resources</span>
      </div>
      {data.entry?.map((entry: any, i: number) => (
        <details key={i} className="mb-2 group">
          <summary className="flex items-center gap-2 bg-slate-50 px-4 py-2.5 rounded-lg cursor-pointer hover:bg-slate-100 transition-colors">
            <svg className="w-3 h-3 text-slate-400 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
            <span className="text-sm font-medium text-slate-900">{entry.resource?.resourceType}</span>
            <span className="text-xs text-slate-400">{entry.resource?.id?.slice(0, 8)}...</span>
          </summary>
          <pre className="mt-1 text-xs font-mono bg-slate-900 text-slate-100 p-4 rounded-lg overflow-x-auto">
            {JSON.stringify(entry.resource, null, 2)}
          </pre>
        </details>
      ))}
    </div>
  );
}

function RoutingView({ data }: { data: any }) {
  if (data.detail) return <div className="text-red-600 text-sm">{data.detail}</div>;
  return (
    <div>
      <div className="grid grid-cols-2 gap-3 mb-5">
        <Field label="Message Type" value={data.message_type} highlight />
        <Field label="Trigger Event" value={data.trigger_event} />
      </div>
      <div className="mb-4">
        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Matched Rules</h4>
        {data.matched_rules?.length ? data.matched_rules.map((r: string, i: number) => (
          <div key={i} className="bg-blue-50 text-blue-700 px-3 py-2 rounded-lg text-sm mb-1">{r}</div>
        )) : <div className="text-sm text-slate-400">No rules matched (AI Router candidate)</div>}
      </div>
      <div>
        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Destinations</h4>
        {data.destinations?.length ? data.destinations.map((d: string, i: number) => (
          <div key={i} className="flex items-center gap-2 bg-purple-50 text-purple-700 px-3 py-2 rounded-lg text-sm mb-1">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
            {d}
          </div>
        )) : <div className="text-sm text-slate-400">No destinations</div>}
      </div>
    </div>
  );
}

function Field({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="bg-slate-50 px-3 py-2 rounded-lg">
      <div className="text-[10px] font-medium text-slate-400 uppercase">{label}</div>
      <div className={`text-sm font-mono ${highlight ? 'text-cyan-700 font-bold' : 'text-slate-900'}`}>{value || '-'}</div>
    </div>
  );
}
