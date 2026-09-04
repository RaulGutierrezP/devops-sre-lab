import logging
import os
import platform
import socket
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, g, jsonify, request


# ============================================================
# Configuration
# ============================================================

class Config:
    APP_NAME = os.getenv("APP_NAME", "devops-sre-lab")
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8080"))

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    SERVICE_NAME = os.getenv(
        "SERVICE_NAME",
        "devops-sre-lab"
    )


# ============================================================
# Application
# ============================================================

app = Flask(__name__)
app.config.from_object(Config)


# ============================================================
# Runtime state
# ============================================================

START_TIME = time.time()

REQUEST_COUNT = 0
ERROR_COUNT = 0
TOTAL_REQUEST_TIME = 0.0


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format=(
        "%(asctime)s "
        "level=%(levelname)s "
        "message=%(message)s"
    ),
)

logger = logging.getLogger(Config.APP_NAME)


# ============================================================
# Helpers
# ============================================================

def utc_now():
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def uptime_seconds():
    """Return application uptime."""
    return round(time.time() - START_TIME, 2)


def response(data, status_code=200):
    """Return a consistent JSON response."""
    return jsonify(data), status_code


# ============================================================
# Request tracing
# ============================================================

@app.before_request
def before_request():
    """
    Create a request ID for distributed tracing.
    """
    g.request_id = request.headers.get(
        "X-Request-ID",
        str(uuid.uuid4())
    )

    g.request_start = time.perf_counter()


@app.after_request
def after_request(http_response):
    """
    Add tracing and security headers to every response.
    """
    global REQUEST_COUNT
    global TOTAL_REQUEST_TIME

    duration = time.perf_counter() - g.request_start

    REQUEST_COUNT += 1
    TOTAL_REQUEST_TIME += duration

    http_response.headers["X-Request-ID"] = g.request_id

    http_response.headers["X-Content-Type-Options"] = "nosniff"
    http_response.headers["X-Frame-Options"] = "DENY"
    http_response.headers["Referrer-Policy"] = "no-referrer"

    logger.info(
        "request "
        "method=%s "
        "path=%s "
        "status=%s "
        "duration_ms=%.2f "
        "request_id=%s",
        request.method,
        request.path,
        http_response.status_code,
        duration * 1000,
        g.request_id,
    )

    return http_response


# ============================================================
# Application endpoints
# ============================================================

@app.route("/", methods=["GET"])
def home():
    """
    Main application endpoint.
    """
    return response({
        "application": Config.APP_NAME,
        "version": Config.APP_VERSION,
        "environment": Config.ENVIRONMENT,
        "service": Config.SERVICE_NAME,
        "status": "running",
        "timestamp": utc_now(),
        "request_id": g.request_id,
    })


# ============================================================
# Health endpoints
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    """
    Liveness probe.

    The process is alive and responding.
    """
    return response({
        "status": "ok",
        "service": Config.SERVICE_NAME,
        "timestamp": utc_now(),
    })


@app.route("/ready", methods=["GET"])
def ready():
    """
    Readiness probe.

    The service is ready to receive traffic.
    """
    return response({
        "status": "ready",
        "service": Config.SERVICE_NAME,
        "timestamp": utc_now(),
    })


# ============================================================
# Application information
# ============================================================

@app.route("/info", methods=["GET"])
def info():
    """
    Runtime information useful for debugging and operations.
    """
    return response({
        "application": Config.APP_NAME,
        "version": Config.APP_VERSION,
        "environment": Config.ENVIRONMENT,
        "service": Config.SERVICE_NAME,
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "uptime_seconds": uptime_seconds(),
        "timestamp": utc_now(),
        "request_id": g.request_id,
    })


# ============================================================
# Metrics
# ============================================================

@app.route("/metrics", methods=["GET"])
def metrics():
    """
    Lightweight Prometheus-style metrics endpoint.
    """
    global ERROR_COUNT

    average_latency = (
        TOTAL_REQUEST_TIME / REQUEST_COUNT
        if REQUEST_COUNT > 0
        else 0
    )

    return (
        "\n".join([
            "# HELP app_requests_total Total HTTP requests",
            "# TYPE app_requests_total counter",
            f"app_requests_total {REQUEST_COUNT}",

            "# HELP app_errors_total Total HTTP 5xx errors",
            "# TYPE app_errors_total counter",
            f"app_errors_total {ERROR_COUNT}",

            "# HELP app_uptime_seconds Application uptime",
            "# TYPE app_uptime_seconds gauge",
            f"app_uptime_seconds {uptime_seconds()}",

            "# HELP app_request_latency_seconds Average request latency",
            "# TYPE app_request_latency_seconds gauge",
            f"app_request_latency_seconds {average_latency}",
        ])
        + "\n",
        200,
        {
            "Content-Type": "text/plain; version=0.0.4"
        }
    )


# ============================================================
# Operational endpoint
# ============================================================

@app.route("/version", methods=["GET"])
def version():
    """
    Return application version.
    """
    return response({
        "application": Config.APP_NAME,
        "version": Config.APP_VERSION,
        "environment": Config.ENVIRONMENT,
    })


# ============================================================
# 404 handler
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return response({
        "error": "not_found",
        "message": "The requested endpoint does not exist",
        "path": request.path,
        "request_id": g.get("request_id"),
        "timestamp": utc_now(),
    }, 404)


# ============================================================
# 405 handler
# ============================================================

@app.errorhandler(405)
def method_not_allowed(error):
    return response({
        "error": "method_not_allowed",
        "message": "HTTP method is not allowed",
        "method": request.method,
        "path": request.path,
        "request_id": g.get("request_id"),
        "timestamp": utc_now(),
    }, 405)


# ============================================================
# Global exception handler
# ============================================================

@app.errorhandler(Exception)
def handle_exception(error):
    """
    Catch unexpected application errors.

    The real exception is logged server-side while the client
    receives a safe generic response.
    """
    global ERROR_COUNT

    ERROR_COUNT += 1

    logger.exception(
        "unhandled_exception "
        "request_id=%s",
        g.get("request_id"),
    )

    return response({
        "error": "internal_server_error",
        "message": "An unexpected error occurred",
        "request_id": g.get("request_id"),
        "timestamp": utc_now(),
    }, 500)


# ============================================================
# Startup
# ============================================================

def log_startup():
    """
    Log important information when the service starts.
    """
    logger.info(
        "application_start "
        "name=%s "
        "version=%s "
        "environment=%s "
        "host=%s "
        "port=%s",
        Config.APP_NAME,
        Config.APP_VERSION,
        Config.ENVIRONMENT,
        Config.HOST,
        Config.PORT,
    )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    log_startup()

    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
    )

