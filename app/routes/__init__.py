from flask import Blueprint, jsonify, redirect, abort
from peewee import fn
from playhouse.shortcuts import model_to_dict

from app.models import Event, Url, User

# Blueprints setup
health_bp = Blueprint("health", __name__)
redirect_bp = Blueprint("redirect", __name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")


# Health check
@health_bp.route("/health")
def health():
    """Simple liveness check."""
    return jsonify({"status": "ok"})


# Redirect short code
@redirect_bp.route("/<short_code>")
def do_redirect(short_code):
    """
    Look up a short code and redirect.
    """
    try:
        url = Url.get(Url.short_code == short_code)
    except Url.DoesNotExist:
        abort(404)

    if not url.is_active:
        return jsonify({"error": "This link has been deactivated.", "short_code": short_code}), 410

    return redirect(url.original_url, code=302)


# API endpoints
@api_bp.route("/urls")
def list_urls():
    """Return all active URLs."""
    urls = Url.select().where(Url.is_active == True).order_by(Url.created_at.desc())
    return jsonify([model_to_dict(u) for u in urls])


@api_bp.route("/urls/<short_code>")
def get_url(short_code):
    """Return metadata for a single short code."""
    try:
        url = Url.get(Url.short_code == short_code)
    except Url.DoesNotExist:
        abort(404)
    
    if not url.is_active:
        return jsonify({
            "status": "error",
            "type": "URL_DEACTIVATED",
            "message": "This shortened link is no longer active.",
            "short_code": short_code,
            "recommendation": "Contact the link owner to reactivate this resource."
        }), 410
        
    return jsonify(model_to_dict(url))


# Statistics
@api_bp.route("/stats")
def stats():
    """Aggregate stats for the dashboard."""
    total_urls   = Url.select().count()
    active_urls  = Url.select().where(Url.is_active == True).count()
    total_users  = User.select().count()
    total_events = Event.select().count()

    # event breakdown by type
    event_counts = (
        Event
        .select(Event.event_type, fn.COUNT(Event.id).alias("count"))
        .group_by(Event.event_type)
    )
    events_by_type = {row.event_type: row.count for row in event_counts}

    # top 5 most-active URLs
    top_urls_q = (
        Event
        .select(Event.url, fn.COUNT(Event.id).alias("event_count"))
        .group_by(Event.url)
        .order_by(fn.COUNT(Event.id).desc())
        .limit(5)
    )
    top_urls = [
        {
            "short_code":  row.url.short_code,
            "title":       row.url.title,
            "event_count": row.event_count,
        }
        for row in top_urls_q
    ]

    return jsonify(
        {
            "urls":          {"total": total_urls, "active": active_urls, "inactive": total_urls - active_urls},
            "users":         {"total": total_users},
            "events":        {"total": total_events, "by_type": events_by_type},
            "top_urls":      top_urls,
        }
    )


# ── /api/metrics (Reliability gold tier) ─────────────────────────────────────

@api_bp.route("/metrics")
def metrics():
    """Prometheus-style plain-text metrics."""
    total   = Url.select().count()
    active  = Url.select().where(Url.is_active == True).count()
    users   = User.select().count()
    events  = Event.select().count()

    lines = [
        "# HELP urls_total Total number of shortened URLs",
        "# TYPE urls_total gauge",
        f"urls_total {total}",
        "# HELP urls_active Active shortened URLs",
        "# TYPE urls_active gauge",
        f"urls_active {active}",
        "# HELP users_total Registered users",
        "# TYPE users_total gauge",
        f"users_total {users}",
        "# HELP events_total Total link events",
        "# TYPE events_total gauge",
        f"events_total {events}",
    ]
    return "\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4"}


# ── registration helper ───────────────────────────────────────────────────────

def register_routes(app):
    app.register_blueprint(health_bp)
    app.register_blueprint(redirect_bp)
    app.register_blueprint(api_bp)