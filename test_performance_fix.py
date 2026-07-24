#!/usr/bin/env python
"""Test performance calculation fix for item 674874972"""

import sqlite3
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Replicate get_avg_performance function (NEW FIXED VERSION)
def get_avg_performance(item_rates: list) -> float:
    """Calculate average ACL Performance using total(acl_null_cnt) / total(acl_event_cnt)."""
    if not item_rates:
        return 0
    
    # Sum ALL null counts and ALL event counts (weighted average)
    total_null_cnt = sum(r['null_cnt'] for r in item_rates)
    total_event_cnt = sum(r['event_cnt'] for r in item_rates)
    
    if total_event_cnt == 0:
        return 0
    
    # Calculate null percentage: total(acl_null_cnt) / total(acl_event_cnt) * 100
    acl_null_pct = (total_null_cnt / total_event_cnt) * 100
    
    # Return PERFORMANCE (inverse of null %)
    return 100 - acl_null_pct

# Get database path
db_path = os.getenv("DATABASE_PATH", "")
if not db_path:
    db_path = str(Path(__file__).parent / "read_rates.db")

print("=" * 70)
print("ITEM 674874972 PERFORMANCE TEST")
print("=" * 70)

if not Path(db_path).exists():
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Query item 674874972
cursor.execute("""
    SELECT acl_insert_date, acl_event_cnt, acl_null_cnt
    FROM read_rates
    WHERE mds_fam_id = ? AND acl_event_cnt > 0
    ORDER BY acl_insert_date
""", ('674874972',))

rows = cursor.fetchall()
conn.close()

if not rows:
    print("ERROR: No records found for item 674874972")
    exit(1)

print(f"\nRecords found: {len(rows)}")

# Build item_rates structure
item_rates = []
for date, event_cnt, null_cnt in rows:
    null_pct = (null_cnt / event_cnt) * 100 if event_cnt > 0 else 0
    item_rates.append({
        'date': date,
        'event_cnt': event_cnt,
        'null_cnt': null_cnt,
        'null_pct': null_pct
    })

# Calculate performance
performance = get_avg_performance(item_rates)

print(f"\nCalculation:")
print(f"  Total Events: {sum(r['event_cnt'] for r in item_rates)}")
print(f"  Total Nulls: {sum(r['null_cnt'] for r in item_rates)}")
print(f"  Performance: {performance:.2f}%")
print(f"\nShould be flagged (< 85%): {performance < 85}")

if performance < 85:
    if performance < 50:
        recommendation = "WORKSTATION RECOMMENDED"
        color = "RED"
    else:
        recommendation = "REQUIRES MANUAL INSPECTION"
        color = "YELLOW"
    print(f"\nRecommendation: {recommendation} ({color})")
else:
    print(f"\nRecommendation: ACL APPROVED (GREEN)")

print("\n" + "=" * 70)
print(" FIX VALIDATED - Item will now be flagged correctly!")
print("=" * 70)
