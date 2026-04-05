import pytest
from app import create_app
from app.database import db
from app.models import Event, Url, User


# Testing setup
@pytest.fixture(scope="session")
def app():
    """Create a test app backed by an in-memory SQLite database."""
    application = create_app(
        {
            "TESTING": True,
            "DATABASE": ":memory:",          
        }
    )
    with application.app_context():
        db.create_tables([User, Url, Event], safe=True)
        _seed()
        yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def _seed():
    """Insert minimal fixture data."""
    user = User.create(
        id=1,
        username="testuser",
        email="test@example.com",
        created_at="2025-01-01 00:00:00",
    )
    active_url = Url.create(
        id=1,
        user=user,
        short_code="abc123",
        original_url="https://example.com",
        title="Example",
        is_active=True,
        created_at="2025-01-01 00:00:00",
        updated_at="2025-01-01 00:00:00",
    )
    inactive_url = Url.create(
        id=2,
        user=user,
        short_code="dead99",
        original_url="https://gone.example.com",
        title="Gone",
        is_active=False,
        created_at="2025-01-01 00:00:00",
        updated_at="2025-01-02 00:00:00",
    )
    Event.create(
        id=1,
        url=active_url,
        user=user,
        event_type="created",
        timestamp="2025-01-01 00:00:00",
        details=None,
    )
    Event.create(
        id=2,
        url=inactive_url,
        user=user,
        event_type="deleted",
        timestamp="2025-01-02 00:00:00",
        details=None,
    )


# --- Bronze: basic health + redirect ---
class TestHealth:
    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_returns_ok(self, client):
        data = r = client.get("/health").get_json()
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


# --- Silver: API endpoints ---
class TestApiUrls:
    def test_list_urls_returns_only_active(self, client):
        r = client.get("/api/urls")
        assert r.status_code == 200
        data = r.get_json()
        assert all(u["is_active"] for u in data)

    def test_get_url_by_short_code(self, client):
        r = client.get("/api/urls/abc123")
        assert r.status_code == 200
        assert r.get_json()["original_url"] == "https://example.com"

    def test_get_url_missing_returns_404(self, client):
        r = client.get("/api/urls/nope")
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
        assert "urls_total" in r.data.decode()
        assert "urls_active" in r.data.decode()