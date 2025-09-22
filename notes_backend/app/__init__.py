import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_smorest import Api

# Load dotenv if present to allow local development
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from .routes.health import blp as health_blp
from .routes.notes import blp as notes_blp
from .routes.taxonomy import blp as taxonomy_blp
from .models import db

app = Flask(__name__)
app.url_map.strict_slashes = False

# CORS: allow all origins for demo; adjust in production
CORS(app, resources={r"/*": {"origins": "*"}})

# Database configuration (SQLite by default)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///notes.db")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Ocean Professional API metadata and OpenAPI config
app.config["API_TITLE"] = "Secure Notes API"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = "/docs"
app.config["OPENAPI_SWAGGER_UI_PATH"] = ""
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

# Tag grouping with theme hint
app.config["OPENAPI_TAGS"] = [
    {"name": "Health Check", "description": "Health check route"},
    {"name": "Notes", "description": "Secure notes endpoints (Ocean Professional theme)"},
    {"name": "Folders", "description": "Manage folders to organize notes"},
    {"name": "Tags", "description": "Manage tags/labels for notes"},
]

# Initialize DB
db.init_app(app)
with app.app_context():
    db.create_all()

api = Api(app)
api.register_blueprint(health_blp)
api.register_blueprint(notes_blp)
api.register_blueprint(taxonomy_blp)


# PUBLIC_INTERFACE
@app.get("/docs/help")
def api_help():
    """Provide quick usage instructions for the API and WebSocket (if any).

    Returns:
        JSON with helpful info and key environment variables required.
    """
    return jsonify(
        {
            "name": "Secure Notes API",
            "version": app.config.get("API_VERSION", "v1"),
            "docs": "/docs",
            "openapi": "/openapi.json",
            "notes_endpoints": {
                "list": "GET /notes/",
                "create": "POST /notes/",
                "detail": "GET /notes/{id}",
                "update": "PATCH /notes/{id}",
                "delete": "DELETE /notes/{id}",
                "search": "GET /notes/?q=keyword&tags=tag1,tag2&from=ISO&to=ISO",
                "sync_pull": "GET /notes/sync",
                "sync_push": "POST /notes/sync",
            },
            "taxonomy_endpoints": {
                "folders": {
                    "list": "GET /folders/",
                    "create": "POST /folders/",
                    "update": "PATCH /folders/{id}",
                    "delete": "DELETE /folders/{id}",
                },
                "tags": {
                    "list": "GET /tags/",
                    "create": "POST /tags/",
                    "delete": "DELETE /tags/{id}",
                },
            },
            "env_required": ["NOTES_ENCRYPTION_KEY"],
            "env_optional": ["DATABASE_URL"],
            "theme": {
                "name": "Ocean Professional",
                "primary": "#2563EB",
                "secondary": "#F59E0B",
                "error": "#EF4444",
                "background": "#f9fafb",
                "surface": "#ffffff",
                "text": "#111827",
                "modes": ["light", "dark"],
                "default_mode": "light",
            },
            "sync": {
                "strategy": "basic revision + last_updated timestamp",
                "conflict_policy": "last-writer-wins by default; client may send revision to detect conflicts",
            },
        }
    )
