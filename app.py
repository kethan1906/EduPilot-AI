import logging

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
from werkzeug.exceptions import HTTPException

load_dotenv()

from config import ConfigError, get_max_upload_bytes  # noqa: E402
from exceptions import EduPilotError  # noqa: E402
from routes.api import api  # noqa: E402

logger = logging.getLogger("edupilot")


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = get_max_upload_bytes()
    app.register_blueprint(api, url_prefix="/api")

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.errorhandler(ConfigError)
    def handle_config_error(exc):
        return jsonify({"error": str(exc)}), 503

    @app.errorhandler(EduPilotError)
    def handle_app_error(exc):
        logger.warning("%s: %s", type(exc).__name__, exc)
        return jsonify({"error": str(exc)}), exc.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        return jsonify({"error": exc.description}), exc.code

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        logger.exception("Unhandled error")
        if type(exc).__module__.startswith("pymongo"):
            return jsonify({"error": "Database error. Please try again."}), 503
        return jsonify({"error": "Internal server error"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    import os
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
