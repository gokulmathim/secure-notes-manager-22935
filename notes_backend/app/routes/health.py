from flask_smorest import Blueprint
from flask.views import MethodView

# Correct tag name and blueprint identifiers
blp = Blueprint("Health Check", "health", url_prefix="/", description="Health check route")


@blp.route("/")
class HealthCheck(MethodView):
    """Basic health check endpoint."""
    def get(self):
        return {"message": "Healthy"}
