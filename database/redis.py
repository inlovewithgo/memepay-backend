from redis.asyncio import Redis
from functools import wraps
import json
from typing import Optional, Any

class RedisConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.REDIS_URL = "redis://:exrilatmemepay@194.15.36.168:6379"
            self.client = None
            self.initialized = False

    async def initialize(self):
        if not self.initialized:
            try:
                self.client = Redis.from_url(
                    self.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                await self.client.ping()
                self.initialized = True
            except Exception as e:
                raise Exception(f"Failed to initialize Redis: {str(e)}")
        return self

    async def close(self):
        if self.client:
            await self.client.close()

    async def get(self, key: str) -> Optional[Any]:
        try:
            data = await self.client.get(key)
            return json.loads(data) if data else None
        except Exception:
            return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        try:
            await self.client.set(key, json.dumps(value), ex=expire)
        except Exception:
            pass

redis_config = RedisConfig()

def get_cached_info(redis):
    return 0

def cached(expire: int = 3600):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            cached_result = await redis_config.get(key)
            if cached_result is not None:
                return cached_result
            result = await func(*args, **kwargs)
            await redis_config.set(key, result, expire)
            return result
        return wrapper
    return decorator
