from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock
import time
from typing import Any
from uuid import uuid4

from app.models import Policy, PolicyCreate


class PolicyStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._policies: dict[str, dict[str, Any]] = {}
        self.seed_default_policies()

    def seed_default_policies(self) -> None:
        default_policy = {
            'id': 'policy_demo',
            'name': 'Public API',
            'description': 'Default rate limit for demo traffic.',
            'limit': 5,
            'window_seconds': 20,
            'algorithm': 'sliding_window',
            'identity_type': 'ip',
            'path_pattern': '/api/v1/demo',
            'action': '429',
            'enabled': True,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        self._policies[default_policy['id']] = default_policy

    def list_policies(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(policy) for policy in self._policies.values()]

    def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        with self._lock:
            policy = self._policies.get(policy_id)
            return dict(policy) if policy else None

    def get_active_policy_for_path(self, path: str, client_id: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            for policy in self._policies.values():
                if policy.get('enabled') and path.startswith(policy.get('path_pattern', '')):
                    return dict(policy)
        return None

    def create_policy(self, payload: PolicyCreate) -> dict[str, Any]:
        new_id = f"policy_{uuid4().hex[:8]}"
        policy = {
            'id': new_id,
            'name': payload.name,
            'description': payload.description,
            'limit': payload.limit,
            'window_seconds': payload.window_seconds,
            'algorithm': payload.algorithm,
            'identity_type': payload.identity_type,
            'path_pattern': payload.path_pattern,
            'action': payload.action,
            'enabled': payload.enabled,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._policies[new_id] = policy
        return dict(policy)

    def update_policy(self, policy_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        allowed_fields = {
            'name', 'description', 'limit', 'window_seconds', 'algorithm',
            'identity_type', 'path_pattern', 'action', 'enabled',
        }
        with self._lock:
            existing = self._policies.get(policy_id)
            if not existing:
                return None
            for field_name, value in payload.items():
                if field_name in allowed_fields:
                    existing[field_name] = value
            existing['updated_at'] = datetime.now(timezone.utc).isoformat()
            return dict(existing)

    def delete_policy(self, policy_id: str) -> bool:
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                return True
            return False


class TelemetryStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: deque[dict[str, Any]] = deque(maxlen=250)
        self._stats = {
            'total_requests': 0,
            'allowed_requests': 0,
            'blocked_requests': 0,
        }
        self._status_counts: defaultdict[str, int] = defaultdict(int)
        self._endpoint_counts: defaultdict[str, int] = defaultdict(int)
        self._client_counts: defaultdict[str, int] = defaultdict(int)
        self._request_times: deque[float] = deque()

    def record(self, request_id: str, method: str, endpoint: str, client_id: str, status_code: int, allowed: bool, latency_ms: float, policy_id: str | None = None, rate_limit: dict[str, Any] | None = None) -> dict[str, Any]:
        recorded_monotonic = time.monotonic()
        item = {
            'request_id': request_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'method': method,
            'endpoint': endpoint,
            'client_id': client_id,
            'status_code': status_code,
            'allowed': allowed,
            'latency_ms': round(latency_ms, 2),
            'policy_id': policy_id,
            'rate_limit': rate_limit,
        }
        with self._lock:
            self._requests.append(item)
            self._request_times.append(recorded_monotonic)
            while self._request_times and self._request_times[0] <= recorded_monotonic - 60:
                self._request_times.popleft()
            self._stats['total_requests'] += 1
            if allowed:
                self._stats['allowed_requests'] += 1
            else:
                self._stats['blocked_requests'] += 1
            self._status_counts[str(status_code)] += 1
            self._endpoint_counts[endpoint] += 1
            self._client_counts[client_id] += 1
        return item

    def get_recent_requests(self, limit: int = 25) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._requests)[-limit:]

    def get_metrics(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            while self._request_times and self._request_times[0] <= now - 60:
                self._request_times.popleft()
            stats = dict(self._stats)
            status_counts = dict(self._status_counts)
            endpoint_counts = dict(self._endpoint_counts)
            client_counts = dict(self._client_counts)
            recent_requests = list(self._requests)[-10:]
            requests_per_minute = len(self._request_times)

        total_requests = stats['total_requests']
        allowed_requests = stats['allowed_requests']
        blocked_requests = stats['blocked_requests']
        success_rate = round((allowed_requests / total_requests) * 100, 2) if total_requests else 0.0
        block_rate = round((blocked_requests / total_requests) * 100, 2) if total_requests else 0.0
        top_clients = [
            {'client_id': client_id, 'count': count}
            for client_id, count in sorted(client_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        ]
        top_endpoints = [
            {'endpoint': endpoint, 'count': count}
            for endpoint, count in sorted(endpoint_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        ]
        status_distribution = {
            key: value for key, value in sorted(status_counts.items(), key=lambda kv: kv[0])
        }
        return {
            'total_requests': total_requests,
            'allowed_requests': allowed_requests,
            'blocked_requests': blocked_requests,
            'success_rate': success_rate,
            'block_rate': block_rate,
            'requests_per_minute': requests_per_minute,
            'active_clients': len(client_counts),
            'top_clients': top_clients,
            'top_endpoints': top_endpoints,
            'status_distribution': status_distribution,
            'recent_requests': recent_requests,
        }


policy_store = PolicyStore()
telemetry_store = TelemetryStore()
