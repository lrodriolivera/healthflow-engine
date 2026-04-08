'use client';

import { useEffect, useState } from 'react';

export default function AgentsPage() {
  const [status, setStatus] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [chatHistory, setChatHistory] = useState<{ role: string; text: string }[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch('/api/v1/agents/status')
      .then((r) => r.json())
      .then(setStatus);
  }, []);

  const handleSend = async () => {
    if (!message.trim()) return;
    setChatHistory((prev) => [...prev, { role: 'user', text: message }]);
    setLoading(true);

    try {
      const res = await fetch('/api/v1/agents/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      const data = await res.json();
      if (res.ok) {
        setChatHistory((prev) => [...prev, { role: 'agent', text: data.response }]);
      } else {
        setChatHistory((prev) => [...prev, { role: 'error', text: data.detail || 'Agent not available' }]);
      }
    } catch (e: any) {
      setChatHistory((prev) => [...prev, { role: 'error', text: e.message }]);
    }

    setMessage('');
    setLoading(false);
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">AI Agents</h2>

      {status && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="font-semibold mb-3">Agent Status</h3>
          <div className="flex gap-2 flex-wrap mb-3">
            {status.agents?.map((agent: string) => (
              <span key={agent} className="bg-green-50 text-green-700 px-3 py-1 rounded-full text-sm">
                {agent}
              </span>
            ))}
          </div>
          <div className="text-sm text-gray-500">
            Bedrock: {status.bedrock ? 'Connected' : 'Not configured'}
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="font-semibold mb-3">ChatOps — OpsAgent</h3>
        <div className="border rounded-lg h-80 overflow-y-auto p-4 mb-4 bg-gray-50 space-y-3">
          {chatHistory.length === 0 && (
            <div className="text-gray-400 text-sm">
              Ask the OpsAgent anything: &quot;Show recent errors&quot;, &quot;What flows are active?&quot;, &quot;Why did MSG001 fail?&quot;
            </div>
          )}
          {chatHistory.map((msg, i) => (
            <div key={i} className={`${msg.role === 'user' ? 'text-right' : ''}`}>
              <div
                className={`inline-block max-w-[80%] px-4 py-2 rounded-lg text-sm ${
                  msg.role === 'user'
                    ? 'bg-healthflow-600 text-white'
                    : msg.role === 'error'
                    ? 'bg-red-50 text-red-700'
                    : 'bg-white border'
                }`}
              >
                <pre className="whitespace-pre-wrap font-sans">{msg.text}</pre>
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask the OpsAgent..."
            className="flex-1 border rounded px-4 py-2"
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={loading}
            className="bg-healthflow-600 text-white px-6 py-2 rounded hover:bg-healthflow-700 disabled:opacity-50"
          >
            {loading ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}
