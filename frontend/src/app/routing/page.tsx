'use client';

import { useEffect, useState } from 'react';

export default function RoutingPage() {
  const [rules, setRules] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: '', field: 'MSH-9.1', operator: 'equals', value: '', destination: '', adapter: '', priority: '100' });

  const loadRules = () => {
    fetch('/api/v1/routing/rules').then(r => r.json()).then(setRules).catch(() => {});
  };

  useEffect(() => { loadRules(); }, []);

  const handleAdd = async () => {
    await fetch('/api/v1/routing/rules', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: form.name,
        priority: parseInt(form.priority),
        conditions: [{ field: form.field, operator: form.operator, value: form.value }],
        destinations: [{ name: form.destination, adapter_name: form.adapter }],
      }),
    });
    setShowAdd(false);
    setForm({ name: '', field: 'MSH-9.1', operator: 'equals', value: '', destination: '', adapter: '', priority: '100' });
    loadRules();
  };

  const handleDelete = async (name: string) => {
    await fetch(`/api/v1/routing/rules/${name}`, { method: 'DELETE' });
    loadRules();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Routing Rules</h1>
          <p className="text-sm text-slate-500 mt-1">Deterministic routing rules evaluated in &lt;1ms</p>
        </div>
        <button onClick={() => setShowAdd(!showAdd)}
          className="bg-cyan-600 text-white px-4 py-2 rounded-lg hover:bg-cyan-700 text-sm font-medium transition-colors">
          + Add Rule
        </button>
      </div>

      {showAdd && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-6">
          <h3 className="font-semibold text-slate-900 mb-4">New Routing Rule</h3>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Rule Name" value={form.name} onChange={v => setForm({...form, name: v})} placeholder="ADT to LIS" />
            <Input label="Priority" value={form.priority} onChange={v => setForm({...form, priority: v})} placeholder="100" />
            <Input label="HL7 Field" value={form.field} onChange={v => setForm({...form, field: v})} placeholder="MSH-9.1" />
            <select value={form.operator} onChange={e => setForm({...form, operator: e.target.value})}
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm">
              {['equals','not_equals','contains','starts_with','ends_with','in','matches'].map(op => (
                <option key={op} value={op}>{op}</option>
              ))}
            </select>
            <Input label="Value" value={form.value} onChange={v => setForm({...form, value: v})} placeholder="ADT" />
            <Input label="Destination" value={form.destination} onChange={v => setForm({...form, destination: v})} placeholder="LIS" />
            <Input label="Adapter Name" value={form.adapter} onChange={v => setForm({...form, adapter: v})} placeholder="MLLP_LIS" />
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={handleAdd} className="bg-cyan-600 text-white px-4 py-2 rounded-lg text-sm font-medium">Create</button>
            <button onClick={() => setShowAdd(false)} className="text-slate-500 px-4 py-2 text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="font-semibold text-slate-900">{rules.length} Rules</h3>
        </div>
        {rules.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-sm">No routing rules configured yet</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {rules.map((rule, i) => (
              <div key={i} className="px-5 py-4 hover:bg-slate-50 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-mono">P{rule.priority}</span>
                    <span className="font-medium text-slate-900">{rule.name}</span>
                  </div>
                  <button onClick={() => handleDelete(rule.name)} className="text-xs text-red-400 hover:text-red-600">Delete</button>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {rule.conditions?.map((c: any, ci: number) => (
                    <span key={ci} className="text-xs font-mono bg-slate-100 text-slate-600 px-2 py-1 rounded">
                      {c.field} {c.operator} &quot;{c.value}&quot;
                    </span>
                  ))}
                  <span className="text-xs text-slate-400">&rarr;</span>
                  {rule.destinations?.map((d: any, di: number) => (
                    <span key={di} className="text-xs bg-purple-50 text-purple-600 px-2 py-1 rounded font-medium">
                      {d.name}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Input({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div>
      <label className="text-xs font-medium text-slate-500 block mb-1">{label}</label>
      <input type="text" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500" />
    </div>
  );
}
