import { useEffect, useMemo, useState } from 'react';
import { fetchJson, invokeDemo, type DemoResponse } from './lib/api';
import type { MetricsResponse, PolicyItem, RequestItem } from './types';

const navItems = ['Overview', 'Requests', 'Policies', 'Clients', 'Metrics', 'Settings'];
type HealthResponse = { status: string; service: string };

function App() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [policies, setPolicies] = useState<PolicyItem[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [selectedTab, setSelectedTab] = useState('Overview');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [playgroundState, setPlaygroundState] = useState<DemoResponse | null>(null);
  const [playgroundLoading, setPlaygroundLoading] = useState(false);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;

    const load = async () => {
      try {
        const [healthResponse, metricsResponse, requestResponse, policyResponse] = await Promise.all([
          fetchJson<HealthResponse>('/health'),
          fetchJson<MetricsResponse>('/api/v1/metrics'),
          fetchJson<{ items: RequestItem[]; total: number }>('/api/v1/requests?limit=10'),
          fetchJson<PolicyItem[]>('/api/v1/policies'),
        ]);
        if (!active) return;
        setHealth(healthResponse);
        setMetrics(metricsResponse);
        setRequests(requestResponse.items);
        setPolicies(policyResponse);
        setLoadError(null);
      } catch {
        if (active) {
          setHealth(null);
          setLoadError('The APIShield backend could not be reached. Check that it is running, then retry.');
        }
      } finally {
        if (active) {
          setLoading(false);
          timer = window.setTimeout(() => void load(), 15000);
        }
      }
    };

    void load();
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [refreshKey]);

  const summaryCards = useMemo(() => {
    if (!metrics) return [];
    return [
      { label: 'Total Requests', value: metrics.total_requests.toLocaleString() },
      { label: 'Blocked', value: metrics.blocked_requests.toLocaleString() },
      { label: 'Block Rate', value: `${metrics.block_rate}%` },
      { label: 'Active Clients', value: metrics.active_clients.toString() },
    ];
  }, [metrics]);

  const handleDemoRequest = async () => {
    setPlaygroundLoading(true);
    try {
      const response = await invokeDemo();
      setPlaygroundState(response);
    } catch {
      setPlaygroundState({
        status: 0,
        latency_ms: 0,
        headers: {},
        error: 'The demo request could not reach the APIShield backend.',
      });
    } finally {
      setPlaygroundLoading(false);
    }
  };

  const retryDashboard = () => {
    setLoading(true);
    setRefreshKey((current) => current + 1);
  };

  const renderOverview = () => (
    <div className="content-grid">
      <div className="panel span-2">
        <div className="panel-header">
          <div>
            <p className="eyebrow">System status</p>
            <h3>{health?.status === 'ok' ? 'Operational' : 'Unavailable'}</h3>
          </div>
          <span className={`status-pill ${health?.status === 'ok' ? 'success' : 'danger'}`}>
            {health?.status === 'ok' ? 'Healthy' : 'Unavailable'}
          </span>
        </div>
        <div className="metrics-grid">
          {summaryCards.map((card) => (
            <div key={card.label} className="metric-card">
              <span>{card.label}</span>
              <strong>{card.value}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Rate limit activity</p>
            <h3>Traffic mix</h3>
          </div>
        </div>
        <div className="bars">
          <div className="bars-row">
            <span>Allowed</span>
            <div className="bar-track">
              <div className="bar allowed" style={{ width: `${Math.max(10, metrics?.success_rate ?? 0)}%` }} />
            </div>
            <strong>{metrics?.success_rate ?? 0}%</strong>
          </div>
          <div className="bars-row">
            <span>Blocked</span>
            <div className="bar-track">
              <div className="bar blocked" style={{ width: `${metrics?.block_rate ?? 0}%` }} />
            </div>
            <strong>{metrics?.block_rate ?? 0}%</strong>
          </div>
        </div>
      </div>

      <div className="panel span-2">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Recent requests</p>
            <h3>Latest traffic</h3>
          </div>
        </div>
        <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Method</th>
              <th>Endpoint</th>
              <th>Status</th>
              <th>Client</th>
            </tr>
          </thead>
          <tbody>
            {requests.map((request) => (
              <tr key={request.request_id}>
                <td>{new Date(request.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                <td>{request.method}</td>
                <td>{request.endpoint}</td>
                <td><span className={request.allowed ? 'status-pill success' : 'status-pill danger'}>{request.status_code}</span></td>
                <td>{request.client_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  );

  const renderRequests = () => (
    <div className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Request monitor</p>
          <h3>Live traffic</h3>
        </div>
      </div>
      <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Request</th>
            <th>Endpoint</th>
            <th>Client</th>
            <th>Latency</th>
            <th>Allowed</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((request) => (
            <tr key={request.request_id}>
              <td>{request.request_id.slice(0, 8)}</td>
              <td>{request.endpoint}</td>
              <td>{request.client_id}</td>
              <td>{request.latency_ms.toFixed(1)} ms</td>
              <td><span className={request.allowed ? 'status-pill success' : 'status-pill danger'}>{request.allowed ? 'Allowed' : 'Blocked'}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );

  const renderPolicies = () => (
    <div className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Policy configuration</p>
          <h3>Active policies</h3>
        </div>
      </div>
      <div className="policy-list">
        {policies.map((policy) => (
          <div key={policy.id} className="policy-card">
            <div>
              <h4>{policy.name}</h4>
              <p>{policy.description || 'Service policy'}</p>
            </div>
            <ul>
              <li>Limit: {policy.limit}</li>
              <li>Window: {policy.window_seconds}s</li>
              <li>Algorithm: {policy.algorithm}</li>
              <li>Identity: {policy.identity_type}</li>
            </ul>
          </div>
        ))}
      </div>
    </div>
  );

  const renderClients = () => (
    <div className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Top clients</p>
          <h3>Traffic distribution</h3>
        </div>
      </div>
      <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Client</th>
            <th>Request count</th>
          </tr>
        </thead>
        <tbody>
          {(metrics?.top_clients ?? []).map((client) => (
            <tr key={client.client_id}>
              <td>{client.client_id}</td>
              <td>{client.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );

  const renderMetrics = () => (
    <div className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Observability</p>
          <h3>Request metrics</h3>
        </div>
      </div>
      <div className="stats-grid">
        {metrics && (
          <>
            <div><span>Requests / minute</span><strong>{metrics.requests_per_minute}</strong></div>
            <div><span>Success rate</span><strong>{metrics.success_rate}%</strong></div>
            <div><span>Block rate</span><strong>{metrics.block_rate}%</strong></div>
            <div><span>Active clients</span><strong>{metrics.active_clients}</strong></div>
          </>
        )}
      </div>
    </div>
  );

  const renderSettings = () => (
    <div className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Config</p>
          <h3>Runtime settings</h3>
        </div>
      </div>
      <div className="settings-box">
        <p>Default local mode is active.</p>
        <p>Trusted proxy list and limit windows are configured in the backend.</p>
      </div>
    </div>
  );

  const contentMap: Record<string, JSX.Element> = {
    Overview: renderOverview(),
    Requests: renderRequests(),
    Policies: renderPolicies(),
    Clients: renderClients(),
    Metrics: renderMetrics(),
    Settings: renderSettings(),
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">A</div>
          <div>
            <strong>APIShield</strong>
            <small>Protect your APIs</small>
          </div>
        </div>

        <nav className="nav">
          {navItems.map((item) => (
            <button
              key={item}
              className={selectedTab === item ? 'nav-item active' : 'nav-item'}
              aria-pressed={selectedTab === item}
              onClick={() => setSelectedTab(item)}
            >
              {item}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">Developer security</p>
            <h1>Traffic overview</h1>
          </div>
          <button className="primary-button" onClick={handleDemoRequest} disabled={playgroundLoading}>
            {playgroundLoading ? 'Sending...' : 'Send demo request'}
          </button>
        </header>

        {loading ? (
          <div className="loading-panel" role="status">Loading APIShield telemetry...</div>
        ) : metrics ? (
          <>
            {loadError && (
              <div className="notice error" role="alert">
                <span>Live data is stale. The backend could not be reached.</span>
                <button onClick={retryDashboard}>Retry</button>
              </div>
            )}
            {contentMap[selectedTab]}
          </>
        ) : (
          <section className="panel recovery-panel" role="alert">
            <h2>APIShield backend unavailable</h2>
            <p>{loadError ?? 'Dashboard data is not available.'}</p>
            <button className="primary-button" onClick={retryDashboard}>Retry connection</button>
          </section>
        )}

        <div className="panel playground-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">API playground</p>
              <h3>Demo endpoint tester</h3>
            </div>
          </div>
          {playgroundState ? (
            <div className="playground-result">
              <div className="playground-row"><span>Status</span><strong className={playgroundState.status === 429 || playgroundState.status === 0 ? 'danger-text' : ''}>{playgroundState.status}</strong></div>
              <div className="playground-row"><span>Latency</span><strong>{playgroundState.latency_ms} ms</strong></div>
              <div className="playground-row"><span>Request ID</span><strong>{playgroundState.request_id ?? '—'}</strong></div>
              <div className="playground-row"><span>Client</span><strong>{playgroundState.client ?? '—'}</strong></div>
              <div className="playground-row"><span>Rate limit</span><strong>{playgroundState.rate_limit?.limit ?? '—'}</strong></div>
              <div className="playground-row"><span>Remaining</span><strong>{playgroundState.rate_limit?.remaining ?? '—'}</strong></div>
              <div className="playground-row"><span>Retry after</span><strong>{playgroundState.headers['retry-after'] ? `${playgroundState.headers['retry-after']}s` : '—'}</strong></div>
              <div className="playground-row"><span>Message</span><strong>{playgroundState.message ?? playgroundState.error ?? '—'}</strong></div>
            </div>
          ) : (
            <p className="muted">Send a request to inspect rate-limit headers and telemetry.</p>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
