import pytest

from app import main as main_module
from app.services.rate_limit import RateLimiter
from app.services.store import PolicyStore, TelemetryStore


@pytest.fixture(autouse=True)
def isolate_application_state(monkeypatch):
    monkeypatch.setattr(main_module, 'policy_store', PolicyStore())
    monkeypatch.setattr(main_module, 'telemetry_store', TelemetryStore())
    monkeypatch.setattr(main_module, 'rate_limiter', RateLimiter())
