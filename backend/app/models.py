from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AlgorithmName = Literal['fixed_window', 'sliding_window', 'token_bucket']
IdentityType = Literal['ip', 'api_key', 'client_id']
ActionType = Literal['429']


class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    description: str | None = None
    limit: int = Field(..., gt=0, le=5000)
    window_seconds: int = Field(..., gt=0, le=86400)
    algorithm: AlgorithmName = 'sliding_window'
    identity_type: IdentityType = 'ip'
    path_pattern: str = '/api/v1/demo'
    action: ActionType = '429'
    enabled: bool = True


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = None
    limit: int | None = Field(default=None, gt=0, le=5000)
    window_seconds: int | None = Field(default=None, gt=0, le=86400)
    algorithm: AlgorithmName | None = None
    identity_type: IdentityType | None = None
    path_pattern: str | None = Field(default=None, min_length=1, max_length=200)
    action: ActionType | None = None
    enabled: bool | None = None

    @model_validator(mode='after')
    def validate_non_nullable_fields(self) -> 'PolicyUpdate':
        nullable_fields = {'description'}
        for field_name in self.model_fields_set - nullable_fields:
            if getattr(self, field_name) is None:
                raise ValueError(f'{field_name} cannot be null')
        if self.path_pattern is not None and not self.path_pattern.startswith('/'):
            raise ValueError('path_pattern must start with /')
        return self


class Policy(PolicyCreate):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RateLimitDecision(BaseModel):
    allowed: bool
    limit: int
    remaining: int
    retry_after: float = 0.0
    reset_at: float | None = None
    reason: str | None = None
    policy_id: str | None = None


class RequestSearchFilters(BaseModel):
    client_id: str | None = None
    status_code: int | None = None
    endpoint: str | None = None
    limit: int = 25


class RequestLogRecord(BaseModel):
    request_id: str
    timestamp: datetime
    method: str
    endpoint: str
    client_id: str
    status_code: int
    allowed: bool
    latency_ms: float
    policy_id: str | None = None
    rate_limit: dict[str, Any] | None = None
