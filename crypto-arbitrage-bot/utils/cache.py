import asyncio
import time
from typing import Any, Optional
import json
import redis.asyncio as redis
from functools import wraps

class Cache:
    def __init__(self, redis_url: Optional[str] = None, ttl: int = 60):
        self.redis_url = redis_url
        self.default_ttl = ttl
        self._redis = None
        self._local_cache = {}
        self._local_cache_ttl = {}
    
    async def _get_redis(self):
        if self._redis is None and self.redis_url:
            self._redis = await redis.from_url(self.redis_url)
        return self._redis
    
    async def get(self, key: str) -> Optional[Any]:
        # Check local cache first
        if key in self._local_cache:
            if time.time() < self._local_cache_ttl.get(key, 0):
                return self._local_cache[key]
            else:
                del self._local_cache[key]
                del self._local_cache_ttl[key]
        
        # Check Redis
        redis_client = await self._get_redis()
        if redis_client:
            try:
                data = await redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        # Store in local cache
        ttl = ttl or self.default_ttl
        self._local_cache[key] = value
        self._local_cache_ttl[key] = time.time() + ttl
        
        # Store in Redis
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.setex(key, ttl, json.dumps(value, default=str))
            except Exception:
                pass
    
    async def delete(self, key: str):
        if key in self._local_cache:
            del self._local_cache[key]
            del self._local_cache_ttl[key]
        
        redis_client = await self._get_redis()
        if redis_client:
            await redis_client.delete(key)
    
    async def close(self):
        if self._redis:
            await self._redis.close()