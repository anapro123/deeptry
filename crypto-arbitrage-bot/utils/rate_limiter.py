import asyncio
import time
from collections import deque
from typing import Optional

class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """Acquire permission to make a request"""
        async with self.lock:
            current_time = time.time()
            
            # Remove old requests
            while self.requests and self.requests[0] < current_time - self.time_window:
                self.requests.popleft()
            
            if len(self.requests) < self.max_requests:
                self.requests.append(current_time)
                return True
            else:
                # Calculate wait time
                wait_time = self.requests[0] + self.time_window - current_time
                await asyncio.sleep(wait_time + 0.01)
                return await self.acquire()