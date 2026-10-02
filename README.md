# APIShield

APIShield is a lightweight API protection and request monitoring platform built to demonstrate backend engineering, rate limiting, observability, and modern developer tooling in a single portfolio project.

## Product focus

APIShield answers four practical questions for engineering teams:

- What is hitting my API?
- Who is making requests?
- Which requests are being blocked?
- What rate limit is active right now?

The project is intentionally focused on a realistic backend security workflow instead of a generic dashboard.

## Architecture

```text
Client
  ↓
APIShield middleware
  ↓
Client identification (IP / API key / client ID)
  ↓
Policy lookup
  ↓
Rate-limit strategy evaluation
  ↓
Allow or reject
  ↓
Telemetry capture
  ↓
Dashboard and request monitor
```

The repository is split into two main parts:

- backend/: FastAPI API, middleware, rate-limit logic, telemetry, tests
- frontend/: React + Vite dashboard and API playground

## Rate-limiting strategy

The backend supports multiple strategies behind a small interface:

- Fixed window
- Sliding window
- Token bucket

Sliding window is used as the default for the demo route because it is a strong production-relevant compromise between correctness and simplicity. The implementation is intentionally explicit and easy to reason about. Redis-ready design is supported, but local in-memory mode is the default for development and demos.

## Local development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

The frontend typically runs on http://localhost:5173 and calls the backend on http://localhost:8000.

## Environment variables

Use the backend `.env.example` file as a template:

```bash
cp .env.example .env
```

Key values:

- APP_NAME
- APP_ENV
- HOST
- PORT
- LOG_LEVEL
- RATE_LIMIT_MODE
- REDIS_URL
- TRUSTED_PROXIES
- DEMO_LIMIT
- DEMO_WINDOW_SECONDS

## Redis setup

Redis is optional for local development. The app defaults to in-memory local mode, which is useful for demos and testing.

For shared state and multi-instance deployments:

```bash
redis-server
```

Set `RATE_LIMIT_MODE=redis` and configure `REDIS_URL` accordingly.

## API endpoints

Core routes:

- GET /health
- GET /api/v1/demo
- GET /api/v1/stats
- GET /api/v1/metrics
- GET /api/v1/policies
- POST /api/v1/policies
- PATCH /api/v1/policies/{id}
- DELETE /api/v1/policies/{id}
- GET /api/v1/requests
- GET /api/v1/requests/{id}

Blocked requests return HTTP 429 with rate-limit headers:

- Retry-After
- X-RateLimit-Limit
- X-RateLimit-Remaining
- X-RateLimit-Reset

## Testing

```bash
cd backend
python -m pytest -q
```

The test suite validates:

- health endpoint
- rate-limit enforcement
- 429 responses
- headers
- metrics endpoint
- policies endpoint
- request list shape

## Load testing

The project includes a lightweight approach for local performance validation, but does not require a paid service. A local script can be added for k6 or Locust if needed.

## Security considerations

This implementation is security-conscious without pretending to be a full WAF or gateway. It focuses on:

- trusted proxy handling
- client IP extraction
- request metadata collection
- safe environment variable configuration
- input validation through Pydantic
- explicit rate-limit decisions
- no hard-coded secrets

## Design decisions

- FastAPI is used because it provides a clean, typed backend with good API documentation and excellent fit for a portfolio project.
- React + Vite is used for a fast dashboard and modern frontend workflow.
- Local in-memory limits are the default for simplicity and demo reliability.
- Redis is kept as an optional path for multi-instance deployment rather than being required for local development.
- The dashboard is intentionally focused on a small set of meaningful developer workflows rather than fake analytics.

## Limitations

This project demonstrates a production-oriented API protection flow, not a full enterprise gateway. It does not include advanced bot detection, WAF features, distributed tracing, or a full multi-tenant admin model.

## Future improvements

- Redis-backed distributed limiter
- per-route policy editor with validation
- richer client identity strategies
- benchmark scripts and k6 load tests
- structured JSON logging to a file or system sink
- deployment templates for Docker or cloud hosting

## License

This project is licensed under the MIT License.
