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
  const [rules, setRules] = useState<any[]>([]);
  const [transforms, setTransforms] = useState<any[]>([]);

  useEffect(() => {
    fetch('/health').then(r => r.json()).then(setHealth).catch(e => setError(e.message));
    fetch('/api/v1/routing/rules').then(r => r.json()).then(setRules).catch(() => {});
    fetch('/api/v1/transforms').then(r => r.json()).then(setTransforms).catch(() => {});
  }, []);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">System overview and health monitoring</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          {health?.status === 'ok' && (
            <span className="flex items-center gap-1.5 bg-green-50 text-green-700 px-3 py-1.5 rounded-full border border-green-200">
              <span className="w-2 h-2 bg-green-500 rounded-full pulse-green" />
              All systems operational
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 flex items-center gap-2">
          <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
          Backend unreachable: {error}
        </div>
      )}

      {/* Service Status Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <ServiceCard name="Backend API" status={health?.status === 'ok'} detail="FastAPI + asyncio" port="8000" />
        <ServiceCard name="PostgreSQL" status={health?.database} detail="TimescaleDB" port="5434" />
        <ServiceCard name="NATS JetStream" status={health?.nats} detail="Message bus" port="4222" />
        <ServiceCard name="Redis" status={health?.redis} detail="Cache + lookups" port="6380" />
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard label="Routing Rules" value={rules.length} icon="rules" color="blue" />
        <StatCard label="Transforms" value={transforms.length} icon="transforms" color="purple" />
        <StatCard label="AI Agents" value={health?.agents?.length || 0} icon="agents" color="cyan" />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AI Agents */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100">
            <h3 className="font-semibold text-slate-900">AI Agents</h3>
          </div>
          <div className="p-5">
            {health?.agents?.length ? (
              <div className="space-y-3">
                {health.agents.map(agent => (
                  <div key={agent} className="flex items-center justify-between bg-slate-50 px-4 py-3 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-gradient-to-br from-cyan-400 to-blue-600 rounded-lg flex items-center justify-center">
                        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714a2.25 2.25 0 00.659 1.591L19 14.5" /></svg>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-slate-900">{formatAgentName(agent)}</div>
                        <div className="text-xs text-slate-500">{getAgentModel(agent)}</div>
                      </div>
                    </div>
                    <span className="text-xs bg-green-50 text-green-700 px-2 py-1 rounded-full">Active</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-slate-400 text-sm">
                Configure AWS Bedrock credentials to enable AI agents
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100">
            <h3 className="font-semibold text-slate-900">Quick Actions</h3>
          </div>
          <div className="p-5 space-y-2">
            <ActionLink href="/messages" label="Parse HL7 Message" desc="Inspect and convert HL7 v2.x messages" />
            <ActionLink href="/messages" label="Convert HL7 to FHIR" desc="Transform v2 messages to FHIR R4 Bundles" />
            <ActionLink href="/routing" label="Test Routing" desc="Evaluate routing rules against a message" />
            <ActionLink href="/agents" label="Ask OpsAgent" desc="Natural language operations via ChatOps" />
            <ActionLink href="/agents/designer" label="Design Transform" desc="AI generates Python transform from spec" />
          </div>
        </div>
      </div>
    </div>
  );
}

function ServiceCard({ name, status, detail, port }: { name: string; status?: boolean; detail: string; port: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-slate-700">{name}</span>
        <span className={`w-2.5 h-2.5 rounded-full ${status ? 'bg-green-500 pulse-green' : status === false ? 'bg-red-400' : 'bg-slate-300'}`} />
      </div>
      <div className="text-xs text-slate-500">{detail}</div>
      <div className="text-xs text-slate-400 font-mono mt-1">:{port}</div>
    </div>
  );
}

function StatCard({ label, value, icon, color }: { label: string; value: number; icon: string; color: string }) {
  const colors = {
    blue: 'from-blue-500 to-blue-600',
    purple: 'from-purple-500 to-purple-600',
    cyan: 'from-cyan-500 to-cyan-600',
  };
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex items-center gap-4">
      <div className={`w-12 h-12 bg-gradient-to-br ${colors[color as keyof typeof colors]} rounded-xl flex items-center justify-center text-white font-bold text-lg`}>
        {value}
      </div>
      <div>
        <div className="text-2xl font-bold text-slate-900">{value}</div>
        <div className="text-xs text-slate-500">{label}</div>
      </div>
    </div>
  );
}

function ActionLink({ href, label, desc }: { href: string; label: string; desc: string }) {
  return (
    <a href={href} className="flex items-center justify-between bg-slate-50 hover:bg-slate-100 px-4 py-3 rounded-lg transition-colors group">
      <div>
        <div className="text-sm font-medium text-slate-900">{label}</div>
        <div className="text-xs text-slate-500">{desc}</div>
      </div>
      <svg className="w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
    </a>
  );
}

function formatAgentName(name: string): string {
  return name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

function getAgentModel(name: string): string {
  const models: Record<string, string> = {
    transform_designer: 'Claude Opus',
    ai_router: 'Claude Sonnet',
    self_healer: 'Claude Sonnet',
    ops_agent: 'Claude Sonnet',
    anomaly_detector: 'Local ML',
  };
  return models[name] || 'Unknown';
}
