'use client';

import { useEffect, useState } from 'react';

interface HealthData {
  status: string;
  version: string;
  nats: boolean;
  redis: boolean;
  database: boolean;
  agents: string[];
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/health')
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          Error connecting to backend: {error}
        </div>
      )}

      {health && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatusCard title="Engine" value={health.status} ok={health.status === 'ok'} />
          <StatusCard title="NATS JetStream" value={health.nats ? 'Connected' : 'Disconnected'} ok={health.nats} />
          <StatusCard title="Redis" value={health.redis ? 'Connected' : 'Disconnected'} ok={health.redis} />
          <StatusCard title="Database" value={health.database ? 'Connected' : 'Disconnected'} ok={health.database} />
        </div>
      )}

      {health?.agents && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-lg font-semibold mb-3">AI Agents</h3>
          <div className="flex flex-wrap gap-2">
            {health.agents.map((agent) => (
              <span key={agent} className="bg-healthflow-50 text-healthflow-700 px-3 py-1 rounded-full text-sm">
                {agent}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-3">Quick Actions</h3>
          <div className="space-y-2">
            <a href="/messages" className="block bg-gray-50 hover:bg-gray-100 px-4 py-3 rounded">
              Parse HL7 Message
            </a>
            <a href="/flows" className="block bg-gray-50 hover:bg-gray-100 px-4 py-3 rounded">
              Manage Flows
            </a>
            <a href="/agents" className="block bg-gray-50 hover:bg-gray-100 px-4 py-3 rounded">
              Chat with OpsAgent
            </a>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-3">System Info</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Version</dt>
              <dd className="font-mono">{health?.version || '...'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">AI Backend</dt>
              <dd className="font-mono">AWS Bedrock</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Message Bus</dt>
              <dd className="font-mono">NATS JetStream</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}

function StatusCard({ title, value, ok }: { title: string; value: string; ok: boolean }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="text-sm text-gray-500 mb-1">{title}</div>
      <div className="flex items-center gap-2">
        <div className={`w-2.5 h-2.5 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="font-semibold">{value}</span>
      </div>
    </div>
  );
}
