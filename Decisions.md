# Technical Decisions & Capacity Notes

## Why Flask + Peewee + PostgreSQL

**Flask** was chosen over FastAPI because the hackathon template uses it and our focus was reliability over raw performance. Flask's simplicity means fewer moving parts to break in production.

**Peewee ORM** was chosen over raw SQL because it lets us write safe, parameterised queries by default — no SQL injection risk on the short code lookup path, which is the most-hit endpoint.

**PostgreSQL** was chosen over SQLite for production realism. SQLite cannot handle concurrent writes, which would silently corrupt data under load. PostgreSQL handles thousands of concurrent connections safely.

---

## Why 410 Gone instead of 404 for inactive URLs

A `404 Not Found` means "this resource never existed." A `410 Gone` means "this resource existed and was intentionally removed."

For a URL shortener, the distinction matters:
- Search engines de-index 410 pages faster than 404 pages
- API clients can distinguish "wrong link" from "link was deleted"
- It's more honest — we have the record, we're choosing not to serve it

---

## Why short codes are stored as-is (case sensitive)

Short codes like `6eFfDh` and `6eFfdh` are treated as different URLs. This maximises the keyspace — a 6-character alphanumeric code gives 62^6 = ~56 billion possible codes case-sensitive vs ~2 billion case-insensitive. We keep case sensitivity to stay in line with industry standard URL shorteners (bit.ly, tinyurl).

---

## Why tests use SQLite in-memory instead of PostgreSQL

Running tests against a real PostgreSQL instance requires the database to be running, seeded, and cleaned between runs. This breaks CI on first clone.

SQLite in-memory gives us:
- Zero setup — tests run on any machine with no dependencies
- Full isolation — each test session gets a fresh database
- Fast — no disk I/O

The trade-off: SQLite and PostgreSQL have minor dialect differences. We accept this risk because our queries are simple (no JSON operators, no CTEs, no window functions).

---

## Why /api/metrics returns plain text not JSON

Prometheus — the industry-standard metrics scraper — expects `text/plain` in a specific format. Returning JSON would mean this endpoint is incompatible with every monitoring tool out of the box. We follow the Prometheus exposition format so the endpoint works with Grafana, Datadog, and any other scraper without any adapter code.

---

## Capacity Assumptions & Known Limits

| Assumption | Value | Reasoning |
|---|---|---|
| Max short code length | 16 chars | Covers all realistic generated codes with room for custom slugs |
| Max original URL length | No hard limit (TEXT) | PostgreSQL TEXT is unlimited; application layer should add validation |
| Expected read:write ratio | ~100:1 | Redirects vastly outnumber link creation in any real shortener |
| DB connection pool | Peewee default (1 conn) | Sufficient for hackathon; production would use pgBouncer |
| Estimated max RPS (single instance) | ~500 req/s | Flask dev server; gunicorn with 4 workers would reach ~2000 req/s |

### Known Bottlenecks

1. **No caching** — every redirect hits PostgreSQL. Under heavy load, adding Redis in front of `Url.get(short_code=...)` would reduce DB load by ~90% since redirect targets rarely change.

2. **Single DB instance** — no read replicas. All reads and writes go to one Postgres node. For high availability, add a read replica and route `SELECT` queries there.

3. **No index on short_code explicitly declared** — Peewee creates a unique index automatically from `unique=True`, but this should be verified in production with `\d urls` in psql.

4. **No rate limiting** — a single client could flood the redirect endpoint. In production, add nginx rate limiting or a token bucket at the application layer.

---

## What We Would Do With More Time

- Add Redis caching on the redirect path
- Add gunicorn + nginx in front of Flask
- Add structured JSON logging with request IDs for tracing
- Add a `/admin` dashboard showing real-time stats
- Add rate limiting on the redirect endpoint
