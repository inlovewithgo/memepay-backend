from redis.asyncio import Redis
from functools import wraps
import json
from typing import Optional, Any

class RedisCacheManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.redis_url = "redis://exril:exrilatmemepay@194.15.36.168:6379"
            self.redis_client = None
            self.initialized = False

    async def initialize(self):
        if not self.initialized:
            self.redis_client = Redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            self.initialized = True
        return self

    async def get(self, key: str) -> Optional[Any]:
        try:
            data = await self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception:
            return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        try:
            await self.redis_client.set(key, json.dumps(value), ex=expire)
        except Exception:
            pass


cache = RedisCacheManager()


def cached(expire: int = 3600):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            cached_result = await cache.get(key)
            if cached_result is not None:
                return cached_result

            result = await func(*args, **kwargs)
            await cache.set(key, result, expire)
            return result

        return wrapper

    return decorator
