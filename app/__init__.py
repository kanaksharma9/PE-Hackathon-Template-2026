from dotenv import load_dotenv
from flask import Flask, jsonify
import peewee
import psycopg2

from app.database import init_db
from app.routes import register_routes


def create_app(test_config=None):
    load_dotenv()

    app = Flask(__name__)

    if test_config:
        app.config.from_mapping(test_config)

    init_db(app)

    @app.errorhandler(peewee.OperationalError)
    @app.errorhandler(psycopg2.OperationalError)
    def handle_database_connection_error(e):
        """Custom handler for database connection crashes."""
        return jsonify({
            "status": "error",
            "message": "The system is currently experiencing a connection issue with the database.",
            "details": "We have detected a PostgreSQL service failure. Our automated reliability protocols have been triggered.",
            "type": "DATABASE_CRASH",
            "recommendation": "Try again in 30 seconds as the service auto-recovers."
        }), 503

    from app import models  # noqa: F401 - registers models with Peewee

    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    return app
