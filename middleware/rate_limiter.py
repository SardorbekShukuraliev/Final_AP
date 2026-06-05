import time
from collections import defaultdict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class TokenBucket:
    def __init__(self, rate: float, burst: int):
        self.rate = rate          # токенов в секунду
        self.burst = burst        # максимальный размер ведра
        self.tokens = burst
        self.last_refill = time.monotonic()

    def consume(self, amount: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 100, burst_size: int = 20):
        super().__init__(app)
        self.rate = requests_per_minute / 60.0
        self.burst = burst_size
        self.buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(self.rate, self.burst)
        )

    async def dispatch(self, request: Request, call_next):
        # Не применяем лимиты к WebSocket и статике
        if request.scope.get("type") == "websocket" or request.url.path.startswith("/app"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        bucket = self.buckets[client_ip]
        if not bucket.consume():
            return JSONResponse(
                status_code=429,
                content={"detail": "Слишком много запросов. Попробуйте позже."}
            )

        response = await call_next(request)
        return response