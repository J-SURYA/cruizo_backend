from fastapi import Request
import redis.asyncio as redis
from typing import Dict, Any, Tuple
from fastapi.responses import JSONResponse


from app.core.config import settings
from app.utils.logger_utils import get_logger


logger = get_logger(__name__)


class RateLimitMiddleware:
    """
    Class implementing rate limiting middleware using Redis.
    Applies per-IP and per-endpoint rate limits with customizable time windows.
    """
    def __init__(self):
        connection_params = {
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "decode_responses": True,
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
            "retry_on_timeout": True,
        }

        # Add password only if provided
        if settings.REDIS_PASSWORD and settings.REDIS_PASSWORD.strip():
            connection_params["password"] = settings.REDIS_PASSWORD.strip()

        self.redis_client = redis.Redis(**connection_params)

        # Default global limits
        self.default_limits = {
            "minute": settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
            "hour": settings.RATE_LIMIT_REQUESTS_PER_HOUR,
            "day": settings.RATE_LIMIT_REQUESTS_PER_DAY,
        }

        # Per-endpoint override limits (useful for sensitive API routes)
        self.endpoint_limits: Dict[str, Dict[str, Any]] = {
            "/api/auth/login": {"minute": 10, "hour": 100},
            "/api/auth/register": {"minute": 5, "hour": 50},
        }

        # IP addresses exempted from rate limiting (empty during testing)
        self.ip_whitelist = []


    async def __call__(self, request: Request, call_next):
        """
        Main middleware handler entrypoint.
        
        Args:
            request: Incoming FastAPI request
            call_next: Next middleware or route handler

        Returns:
            Response from next handler or rate-limit error response
        """
        try:
            client_ip = self.get_client_ip(request)
            endpoint = request.url.path

            if client_ip in self.ip_whitelist:
                return await call_next(request)

            if request.method == "OPTIONS":
                return await call_next(request)

            if await self.should_skip_rate_limit(request):
                return await call_next(request)

            limits = self.endpoint_limits.get(endpoint, self.default_limits)

            is_blocked, retry_after = await self.check_rate_limits(
                client_ip, endpoint, limits, request.method
            )

            if is_blocked:
                return await self.rate_limit_response(retry_after)

            response = await call_next(request)

            if not self.is_streaming_endpoint(request):
                await self.add_rate_limit_headers(response, client_ip, endpoint, limits)

            return response

        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}", exc_info=True)
            return await call_next(request)


    async def rate_limit_response(self, retry_after: int):
        """
        Return standardized 429 rate-limit response.
        
        Args:
            retry_after: Seconds until client can retry
        
        Returns:
            JSONResponse with 429 status and retry info
        """
        return JSONResponse(
            status_code=429,
            content={
                "error": "Too many requests",
                "retry_after": retry_after,
                "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
            },
            headers={"Retry-After": str(retry_after)},
        )
    

    async def check_rate_limits(
        self, client_ip: str, endpoint: str, limits: Dict[str, Any], method: str
    ) -> Tuple[bool, int]:
        """
        Check whether request exceeds any configured time window.
        
        Args:
            client_ip: IP address of the client
            endpoint: Requested API endpoint
            limits: Rate limit configuration per time window
            method: HTTP method of the request  
        
        Returns:
            Tuple indicating if blocked and retry-after seconds
        """

        try:
            time_windows = {
                "minute": 60,
                "hour": 3600,
                "day": 86400,
            }

            method_multiplier = {
                "GET": 1,
                "POST": 2,
                "PUT": 2,
                "DELETE": 3,
                "PATCH": 2,
            }
            weight = method_multiplier.get(method, 1)

            for period, limit in limits.items():
                window = time_windows.get(period, 60)
                key = f"rate_limit:{client_ip}:{endpoint}:{period}"

                current_count = await self.increment_counter(key, window, weight)
                print(f"{endpoint} {period}: {current_count}/{limit}")

                if current_count > limit:
                    ttl = await self.redis_client.ttl(key)
                    retry_after = ttl if ttl > 0 else window
                    print(
                        f"Rate limit exceeded: {endpoint} {current_count}/{limit}, retry in {retry_after}s"
                    )
                    return True, retry_after

            return False, 0

        except Exception as e:
            print(f"Redis rate limit check error: {e}")
            return False, 0


    async def increment_counter(self, key: str, window: int, weight: int = 1) -> int:
        """
        Increment request counter and set TTL if needed.
        
        Args:
            key: Redis key for the rate limit counter
            window: Time window in seconds
            weight: Weight of the request based on HTTP method

        Returns:
            Current count after increment
        """
        try:
            pipeline = self.redis_client.pipeline()
            pipeline.incrby(key, weight)
            pipeline.expire(key, window)
            results = await pipeline.execute()
            return results[0]
        except Exception as e:
            print(f"Redis increment error: {e}")
            return 0


    async def add_rate_limit_headers(
        self, response, client_ip: str, endpoint: str, limits: Dict[str, Any]
    ):
        """
        Attach rate-limit information headers to response.

        Args:
            response: FastAPI response object
            client_ip: IP address of the client
            endpoint: Requested API endpoint
            limits: Rate limit configuration per time window

        Returns:
            None
        """
        try:
            for period, limit in limits.items():
                key = f"rate_limit:{client_ip}:{endpoint}:{period}"
                current_count = int(await self.redis_client.get(key) or 0)
                ttl = await self.redis_client.ttl(key)

                response.headers[f"X-RateLimit-Limit-{period.capitalize()}"] = str(
                    limit
                )
                response.headers[f"X-RateLimit-Remaining-{period.capitalize()}"] = str(
                    max(0, limit - current_count)
                )
                response.headers[f"X-RateLimit-Reset-{period.capitalize()}"] = str(ttl)

        except Exception as e:
            print(f"Header update error: {e}")


    def get_client_ip(self, request: Request) -> str:
        """
        Extract client IP considering proxy headers.
        
        Args:
            request: Incoming FastAPI request

        Returns:
            Client IP address as string
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


    async def should_skip_rate_limit(self, request: Request) -> bool:
        """
        Paths excluded from rate limiting (docs, schema, assets).
        
        Args:
            request: Incoming FastAPI request

        Returns:
            Boolean indicating if rate limiting should be skipped
        """
        skip_paths = ["/docs", "/redoc", "/openapi.json", "/favicon.ico"]
        return request.url.path in skip_paths


    def is_streaming_endpoint(self, request: Request) -> bool:
        """
        Check if endpoint is a streaming endpoint.
        
        Args:
            request: Incoming FastAPI request

        Returns:
            Boolean indicating if endpoint is streaming
        """
        streaming_paths = ["/api/v1/chat/stream", "/api/chat/stream"]
        return request.url.path in streaming_paths


rate_limit_middleware = RateLimitMiddleware()
