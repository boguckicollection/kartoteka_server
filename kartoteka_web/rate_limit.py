"""Simple in-memory rate limiter for authentication endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Optional

from fastapi import HTTPException, Request, status


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.
    
    Thread-safe implementation for limiting requests per IP address.
    """
    
    def __init__(
        self,
        max_requests: int = 5,
        window_seconds: int = 60,
        block_seconds: int = 300,
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in the window
            window_seconds: Time window in seconds
            block_seconds: How long to block after exceeding limit
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._blocked: dict[str, float] = {}
        self._lock = Lock()
    
    def _cleanup_old_requests(self, key: str, now: float) -> None:
        """Remove requests older than the window."""
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
    
    def _is_blocked(self, key: str, now: float) -> bool:
        """Check if the key is currently blocked."""
        if key in self._blocked:
            if now < self._blocked[key]:
                return True
            else:
                del self._blocked[key]
        return False
    
    def _get_remaining_block_time(self, key: str, now: float) -> int:
        """Get remaining block time in seconds."""
        if key in self._blocked:
            return max(0, int(self._blocked[key] - now))
        return 0
    
    def check(self, key: str) -> tuple[bool, Optional[int]]:
        """
        Check if request is allowed.
        
        Args:
            key: Unique identifier (usually IP address)
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = time.time()
        
        with self._lock:
            # Check if blocked
            if self._is_blocked(key, now):
                retry_after = self._get_remaining_block_time(key, now)
                return False, retry_after
            
            # Cleanup old requests
            self._cleanup_old_requests(key, now)
            
            # Check rate limit
            if len(self._requests[key]) >= self.max_requests:
                # Block the key
                self._blocked[key] = now + self.block_seconds
                return False, self.block_seconds
            
            # Allow request and record it
            self._requests[key].append(now)
            return True, None
    
    def reset(self, key: str) -> None:
        """Reset rate limit for a key (e.g., after successful login)."""
        with self._lock:
            if key in self._requests:
                del self._requests[key]
            if key in self._blocked:
                del self._blocked[key]


# Global rate limiters for different endpoints
# Login: 5 attempts per minute, block for 5 minutes
login_limiter = RateLimiter(max_requests=5, window_seconds=60, block_seconds=300)

# Register: 3 attempts per minute, block for 10 minutes
register_limiter = RateLimiter(max_requests=3, window_seconds=60, block_seconds=600)


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxy headers."""
    # Check for forwarded headers (when behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct client
    if request.client:
        return request.client.host
    
    return "unknown"


def check_login_rate_limit(request: Request) -> None:
    """
    Dependency to check login rate limit.
    
    Raises HTTPException 429 if rate limit exceeded.
    """
    client_ip = get_client_ip(request)
    allowed, retry_after = login_limiter.check(client_ip)
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Zbyt wiele prób logowania. Spróbuj ponownie za {retry_after} sekund.",
            headers={"Retry-After": str(retry_after)},
        )


def check_register_rate_limit(request: Request) -> None:
    """
    Dependency to check registration rate limit.
    
    Raises HTTPException 429 if rate limit exceeded.
    """
    client_ip = get_client_ip(request)
    allowed, retry_after = register_limiter.check(client_ip)
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Zbyt wiele prób rejestracji. Spróbuj ponownie za {retry_after} sekund.",
            headers={"Retry-After": str(retry_after)},
        )


def reset_login_rate_limit(request: Request) -> None:
    """Reset login rate limit after successful login."""
    client_ip = get_client_ip(request)
    login_limiter.reset(client_ip)
