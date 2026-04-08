'use client';

import { useState } from 'react';

const SAMPLE_ADT = `MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408120000||ADT^A08|MSG001|P|2.5
EVN|A08|20260408120000
PID|1||PAC123^^^MPI^MR||GONZALEZ^MARIA||19800115|F
PV1|1|I|SALA301^CAMA1`;

export default function MessagesPage() {
  const [message, setMessage] = useState(SAMPLE_ADT);
  const [parsed, setParsed] = useState<any>(null);
  const [fhir, setFhir] = useState<any>(null);
  const [tab, setTab] = useState<'parse' | 'fhir'>('parse');

  const handleParse = async () => {
    const res = await fetch('/api/v1/messages/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    setParsed(await res.json());
  };

  const handleConvert = async () => {
    const res = await fetch('/fhir/$convert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    setFhir(await res.json());
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Message Inspector</h2>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <label className="block text-sm font-medium mb-2">HL7 v2.x Message</label>
        <textarea
          className="w-full h-40 font-mono text-sm border rounded p-3 bg-gray-50"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        <div className="flex gap-3 mt-3">
          <button
            onClick={handleParse}
            className="bg-healthflow-600 text-white px-4 py-2 rounded hover:bg-healthflow-700"
          >
            Parse HL7
          </button>
          <button
            onClick={handleConvert}
            className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
          >
            Convert to FHIR
          </button>
        </div>
      </div>

      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setTab('parse')}
          className={`px-4 py-2 rounded ${tab === 'parse' ? 'bg-healthflow-600 text-white' : 'bg-gray-200'}`}
        >
          Parsed HL7
        </button>
        <button
          onClick={() => setTab('fhir')}
          className={`px-4 py-2 rounded ${tab === 'fhir' ? 'bg-green-600 text-white' : 'bg-gray-200'}`}
        >
          FHIR Bundle
        </button>
      </div>

      {tab === 'parse' && parsed && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div><span className="text-gray-500">Type:</span> <strong>{parsed.message_type}</strong></div>
            <div><span className="text-gray-500">Event:</span> <strong>{parsed.trigger_event}</strong></div>
            <div><span className="text-gray-500">ID:</span> <strong>{parsed.message_id}</strong></div>
            <div><span className="text-gray-500">From:</span> <strong>{parsed.sending_app}</strong></div>
          </div>
          <h4 className="font-semibold mb-2">Segments ({parsed.segment_count})</h4>
          <div className="space-y-1">
            {parsed.segments?.map((seg: any, i: number) => (
              <div key={i} className="flex gap-3 font-mono text-sm bg-gray-50 px-3 py-1 rounded">
                <span className="font-bold text-healthflow-700 w-10">{seg.name}</span>
                <span className="text-gray-500">{seg.fields} fields</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'fhir' && fhir && (
        <div className="bg-white rounded-lg shadow p-6">
          <pre className="font-mono text-sm overflow-auto max-h-96 bg-gray-50 p-4 rounded">
            {JSON.stringify(fhir, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
