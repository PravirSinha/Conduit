"""
CONDUIT — API Log Middleware
==============================
FastAPI middleware that logs every HTTP request and response.
Attached to the FastAPI app in api/main.py.

Logs:
    - Method, path, query params
    - Response status code
    - Request duration in ms
    - Client IP
    - RO ID if present in path or body

Usage in api/main.py:
    from app_logging.log_middleware import LoggingMiddleware
    app.add_middleware(LoggingMiddleware)
"""

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app_logging.logger import api_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every API request with timing.
    Skips health check endpoint to reduce noise.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:

        # Skip health check — too noisy
        if request.url.path == "/health":
            return await call_next(request)

        start_time = time.time()

        # Extract RO ID from path if present
        # e.g. /api/repair-orders/RO-2024-001
        path_parts = request.url.path.split("/")
        ro_id = None
        for i, part in enumerate(path_parts):
            if part in ["repair-orders", "quotes"] and i + 1 < len(path_parts):
                ro_id = path_parts[i + 1]
                break

        # Log incoming request
        api_logger.info({
            "event":       "request_start",
            "method":      request.method,
            "path":        request.url.path,
            "query":       str(request.query_params),
            "client_ip":   request.client.host if request.client else None,
            "ro_id":       ro_id,
        })

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code

        except Exception as e:
            api_logger.error({
                "event":  "request_error",
                "method": request.method,
                "path":   request.url.path,
                "error":  str(e),
                "ro_id":  ro_id,
            })
            raise

        # Log completed request with timing
        duration_ms = int((time.time() - start_time) * 1000)

        log_fn = api_logger.warning if status_code >= 400 else api_logger.info

        log_fn({
            "event":       "request_end",
            "method":      request.method,
            "path":        request.url.path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "ro_id":       ro_id,
        })

        return response