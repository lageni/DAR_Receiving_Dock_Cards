r"""Cache manager for delivery analysis data.

Stores and retrieves cached data from L:\Engineering\DAR Docktag Cards\cache_data
Auto-clears entries older than 2 days.
"""

import json
import os
import time
import hashlib
from pathlib import Path
from datetime import datetime, timedelta


class CacheManager:
    """Manages local cache for delivery, PO, and item data."""
    
    def __init__(self, cache_dir: str = None):
        """Initialize cache manager."""
        if cache_dir is None:
            cache_dir = r"L:\Engineering\DAR Docktag Cards\cache_data"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_seconds = 2 * 24 * 60 * 60  # 2 days
    
    def _get_hash_key(self, key: str) -> str:
        """Convert key to safe filename."""
        return hashlib.md5(key.encode()).hexdigest()
    
    def _get_cache_path(self, key: str, category: str = "general") -> Path:
        """Get full cache file path."""
        cat_dir = self.cache_dir / category
        cat_dir.mkdir(exist_ok=True)
        return cat_dir / f"{self._get_hash_key(key)}.json"
    
    def _is_expired(self, cache_path: Path) -> bool:
        """Check if cache file is expired."""
        if not cache_path.exists():
            return True
        
        file_age = time.time() - cache_path.stat().st_mtime
        return file_age > self.max_age_seconds
    
    def _cleanup_expired(self, category: str = None):
        """Remove expired cache files."""
        if category:
            dirs_to_clean = [self.cache_dir / category]
        else:
            dirs_to_clean = [d for d in self.cache_dir.iterdir() if d.is_dir()]
        
        for cat_dir in dirs_to_clean:
            if not cat_dir.exists():
                continue
            for cache_file in cat_dir.glob("*.json"):
                if self._is_expired(cache_file):
                    try:
                        cache_file.unlink()
                    except:
                        pass
    
    def get(self, key: str, category: str = "general"):
        """Retrieve data from cache if available and not expired."""
        self._cleanup_expired(category)
        cache_path = self._get_cache_path(key, category)
        
        if not cache_path.exists() or self._is_expired(cache_path):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('data')
        except:
            return None
    
    def set(self, key: str, data, category: str = "general"):
        """Store data in cache."""
        cache_path = self._get_cache_path(key, category)
        
        try:
            cache_data = {
                'key': key,
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, default=str)
            return True
        except Exception as e:
            print(f"[CACHE] Error writing cache: {str(e)}")
            return False
    
    def clear_category(self, category: str):
        """Clear all cache files in a category."""
        cat_dir = self.cache_dir / category
        if cat_dir.exists():
            for cache_file in cat_dir.glob("*.json"):
                try:
                    cache_file.unlink()
                except:
                    pass
    
    def clear_all(self):
        """Clear entire cache."""
        for cat_dir in self.cache_dir.iterdir():
            if cat_dir.is_dir():
                for cache_file in cat_dir.glob("*.json"):
                    try:
                        cache_file.unlink()
                    except:
                        pass


# Global cache instance
_cache = None

def get_cache_manager():
    """Get or create global cache manager."""
    global _cache
    if _cache is None:
        _cache = CacheManager()
    return _cache
