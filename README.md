# URL Shortener — Production Engineering Hackathon 2026

A production-hardened URL shortener built on Flask + Peewee + PostgreSQL.  
**Track: Reliability | Bronze → Gold**

---

## Quick Start (5 commands)

```bash
uv sync
createdb hackathon_db
cp .env.example .env
uv run seed.py
uv run run.py
```

Verify:
```bash
curl http://localhost:5000/health
# → {"status":"ok"}
```

---

## Environment Variables

All config lives in `.env`. Copy `.env.example` to get started.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | `postgresql://localhost/hackathon_db` | Full Postgres connection string |
| `FLASK_ENV` | No | `production` | Set to `development` for debug mode + auto-reload |
| `FLASK_SECRET_KEY` | No | `dev` | Secret key for Flask sessions — change in production |

Example `.env`:
```
DATABASE_URL=postgresql://postgres:password@localhost/hackathon_db
FLASK_ENV=development
FLASK_SECRET_KEY=change-me-in-production
```

---

## API Reference

### `GET /health`
Liveness check. Returns 200 if the service is up.
```json
{"status": "ok"}
```

### `GET /<short_code>`
Redirect to the original URL.
- `302` — redirect to original URL
- `410` — link exists but was deactivated
- `404` — unknown short code

```bash
curl -L http://localhost:5000/6eFfDh
# → redirects to https://acme.dev/rapid/quartz/1
```

### `GET /api/urls`
List all active URLs.
```json
[
  {
    "id": 1,
    "short_code": "6eFfDh",
    "original_url": "https://acme.dev/rapid/quartz/1",
    "title": "Alert feed kernel",
    "is_active": true,
    "created_at": "2025-03-03 16:12:57"
  }
]
```

### `GET /api/urls/<short_code>`
Get metadata for a single short code.
- `200` — returns URL object
- `404` — unknown short code

### `GET /api/stats`
Aggregate statistics across all URLs, users, and events.
```json
{
  "urls":    {"total": 2000, "active": 1847, "inactive": 153},
  "users":   {"total": 400},
  "events":  {"total": 3422, "by_type": {"created": 2000, "updated": 1200, "deleted": 222}},
  "top_urls": [{"short_code": "abc123", "title": "...", "event_count": 12}]
}
```

### `GET /api/metrics`
Prometheus-compatible plain-text metrics for monitoring tools.
```
# HELP urls_total Total number of shortened URLs
# TYPE urls_total gauge
urls_total 2000
# HELP urls_active Active shortened URLs
urls_active 1847
```

---

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage report
uv run pytest tests/ -v --cov=app --cov-report=term-missing
```

Current coverage: **97%**

---

## Deployment

### Local (development)
```bash
uv run run.py
```

### Production (gunicorn)
```bash
uv add gunicorn
uv run gunicorn "app:create_app()" --workers 4 --bind 0.0.0.0:5000
```

### Docker (optional)
```bash
docker build -t url-shortener .
docker run -e DATABASE_URL=postgresql://... -p 5000:5000 url-shortener
```

---

## Rollback Steps

If a deployment breaks the service:

```bash
# 1. Revert to last working commit
git log --oneline -5         # find the last good commit hash
git checkout <hash>          # check it out

# 2. Restart the server
pkill -f "run.py"
uv run run.py &

# 3. Verify
curl http://localhost:5000/health
```

If the database schema changed and needs reverting:
```bash
# Re-create tables from scratch (WARNING: deletes data)
uv run python -c "
from app import create_app
from app.database import db
from app.models import User, Url, Event
app = create_app()
with app.app_context():
    db.drop_tables([Event, Url, User])
    db.create_tables([User, Url, Event])
"
uv run seed.py   # re-seed from CSVs
```

---

## Architecture

```
Client
  │
  ▼
Flask App (run.py)
  │
  ├── GET /health          → liveness check
  ├── GET /<short_code>    → redirect engine
  ├── GET /api/urls        → URL listing
  ├── GET /api/stats       → aggregate stats
  └── GET /api/metrics     → Prometheus metrics
          │
          ▼
    Peewee ORM
          │
          ▼
    PostgreSQL
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  users   │  │   urls   │  │  events  │
    │ 400 rows │  │2000 rows │  │3422 rows │
    └──────────┘  └──────────┘  └──────────┘
```

See [DECISIONS.md](./DECISIONS.md) for why each technology was chosen.  
See [RUNBOOK.md](./RUNBOOK.md) for incident response procedures.

---

## CI/CD

Every push to `main` automatically:
1. Installs dependencies via `uv sync`
2. Runs the full test suite
3. Fails the build if coverage drops below 70%

CI config: `.github/workflows/ci.yml`