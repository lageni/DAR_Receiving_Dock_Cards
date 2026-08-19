#!/usr/bin/env python
"""Test if DB query with string IDs works"""

import sqlite3
from pathlib import Path

db_path = Path(r"L:\Engineering\DAR Docktag Cards\read_rates.db")

# Test with known item
test_ids = ['550508254', '674874972', '570741739']  # Known items

print(f"Testing query with IDs: {test_ids}")
print(f"ID types: {[type(id).__name__ for id in test_ids]}")

with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=20.0) as conn:
    cursor = conn.cursor()
    
    # Create placeholders
    placeholders = ','.join('?' * len(test_ids))
    query = f"""
        SELECT mds_fam_id, COUNT(*) as record_count
        FROM read_rates
        WHERE mds_fam_id IN ({placeholders})
        GROUP BY mds_fam_id
    """
    
    print(f"\nExecuting query...")
    cursor.execute(query, test_ids)
    
    rows = cursor.fetchall()
    print(f"\nResults: {len(rows)} items found")
    
    for item_id, count in rows:
        print(f"  Item {item_id}: {count} records")
    
    if len(rows) == 0:
        print("\nERROR: No results! Testing with integer IDs...")
        
        # Try with integers
        int_ids = [int(id) for id in test_ids]
        cursor.execute(query, int_ids)
        rows = cursor.fetchall()
        print(f"Integer query results: {len(rows)} items")
        
        for item_id, count in rows:
            print(f"  Item {item_id}: {count} records")

print("\nDone!")
