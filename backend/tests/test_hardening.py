from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest

from app import main as main_module
from app.config import settings
from app.main import app
from app.services.rate_limit import RateLimiter
from app.services.store import TelemetryStore


client = TestClient(app)


def test_policy_patch_rejects_invalid_values_without_mutating_policy():
    created = client.post(
        '/api/v1/policies',
        json={
            'name': 'Temporary validation policy',
            'limit': 3,
            'window_seconds': 20,
            'path_pattern': '/api/v1/unused',
        },
    )
    assert created.status_code == 200
    policy_id = created.json()['id']

    try:
        invalid_update = client.patch(
            f'/api/v1/policies/{policy_id}',
            json={'limit': 'invalid'},
        )
        assert invalid_update.status_code == 422

        current = next(policy for policy in client.get('/api/v1/policies').json() if policy['id'] == policy_id)
        assert current['limit'] == 3
    finally:
        client.delete(f'/api/v1/policies/{policy_id}')


def test_forwarded_identity_uses_configured_trusted_proxy(monkeypatch):
    monkeypatch.setattr(settings, 'trusted_proxies', 'testclient')
    response = client.get(
        '/api/v1/demo',
        headers={'X-Forwarded-For': '203.0.113.8'},
    )

    assert response.status_code == 200
    assert response.json()['client'] == '203.0.113.8'


def test_cors_exposes_rate_limit_headers_to_frontend():
    response = client.get(
        '/api/v1/demo',
        headers={'Origin': 'http://localhost:5174'},
    )
    assert response.status_code in (200, 429)
    exposed = response.headers.get('access-control-expose-headers', '').lower()
    assert 'retry-after' in exposed
    assert 'x-ratelimit-limit' in exposed
    assert 'x-ratelimit-remaining' in exposed
    assert 'x-ratelimit-reset' in exposed


def test_requests_per_minute_is_a_real_rolling_count(monkeypatch):
    telemetry = TelemetryStore()
    timestamps = iter([0.0, 61.0, 61.0])
    monkeypatch.setattr('app.services.store.time.monotonic', lambda: next(timestamps))
    for index in range(2):
        telemetry.record(
            request_id=str(index),
            method='GET',
            endpoint='/test',
            client_id='client',
            status_code=200,
            allowed=True,
            latency_ms=1,
        )

    metrics = telemetry.get_metrics()
    assert metrics['total_requests'] == 2
    assert metrics['requests_per_minute'] == 1


def test_http_errors_are_not_reported_as_rate_limit_blocks(monkeypatch):
    telemetry = TelemetryStore()
    monkeypatch.setattr(main_module, 'telemetry_store', telemetry)

    missing = client.get('/does-not-exist')
    metrics = client.get('/api/v1/metrics').json()

    assert missing.status_code == 404
    assert metrics['total_requests'] == 1
    assert metrics['allowed_requests'] == 1
    assert metrics['blocked_requests'] == 0


def test_rate_limiter_concurrent_requests_do_not_exceed_limit():
    limiter = RateLimiter()
    with ThreadPoolExecutor(max_workers=32) as executor:
        decisions = list(
            executor.map(
                lambda _: limiter.check('same-client', 5, 60, 'fixed_window'),
                range(100),
            )
        )

    assert sum(decision.allowed for decision in decisions) == 5


@pytest.mark.parametrize('algorithm', ['fixed_window', 'sliding_window', 'token_bucket'])
def test_each_rate_limit_algorithm_enforces_limit_one(algorithm):
    limiter = RateLimiter()

    first = limiter.check('client-a', 1, 60, algorithm)
    second = limiter.check('client-a', 1, 60, algorithm)
    separate_client = limiter.check('client-b', 1, 60, algorithm)

    assert first.allowed is True
    assert first.remaining == 0
    assert second.allowed is False
    assert second.retry_after > 0
    assert separate_client.allowed is True
