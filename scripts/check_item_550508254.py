#!/usr/bin/env python
"""Check performance for item 550508254"""
import sqlite3
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

db_path = os.getenv("DATABASE_PATH", "")
if not db_path:
    db_path = str(Path(__file__).parent / "read_rates.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if item exists
cursor.execute("SELECT COUNT(*) FROM read_rates WHERE mds_fam_id = ?", ('550508254',))
count = cursor.fetchone()[0]
print(f"Item 550508254 has {count} records in database")

if count > 0:
    # Get totals
    cursor.execute("""
        SELECT SUM(acl_null_cnt), SUM(acl_event_cnt)
        FROM read_rates
        WHERE mds_fam_id = ? AND acl_event_cnt > 0
    """, ('550508254',))
    
    row = cursor.fetchone()
    total_null = row[0] or 0
    total_events = row[1] or 0
    
    print(f"Total successful reads (acl_null_cnt): {total_null}")
    print(f"Total events: {total_events}")
    
    if total_events > 0:
        performance = (total_null / total_events) * 100
        print(f"Performance: {performance:.2f}%")
        print(f"Should flag (< 85%): {performance < 85}")
    else:
        print("No events found - cannot calculate performance")
else:
    print("Item not found in database - cannot calculate performance")
    print("This item will show 0% performance or be skipped")

conn.close()
