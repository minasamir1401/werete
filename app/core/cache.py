import time
from typing import Any, Optional

class MemoryCache:
    def __init__(self):
        self._data = {}
        self._expiry = {}

    def set(self, key: str, value: Any, ttl: int = 60):
        self._data[key] = value
        self._expiry[key] = time.time() + ttl

    def get(self, key: str) -> Optional[Any]:
        if key in self._data:
            if time.time() < self._expiry[key]:
                return self._data[key]
            else:
                del self._data[key]
                del self._expiry[key]
        return None

    def invalidate(self, key: str):
        if key in self._data:
            del self._data[key]
            del self._expiry[key]

# Global instance
cache = MemoryCache()
