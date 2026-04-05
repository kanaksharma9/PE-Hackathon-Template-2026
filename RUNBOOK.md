# URL Shortener — Runbook

> **Hackathon:** Production Engineering Hackathon 2026  
> **Track:** Reliability  

---

## Service Overview

A Flask + Peewee + PostgreSQL URL shortener.  
Short codes redirect users to original URLs and every action is logged as an event.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness check |
| `GET /<short_code>` | Redirect to original URL |
| `GET /api/urls` | List active URLs |
| `GET /api/stats` | Aggregate statistics |
| `GET /api/metrics` | Prometheus-style metrics |

---

## Starting the Service

```bash
uv sync
cp .env.example .env   # set DATABASE_URL
uv run seed.py         # load CSV data
uv run run.py          # starts on port 5000
```

Verify:
```bash
curl http://localhost:5000/health
# → {"status":"ok"}
```

---

## Runbook: Database is Down

**Symptoms:** All endpoints return 500, logs show `OperationalError`.

**Steps:**
1. Check DB is running: `pg_isready -h localhost -p 5432`
2. If not: `sudo systemctl start postgresql`
3. Verify `DATABASE_URL` in `.env` is correct
4. Restart the app: `uv run run.py`
5. Confirm recovery: `curl /health`

---

## Runbook: Short Code Returns 404

**Symptoms:** A user reports a link is broken.

**Steps:**
1. Check the URL exists in DB:
   ```sql
   SELECT * FROM urls WHERE short_code = '<code>';
   ```
2. If `is_active = false` → the link was deactivated (returns 410, expected).
3. If row is missing → it was never seeded. Re-run: `uv run seed.py`

---

## Runbook: Service is Slow

**Symptoms:** Redirects taking >500ms.

**Steps:**
1. Check `/api/metrics` for high event/URL counts
2. Ensure index exists on `short_code`:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_urls_short_code ON urls(short_code);
   ```
3. Restart app to clear any connection leaks

---

## Running Tests

```bash
uv run pytest tests/ -v
```

All tests use an in-memory SQLite DB — no Postgres needed to run the test suite.

---

## Deploying

```bash
git push origin main   # CI runs tests automatically
```

If CI is green, the service is safe to deploy.