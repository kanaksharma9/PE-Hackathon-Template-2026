import os
from flask import Flask, jsonify
from dotenv import load_dotenv
from peewee import OperationalError, DatabaseError
from app.database import db


def create_app(config=None):
    load_dotenv()  # Load environment variables from .env
    app = Flask(__name__)

    if config:
        app.config.update(config)

    from app.database import init_db
    init_db(app)

    from app.models import User, Url, Event  
    with app.app_context():
        from app.database import db
        db.create_tables([User, Url, Event], safe=True)

    from app.routes import register_routes
    register_routes(app)

    # ── global error handlers ─────────────────────────────────────────────────

    @app.errorhandler(OperationalError)
    @app.errorhandler(DatabaseError)
    def handle_db_error(e):
        """Postgres is down -> clean 503 instead of ugly 500."""
        return jsonify({
            "error": "Service temporarily unavailable",
            "detail": "Database connection failed. Please retry in a moment.",
            "status": 503
        }), 503

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({"error": "Not found", "status": 404}), 404

    @app.errorhandler(410)
    def handle_410(e):
        return jsonify({"error": "Gone - this link has been deactivated", "status": 410}), 410

    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({
            "error": "Internal server error",
            "detail": str(e),
            "status": 500
        }), 500

    return app