const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// --- Health ---
export const getHealth = () => fetchAPI<{
  status: string; version: string; nats: boolean; redis: boolean; agents: string[];
}>('/health');

// --- Flows ---
export const getFlows = () => fetchAPI<{ id: string; name: string; is_active: boolean }[]>('/api/v1/flows');

// --- Routing ---
export const getRoutingRules = () => fetchAPI<any[]>('/api/v1/routing/rules');
export const testRouting = (message: string) =>
  fetchAPI<{ message_type: string; destinations: string[] }>('/api/v1/routing/test', {
    method: 'POST', body: JSON.stringify({ message }),
  });

// --- Transforms ---
export const getTransforms = () => fetchAPI<any[]>('/api/v1/transforms');

// --- Agents ---
export const getAgentStatus = () => fetchAPI<{ agents: string[]; bedrock: boolean }>('/api/v1/agents/status');
export const getAnomalies = () => fetchAPI<{ anomalies: any[] }>('/api/v1/agents/anomalies');
export const chatWithAgent = (message: string) =>
  fetchAPI<{ response: string }>('/api/v1/agents/chat', {
    method: 'POST', body: JSON.stringify({ message }),
  });

// --- Messages ---
export const parseHL7 = (message: string) =>
  fetchAPI<any>('/api/v1/messages/parse', {
    method: 'POST', body: JSON.stringify({ message }),
  });

// --- FHIR ---
export const convertToFHIR = (message: string) =>
  fetchAPI<any>('/fhir/$convert', {
    method: 'POST', body: JSON.stringify({ message }),
  });
