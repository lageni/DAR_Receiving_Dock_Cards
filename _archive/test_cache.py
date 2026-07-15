#!/usr/bin/env python3
"""
Check if HTML caching is actually working
"""

from pathlib import Path
from cache_manager import get_cache_manager

cache = get_cache_manager()

# Check what files exist in cache
cache_dir = Path(r"L:\Engineering\DAR Docktag Cards\cache_data")
if cache_dir.exists():
    print("Cache directory exists")
    deliveries_dir = cache_dir / "deliveries"
    if deliveries_dir.exists():
        files = list(deliveries_dir.glob("*.json"))
        print(f"Found {len(files)} cache files in deliveries/")
        for f in files[:10]:  # Show first 10
            print(f"  - {f.name} ({f.stat().st_size} bytes)")
    else:
        print("No deliveries/ subdirectory")
else:
    print("Cache directory does NOT exist!")

# Test cache write and read
test_data = "<html>TEST</html>"
cache.set("test_delivery", test_data, category="deliveries")
print("\nWrote test cache...")

retrieved = cache.get("test_delivery", category="deliveries")
if retrieved == test_data:
    print("Cache read/write works!")
else:
    print(f"Cache problem - got back: {retrieved}")
