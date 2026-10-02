from __future__ import annotations

import ipaddress
import time
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import PolicyCreate, PolicyUpdate
from app.services.rate_limit import RateLimiter
from app.services.store import policy_store, telemetry_store

app = FastAPI(
    title='APIShield',
    version='0.1.0',
    description='Rate limiting and request monitoring API.',
    docs_url='/docs',
    redoc_url='/redoc',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
    expose_headers=['Retry-After', 'X-RateLimit-Limit', 'X-RateLimit-Remaining', 'X-RateLimit-Reset'],
)

rate_limiter = RateLimiter()


def resolve_client_id(peer_ip: str, forwarded_for: str | None, trusted_proxies: list[str]) -> str:
    if not forwarded_for:
        return peer_ip

    def is_trusted(address: str) -> bool:
        for proxy in trusted_proxies:
            try:
                if '/' in proxy:
                    if ipaddress.ip_address(address) in ipaddress.ip_network(proxy, strict=False):
                        return True
                elif ipaddress.ip_address(address) == ipaddress.ip_address(proxy):
                    return True
            except ValueError:
                if address.lower() == proxy.lower():
                    return True
        return False

    client_ip = peer_ip
    for forwarded_ip in reversed([part.strip() for part in forwarded_for.split(',') if part.strip()]):
        if not is_trusted(client_ip):
            break
        try:
            ipaddress.ip_address(forwarded_ip)
        except ValueError:
            break
        client_ip = forwarded_ip
    return client_ip


@app.middleware('http')
async def request_monitoring_middleware(request: Request, call_next):
    start = time.perf_counter()
    request_id = str(uuid4())
    request.state.request_id = request_id
    client_ip = request.client.host if request.client else 'unknown'
    client_ip = resolve_client_id(
        client_ip,
        request.headers.get('x-forwarded-for'),
        settings.trusted_proxy_list,
    )
    request.state.client_id = client_ip
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    status_code = getattr(response, 'status_code', 500)
    endpoint = request.url.path
    allowed = status_code != 429
    telemetry_store.record(
        request_id=request_id,
        method=request.method,
        endpoint=endpoint,
        client_id=client_ip,
        status_code=status_code,
        allowed=allowed,
        latency_ms=duration_ms,
    )
    return response


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok', 'service': settings.app_name}


@app.get('/api/v1/demo')
def demo_endpoint(request: Request):
    client_id = request.state.client_id
    policy = policy_store.get_active_policy_for_path('/api/v1/demo') or {'limit': settings.demo_limit, 'window_seconds': settings.demo_window_seconds, 'algorithm': 'sliding_window'}
    decision = rate_limiter.check(client_id, policy['limit'], policy['window_seconds'], policy['algorithm'])

    if not decision.allowed:
        retry_after_seconds = max(1, int(decision.retry_after))
        response = JSONResponse(
            status_code=429,
            content={'error': 'rate_limit_exceeded', 'message': 'Rate limit exceeded. Retry later.', 'retry_after': retry_after_seconds},
        )
        response.headers['Retry-After'] = str(retry_after_seconds)
        response.headers['X-RateLimit-Limit'] = str(policy['limit'])
        response.headers['X-RateLimit-Remaining'] = '0'
        response.headers['X-RateLimit-Reset'] = str(int(time.time() + max(decision.retry_after, 1)))
        return response

    response = JSONResponse(
        status_code=200,
        content={
            'message': 'Request allowed',
            'client': client_id,
            'request_id': request.state.request_id,
            'rate_limit': {
                'limit': policy['limit'],
                'remaining': decision.remaining,
                'reset_after': round(decision.retry_after, 2),
            },
        },
    )
    response.headers['X-RateLimit-Limit'] = str(policy['limit'])
    response.headers['X-RateLimit-Remaining'] = str(decision.remaining)
    response.headers['X-RateLimit-Reset'] = str(int(time.time() + max(decision.retry_after, 1)))
    return response


@app.get('/api/v1/requests')
def get_requests(limit: int = Query(25, ge=1, le=100)):
    items = telemetry_store.get_recent_requests(limit)
    return {'items': items, 'total': len(items)}


@app.get('/api/v1/requests/{request_id}')
def get_request_details(request_id: str):
    for item in reversed(telemetry_store.get_recent_requests(250)):
        if item['request_id'] == request_id:
            return item
    raise HTTPException(status_code=404, detail='Request not found')


@app.get('/api/v1/metrics')
def get_metrics():
    return telemetry_store.get_metrics()


@app.get('/api/v1/stats')
def get_stats():
    return telemetry_store.get_metrics()


@app.get('/api/v1/policies')
def list_policies():
    return policy_store.list_policies()


@app.post('/api/v1/policies')
def create_policy(payload: PolicyCreate):
    policy = policy_store.create_policy(payload)
    return policy


@app.patch('/api/v1/policies/{policy_id}')
def update_policy(policy_id: str, payload: PolicyUpdate):
    updated = policy_store.update_policy(policy_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail='Policy not found')
    return updated


@app.delete('/api/v1/policies/{policy_id}')
def delete_policy(policy_id: str):
    deleted = policy_store.delete_policy(policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail='Policy not found')
    return {'deleted': True, 'policy_id': policy_id}
