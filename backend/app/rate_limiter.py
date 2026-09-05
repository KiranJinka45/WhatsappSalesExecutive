import time
from fastapi import Request, HTTPException, status
from collections import defaultdict
import logging
import uuid

logger = logging.getLogger(__name__)

class RedisRateLimiter:
    def __init__(self, name: str, requests_limit: int, window_seconds: int):
        self.name = name
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        # In-memory fallback
        self.fallback_requests = defaultdict(list)

    def _in_memory_check(self, client_ip: str, now: float):
        # Clean up old requests outside window
        self.fallback_requests[client_ip] = [t for t in self.fallback_requests[client_ip] if now - t < self.window_seconds]
        if len(self.fallback_requests[client_ip]) >= self.requests_limit:
            logger.warning(f"Rate limit exceeded (in-memory fallback) for client IP: {client_ip}. Limit: {self.requests_limit}/{self.window_seconds}s")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )
        self.fallback_requests[client_ip].append(now)

    @property
    def requests(self):
        return self.fallback_requests

    def __call__(self, request: Request):
        from .config import settings
        
        # Resolve real client IP behind reverse proxy (Render, Cloudflare, ALB)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.headers.get("x-real-ip"):
            client_ip = request.headers.get("x-real-ip").strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
            
        now = time.time()

        if settings.TESTING:
            self._in_memory_check(client_ip, now)
            return

        # Try Redis first
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            key = f"rate_limit:{self.name}:{client_ip}"
            
            # Sliding window using ZSET
            pipe = r.pipeline()
            # Remove timestamps older than the window
            pipe.zremrangebyscore(key, "-inf", f"({now - self.window_seconds}")
            # Count the remaining requests
            pipe.zcard(key)
            _, current_count = pipe.execute()

            if current_count >= self.requests_limit:
                logger.warning(f"Rate limit exceeded (Redis) for client IP: {client_ip}. Limit: {self.requests_limit}/{self.window_seconds}s")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later."
                )

            # Add current request timestamp
            pipe = r.pipeline()
            pipe.zadd(key, {f"{now}-{uuid.uuid4()}": now})
            pipe.expire(key, self.window_seconds + 10)
            pipe.execute()

        except HTTPException:
            # Re-raise rate limit exceptions
            raise
        except Exception as e:
            logger.warning(f"Redis rate limiter failed ({e}), falling back to in-memory limiter.")
            self._in_memory_check(client_ip, now)

# Backwards compatible alias mapping
class InMemoryRateLimiter(RedisRateLimiter):
    def __init__(self, requests_limit: int, window_seconds: int, name: str = "default"):
        super().__init__(name, requests_limit, window_seconds)
