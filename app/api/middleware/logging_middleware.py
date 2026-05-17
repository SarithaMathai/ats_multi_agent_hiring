"""
Request/response logging middleware.

Logs method, path, status code, and wall-clock duration for every HTTP request.
Adds an X-Request-ID header to each response for end-to-end tracing.
"""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("ats.http")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        logger.info(
            "[%s] --> %s %s",
            request_id, request.method, request.url.path,
        )

        response: Response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "[%s] <-- %s %s  status=%d  %.0f ms",
            request_id, request.method, request.url.path,
            response.status_code, elapsed_ms,
        )
        return response
