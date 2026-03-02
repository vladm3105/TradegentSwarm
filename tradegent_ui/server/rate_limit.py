"""Per-user rate limiting for Tradegent Agent UI."""
import structlog
import time
from collections import defaultdict
from typing import Optional
from fastapi import HTTPException, Request

from .config import get_settings

log = structlog.get_logger()


class RateLimiter:
    """In-memory rate limiter with sliding window."""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)

    def check(self, user_id: str) -> None:
        """Check if user is within rate limit.

        Args:
            user_id: User identifier (Auth0 sub or API key ID)

        Raises:
            HTTPException: If rate limit exceeded (429)
        """
        now = time.time()
        minute_ago = now - 60

        # Clean old requests
        self.requests[user_id] = [
            t for t in self.requests[user_id] if t > minute_ago
        ]

        # Check limit
        if len(self.requests[user_id]) >= self.rpm:
            log.warn("Rate limit exceeded", user_id=user_id, requests=len(self.requests[user_id]))
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.rpm),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + 60)),
                },
            )

        # Record request
        self.requests[user_id].append(now)

    def get_remaining(self, user_id: str) -> int:
        """Get remaining requests for user."""
        now = time.time()
        minute_ago = now - 60

        # Count recent requests
        recent = [t for t in self.requests.get(user_id, []) if t > minute_ago]
        return max(0, self.rpm - len(recent))

    def get_headers(self, user_id: str) -> dict[str, str]:
        """Get rate limit headers for response."""
        remaining = self.get_remaining(user_id)
        now = time.time()

        return {
            "X-RateLimit-Limit": str(self.rpm),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(now + 60)),
        }

    def cleanup(self) -> None:
        """Remove expired entries to free memory."""
        now = time.time()
        minute_ago = now - 60

        users_to_remove = []
        for user_id, timestamps in self.requests.items():
            # Remove old timestamps
            self.requests[user_id] = [t for t in timestamps if t > minute_ago]
            # Mark empty users for removal
            if not self.requests[user_id]:
                users_to_remove.append(user_id)

        # Remove empty users
        for user_id in users_to_remove:
            del self.requests[user_id]


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        settings = get_settings()
        _rate_limiter = RateLimiter(
            requests_per_minute=settings.rate_limit_requests_per_minute
        )
    return _rate_limiter


async def rate_limit_middleware(request: Request, call_next):
    """Middleware to apply rate limiting.

    Applies rate limiting based on:
    1. Authenticated user's sub (from request.state.user)
    2. API key ID
    3. IP address (fallback for unauthenticated requests)
    """
    settings = get_settings()

    if not settings.rate_limit_enabled:
        return await call_next(request)

    # Skip rate limiting for health checks
    if request.url.path in ["/health", "/ready"]:
        return await call_next(request)

    rate_limiter = get_rate_limiter()

    # Determine user identifier
    user_id: str
    if hasattr(request.state, "user") and request.state.user:
        user = request.state.user
        if user.is_api_key:
            user_id = f"api_key:{user.api_key_id}"
        else:
            user_id = f"user:{user.sub}"
    else:
        # Fallback to IP address for unauthenticated requests
        client_ip = request.client.host if request.client else "unknown"
        user_id = f"ip:{client_ip}"

    # Check rate limit
    try:
        rate_limiter.check(user_id)
    except HTTPException:
        raise

    # Process request
    response = await call_next(request)

    # Add rate limit headers
    headers = rate_limiter.get_headers(user_id)
    for key, value in headers.items():
        response.headers[key] = value

    return response


class EndpointRateLimiter:
    """Rate limiter for specific endpoints with custom limits."""

    def __init__(self, endpoint_limits: dict[str, int] | None = None):
        """
        Args:
            endpoint_limits: Dict mapping endpoint paths to requests per minute.
                            e.g., {"/api/chat": 10, "/api/analyze": 5}
        """
        self.endpoint_limits = endpoint_limits or {}
        self.limiters: dict[str, RateLimiter] = {}

    def get_limiter(self, endpoint: str) -> Optional[RateLimiter]:
        """Get rate limiter for endpoint if configured."""
        if endpoint not in self.endpoint_limits:
            return None

        if endpoint not in self.limiters:
            self.limiters[endpoint] = RateLimiter(
                requests_per_minute=self.endpoint_limits[endpoint]
            )

        return self.limiters[endpoint]

    def check(self, endpoint: str, user_id: str) -> None:
        """Check rate limit for specific endpoint."""
        limiter = self.get_limiter(endpoint)
        if limiter:
            limiter.check(user_id)


# Endpoint-specific rate limiter (more restrictive for expensive operations)
_endpoint_limiter: Optional[EndpointRateLimiter] = None


def get_endpoint_rate_limiter() -> EndpointRateLimiter:
    """Get endpoint rate limiter with custom limits."""
    global _endpoint_limiter
    if _endpoint_limiter is None:
        _endpoint_limiter = EndpointRateLimiter({
            "/api/chat": 30,  # 30 messages per minute
            "/api/analyze": 10,  # 10 analyses per minute
        })
    return _endpoint_limiter
