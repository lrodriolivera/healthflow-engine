'use client';

import { useEffect, useState } from 'react';

export default function SettingsPage() {
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    fetch('/health').then(r => r.json()).then(setHealth).catch(() => {});
  }, []);

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="text-sm text-slate-500 mt-1">System configuration and connection details</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Section title="Connection Status">
          <StatusRow label="Backend API" status={health?.status === 'ok'} detail="http://localhost:8000" />
          <StatusRow label="PostgreSQL + TimescaleDB" status={health?.database} detail="localhost:5434" />
          <StatusRow label="NATS JetStream" status={health?.nats} detail="localhost:4222" />
          <StatusRow label="Redis" status={health?.redis} detail="localhost:6380" />
          <StatusRow label="OpenTelemetry Collector" status={true} detail="localhost:4317" />
          <StatusRow label="Grafana" status={true} detail="localhost:3001" />
        </Section>

        <Section title="AI Configuration">
          <ConfigRow label="Provider" value="AWS Bedrock" />
          <ConfigRow label="Sonnet Model" value="claude-sonnet-4-6-20250514" />
          <ConfigRow label="Opus Model" value="claude-opus-4-6-20250514" />
          <ConfigRow label="Region" value="us-east-1" />
          <ConfigRow label="Agents Active" value={health?.agents?.length?.toString() || '0'} />
        </Section>

        <Section title="Healthcare Standards">
          <ConfigRow label="HL7 v2.x" value="2.3 — 2.8 (ER7 parser)" />
          <ConfigRow label="FHIR" value="R4 (4.0.1) + R5 Subscriptions" />
          <ConfigRow label="MLLP" value="VT/FS/CR framing, TLS optional" />
          <ConfigRow label="SOAP" value="Generic client, Basic Auth" />
          <ConfigRow label="IHE" value="ATNA audit trail" />
        </Section>

        <Section title="Endpoints">
          <ConfigRow label="REST API" value="/api/v1/*" />
          <ConfigRow label="FHIR Server" value="/fhir/*" />
          <ConfigRow label="MLLP" value="TCP :2575" />
          <ConfigRow label="OpenAPI Docs" value="/docs" />
          <ConfigRow label="Health Check" value="/health" />
          <ConfigRow label="SMART Config" value="/fhir/.well-known/smart-configuration" />
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
      <div className="px-5 py-4 border-b border-slate-100">
        <h3 className="font-semibold text-slate-900">{title}</h3>
      </div>
      <div className="divide-y divide-slate-50">{children}</div>
    </div>
  );
}

function StatusRow({ label, status, detail }: { label: string; status?: boolean; detail: string }) {
  return (
    <div className="px-5 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className={`w-2.5 h-2.5 rounded-full ${status ? 'bg-green-500' : status === false ? 'bg-red-400' : 'bg-slate-300'}`} />
        <span className="text-sm text-slate-700">{label}</span>
      </div>
      <span className="text-xs font-mono text-slate-400">{detail}</span>
    </div>
  );
}

function ConfigRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="px-5 py-3 flex items-center justify-between">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="text-sm font-medium text-slate-900">{value}</span>
    </div>
  );
}
