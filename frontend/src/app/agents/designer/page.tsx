'use client';

import { useState } from 'react';

export default function TransformDesignerPage() {
  const [spec, setSpec] = useState('');
  const [sampleMsg, setSampleMsg] = useState('MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408||ADT^A08|MSG001|P|2.5\rPID|1||PAC123^^^MPI||GONZALEZ^MARIA||19800115|F\rPV1|1|I|SALA301');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleDesign = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/v1/transforms/design', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          spec,
          sample_messages: [sampleMsg],
          flow_id: '00000000-0000-0000-0000-000000000001',
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        setError(err.detail || 'Design failed');
      } else {
        setResult(await res.json());
      }
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  };

  const handleRegister = async () => {
    if (!result?.source_code) return;
    const name = prompt('Transform name:');
    if (!name) return;
    const res = await fetch('/api/v1/transforms', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        source_code: result.source_code,
        flow_id: '00000000-0000-0000-0000-000000000001',
      }),
    });
    if (res.ok) alert(`Transform "${name}" registered successfully`);
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">AI Transform Designer</h1>
        <p className="text-sm text-slate-500 mt-1">Describe what you want in natural language — Claude Opus generates the Python code</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Input */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h3 className="font-semibold text-slate-900 mb-3">Transformation Spec</h3>
            <textarea
              className="w-full h-32 border border-slate-200 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 resize-none"
              value={spec}
              onChange={e => setSpec(e.target.value)}
              placeholder="Example: Remap MSH-3 from SAP to SAP-ENTERPRISE, change MSH-5 to HEALTHFLOW, and strip PID-13 (phone) for privacy"
            />
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h3 className="font-semibold text-slate-900 mb-3">Sample HL7 Message</h3>
            <textarea
              className="w-full h-32 font-mono text-xs border border-slate-200 rounded-lg p-3 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-cyan-500 resize-none"
              value={sampleMsg}
              onChange={e => setSampleMsg(e.target.value)}
            />
          </div>

          <button onClick={handleDesign} disabled={loading || !spec.trim()}
            className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 text-white px-6 py-3 rounded-lg hover:from-cyan-700 hover:to-blue-700 transition-all text-sm font-semibold disabled:opacity-50 flex items-center justify-center gap-2">
            {loading ? (
              <><span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" /> Generating with Claude Opus...</>
            ) : (
              <><svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg> Generate Transform</>
            )}
          </button>
        </div>

        {/* Output */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900">Generated Code</h3>
            {result?.validated && (
              <button onClick={handleRegister} className="text-xs bg-emerald-50 text-emerald-700 px-3 py-1.5 rounded-lg hover:bg-emerald-100 font-medium">
                Register Transform
              </button>
            )}
          </div>
          <div className="p-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm mb-4">{error}</div>
            )}

            {result ? (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  {result.validated ? (
                    <span className="flex items-center gap-1 text-xs bg-green-50 text-green-700 px-2 py-1 rounded-full">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                      Validated
                    </span>
                  ) : (
                    <span className="text-xs bg-red-50 text-red-700 px-2 py-1 rounded-full">Validation failed</span>
                  )}
                </div>
                <pre className="text-xs font-mono bg-slate-900 text-slate-100 p-4 rounded-lg overflow-x-auto max-h-80">
                  {result.source_code}
                </pre>
                {result.test_results?.length > 0 && (
                  <div className="mt-3">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">Test Results</h4>
                    {result.test_results.map((t: any, i: number) => (
                      <div key={i} className={`text-xs px-3 py-2 rounded mb-1 ${
                        t.status === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                      }`}>
                        Message {t.message_index}: {t.status} {t.error ? `— ${t.error}` : ''}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
                Describe your transformation and click Generate
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
