from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_demo_endpoint_enforces_rate_limit():
    for _ in range(5):
        response = client.get('/api/v1/demo')
        assert response.status_code == 200

    blocked = client.get('/api/v1/demo')
    assert blocked.status_code == 429
    assert 'Retry-After' in blocked.headers
    assert blocked.json()['error'] == 'rate_limit_exceeded'


def test_metrics_and_policies_endpoints():
    policies = client.get('/api/v1/policies')
    assert policies.status_code == 200
    assert isinstance(policies.json(), list)

    metrics = client.get('/api/v1/metrics')
    assert metrics.status_code == 200
    assert 'total_requests' in metrics.json()

    stats = client.get('/api/v1/stats')
    assert stats.status_code == 200
    assert 'total_requests' in stats.json()


def test_request_details_are_present():
    client.get('/health')
    response = client.get('/api/v1/requests')
    assert response.status_code == 200
    payload = response.json()
    assert 'items' in payload
    assert 'total' in payload

    first_request = payload['items'][0]
    detail = client.get(f"/api/v1/requests/{first_request['request_id']}")
    assert detail.status_code == 200
    assert detail.json()['request_id'] == first_request['request_id']
