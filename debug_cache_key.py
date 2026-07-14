#!/usr/bin/env python3

import hashlib

delivery = "10774072"
html_key = f"html_{delivery}"
print(f"Checking cache key for: {html_key}")
print(f"MD5 hash: {hashlib.md5(html_key.encode()).hexdigest()}")

# Check all files
import os
from pathlib import Path

cache_dir = Path(r"L:\Engineering\DAR Docktag Cards\cache_data\deliveries")
files = sorted(cache_dir.glob("*.json"))

print(f"\nFound {len(files)} cache files:")
for f in files:
    print(f.name)

# Try to read the largest one (likely the HTML)
largest = max(files, key=lambda x: x.stat().st_size)
print(f"\nLargest file: {largest.name}")

import json
try:
    with open(largest, 'r') as f:
        data = json.load(f)
        if isinstance(data, dict) and 'key' in data:
            print(f"Cache key in file: {data['key']}")
except:
    print("Could not read file")
