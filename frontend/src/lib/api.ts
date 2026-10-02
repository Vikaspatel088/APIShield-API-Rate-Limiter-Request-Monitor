const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type DemoResponse = {
  status: number;
  latency_ms: number;
  headers: Record<string, string>;
  message?: string;
  client?: string;
  request_id?: string;
  rate_limit?: { limit: number; remaining: number; reset_after: number };
  retry_after?: number;
  error?: string;
};

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Backend returned HTTP ${response.status} for ${path}`);
  }
  return response.json() as Promise<T>;
}

export async function invokeDemo(): Promise<DemoResponse> {
  const startedAt = performance.now();
  const response = await fetch(`${API_BASE_URL}/api/v1/demo`);
  const payload = await response.json() as Omit<DemoResponse, 'status' | 'latency_ms' | 'headers'>;
  return {
    ...payload,
    status: response.status,
    latency_ms: Math.round(performance.now() - startedAt),
    headers: Object.fromEntries(response.headers.entries()),
  };
}
