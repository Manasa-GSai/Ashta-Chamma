"""Security headers middleware.

Adds OWASP-recommended security headers to every HTTP response so that
browsers enforce content-type sniffing prevention, clickjacking protection,
and transport security.

Architecture spec requires HSTS with a 1-year max-age.
"""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# HSTS 1-year max-age as mandated by the security architecture spec.
_HSTS_VALUE = "max-age=31536000; includeSubDomains"

_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Strict-Transport-Security": _HSTS_VALUE,
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects OWASP-recommended security headers into every HTTP response.

    This middleware runs after all route handlers and other middleware so
    headers are added regardless of which path served the response.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
