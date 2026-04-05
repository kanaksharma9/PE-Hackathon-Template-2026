"""
Reliability test suite — Bronze + Silver + Gold tier.

Run with:
    uv run pytest tests/ -v
    uv run pytest tests/ -v --cov=app --cov-report=term-missing
"""

import pytest
from app import create_app
from app.database import db
from app.models import Event, Url, User


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    application = create_app({"TESTING": True, "DATABASE": ":memory:"})
    with application.app_context():
        db.create_tables([User, Url, Event], safe=True)
        _seed()
        yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def _seed():
    user = User.create(
        id=1, username="testuser", email="test@example.com",
        created_at="2025-01-01 00:00:00",
    )
    active_url = Url.create(
        id=1, user=user, short_code="abc123",
        original_url="https://example.com", title="Example",
        is_active=True,
        created_at="2025-01-01 00:00:00",
        updated_at="2025-01-01 00:00:00",
    )
    inactive_url = Url.create(
        id=2, user=user, short_code="dead99",
        original_url="https://gone.example.com", title="Gone",
        is_active=False,
        created_at="2025-01-01 00:00:00",
        updated_at="2025-01-02 00:00:00",
    )
    Event.create(
        id=1, url=active_url, user=user, event_type="created",
        timestamp="2025-01-01 00:00:00", details=None,
    )
    Event.create(
        id=2, url=inactive_url, user=user, event_type="deleted",
        timestamp="2025-01-02 00:00:00", details=None,
    )


# ── Bronze: health + redirect ─────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_returns_ok(self, client):
        data = client.get("/health").get_json()
        assert data["status"] == "ok"


class TestRedirect:
    def test_active_short_code_redirects(self, client):
        r = client.get("/abc123")
        assert r.status_code == 302
        assert r.headers["Location"] == "https://example.com"

    def test_unknown_short_code_returns_404(self, client):
        r = client.get("/doesnotexist")
        assert r.status_code == 404

    def test_inactive_short_code_returns_410(self, client):
        r = client.get("/dead99")
        assert r.status_code == 410


# ── Silver: API endpoints ─────────────────────────────────────────────────────

class TestApiUrls:
    # your actual route is /urls, not /api/urls
    def test_list_urls_returns_200(self, client):
        r = client.get("/urls")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)

    def test_list_urls_active_filter(self, client):
        r = client.get("/urls?is_active=true")
        assert r.status_code == 200
        data = r.get_json()
        assert all(u["is_active"] for u in data)

    def test_get_url_by_id(self, client):
        r = client.get("/urls/1")
        assert r.status_code == 200
        assert r.get_json()["original_url"] == "https://example.com"

    def test_get_url_missing_returns_404(self, client):
        r = client.get("/urls/99999")
        assert r.status_code == 404


class TestStats:
    def test_stats_shape(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.get_json()
        assert "urls" in data
        assert "users" in data
        assert "events" in data
        assert "top_urls" in data

    def test_stats_counts(self, client):
        data = client.get("/api/stats").get_json()
        assert data["urls"]["total"] == 2
        assert data["urls"]["active"] == 1
        assert data["users"]["total"] == 1
        assert data["events"]["total"] == 2


class TestMetrics:
    def test_metrics_plain_text(self, client):
        r = client.get("/api/metrics")
        assert r.status_code == 200
        assert "text/plain" in r.content_type
        body = r.data.decode()
        assert "urls_total" in body
        assert "urls_active" in body


# ── Gold: error handlers ──────────────────────────────────────────────────────

class TestErrorHandlers:
    def test_404_returns_json(self, client):
        r = client.get("/no-such-route-xyz")
        assert r.status_code == 404
        data = r.get_json()
        assert data is not None
        assert "error" in data

    def test_inactive_url_returns_410_with_message(self, client):
        r = client.get("/dead99")
        assert r.status_code == 410
        data = r.get_json()
        assert "error" in data

    def test_db_error_returns_503(self, client):
        from unittest.mock import patch
        from peewee import OperationalError as PeeweeOpError
        with patch("app.models.Url.get", side_effect=PeeweeOpError("connection refused")):
            r = client.get("/abc123")
            assert r.status_code == 503
            data = r.get_json()
            assert data["status"] == 503
            assert "unavailable" in data["error"].lower()


# ── Users CRUD (bonus coverage) ───────────────────────────────────────────────

class TestUsers:
    def test_list_users(self, client):
        r = client.get("/users")
        assert r.status_code == 200
        assert len(r.get_json()) >= 1

    def test_get_user_by_id(self, client):
        r = client.get("/users/1")
        assert r.status_code == 200
        assert r.get_json()["username"] == "testuser"

    def test_get_missing_user_returns_404(self, client):
        r = client.get("/users/99999")
        assert r.status_code == 404

    def test_create_user(self, client):
        r = client.post("/users", json={"username": "newuser", "email": "new@example.com"})
        assert r.status_code == 201
        assert r.get_json()["username"] == "newuser"

    def test_create_user_missing_fields(self, client):
        r = client.post("/users", json={"username": "nomail"})
        assert r.status_code == 400


# ── Events (bonus coverage) ───────────────────────────────────────────────────

class TestEvents:
    def test_list_events(self, client):
        r = client.get("/events")
        assert r.status_code == 200
        assert len(r.get_json()) >= 1

    def test_filter_events_by_type(self, client):
        r = client.get("/events?event_type=created")
        assert r.status_code == 200
        data = r.get_json()
        assert all(e["event_type"] == "created" for e in data)

    def test_create_event(self, client):
        r = client.post("/events", json={"url_id": 1, "user_id": 1, "event_type": "updated"})
        assert r.status_code == 201


# ── Extra coverage: bulk routes ───────────────────────────────────────────────

class TestBulkRoutes:
    def test_bulk_users_no_file_returns_200(self, client):
        """When CSV not present, returns count of existing users."""
        r = client.post("/users/bulk", json={"file": "nonexistent.csv"})
        assert r.status_code == 200
        assert "loaded" in r.get_json()

    def test_bulk_urls_no_file_returns_200(self, client):
        r = client.post("/urls/bulk", json={"file": "nonexistent.csv"})
        assert r.status_code == 200
        assert "loaded" in r.get_json()

    def test_bulk_events_no_file_returns_200(self, client):
        r = client.post("/events/bulk", json={"file": "nonexistent.csv"})
        assert r.status_code == 200
        assert "loaded" in r.get_json()


# ── Extra coverage: URL CRUD ──────────────────────────────────────────────────

class TestUrlCrud:
    def test_create_url(self, client):
        r = client.post("/urls", json={"original_url": "https://test.com", "title": "Test"})
        assert r.status_code == 201
        data = r.get_json()
        assert data["original_url"] == "https://test.com"
        assert "short_code" in data

    def test_create_url_missing_field(self, client):
        r = client.post("/urls", json={"title": "no url"})
        assert r.status_code == 400

    def test_update_url(self, client):
        r = client.patch("/urls/1", json={"title": "Updated title"})
        assert r.status_code == 200
        assert r.get_json()["title"] == "Updated title"

    def test_update_url_missing(self, client):
        r = client.patch("/urls/99999", json={"title": "x"})
        assert r.status_code == 404

    def test_delete_url(self, client):
        # create one first so we don't break other tests
        created = client.post("/urls", json={"original_url": "https://delete-me.com"}).get_json()
        r = client.delete(f"/urls/{created['id']}")
        assert r.status_code == 200
        assert r.get_json()["deleted"] is True

    def test_delete_url_missing(self, client):
        r = client.delete("/urls/99999")
        assert r.status_code == 404


# ── Extra coverage: User CRUD ─────────────────────────────────────────────────

class TestUserCrud:
    def test_update_user(self, client):
        r = client.patch("/users/1", json={"username": "updated_user"})
        assert r.status_code == 200
        assert r.get_json()["username"] == "updated_user"

    def test_update_user_missing(self, client):
        r = client.patch("/users/99999", json={"username": "x"})
        assert r.status_code == 404

    def test_delete_user(self, client):
        created = client.post("/users", json={
            "username": "todelete", "email": "todelete@example.com"
        }).get_json()
        r = client.delete(f"/users/{created['id']}")
        assert r.status_code == 200
        assert r.get_json()["deleted"] is True

    def test_delete_user_missing(self, client):
        r = client.delete("/users/99999")
        assert r.status_code == 404

    def test_create_duplicate_email(self, client):
        client.post("/users", json={"username": "dupuser", "email": "dup@example.com"})
        r = client.post("/users", json={"username": "dupuser2", "email": "dup@example.com"})
        assert r.status_code == 409


# ── Extra coverage: Events CRUD ───────────────────────────────────────────────

class TestEventCrud:
    def test_get_event_by_id(self, client):
        r = client.get("/events/1")
        assert r.status_code == 200
        assert "event_type" in r.get_json()

    def test_get_event_missing(self, client):
        r = client.get("/events/99999")
        assert r.status_code == 404

    def test_filter_events_by_url(self, client):
        r = client.get("/events?url_id=1")
        assert r.status_code == 200

    def test_filter_events_by_user(self, client):
        r = client.get("/events?user_id=1")
        assert r.status_code == 200

    def test_create_event_missing_fields(self, client):
        r = client.post("/events", json={"event_type": "created"})
        assert r.status_code == 400

    def test_create_event_with_dict_details(self, client):
        r = client.post("/events", json={
            "url_id": 1, "user_id": 1,
            "event_type": "updated",
            "details": {"key": "value"}
        })
        assert r.status_code == 201