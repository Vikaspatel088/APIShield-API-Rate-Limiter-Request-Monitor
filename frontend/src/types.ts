export type RequestItem = {
  request_id: string;
  timestamp: string;
  method: string;
  endpoint: string;
  client_id: string;
  status_code: number;
  allowed: boolean;
  latency_ms: number;
  policy_id?: string | null;
  rate_limit?: { [key: string]: unknown } | null;
};

export type MetricsResponse = {
  total_requests: number;
  allowed_requests: number;
  blocked_requests: number;
  success_rate: number;
  block_rate: number;
  requests_per_minute: number;
  active_clients: number;
  top_clients: Array<{ client_id: string; count: number }>;
  top_endpoints: Array<{ endpoint: string; count: number }>;
  status_distribution: Record<string, number>;
  recent_requests: RequestItem[];
};

export type PolicyItem = {
  id: string;
  name: string;
  description?: string | null;
  limit: number;
  window_seconds: number;
  algorithm: string;
  identity_type: string;
  path_pattern: string;
  action: string;
  enabled: boolean;
};
