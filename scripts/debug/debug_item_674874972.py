#!/usr/bin/env python
"""Debug script to investigate why item 674874972 isn't flagged"""

import sys
import sqlite3
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Calculate performance directly from database
db_path = os.getenv("DATABASE_PATH", "")
if not db_path:
    db_path = str(Path(__file__).parent / "read_rates.db")

print("=" * 60)
print("TESTING PERFORMANCE CALCULATION FIX")
print("=" * 60)

if Path(db_path).exists():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # OLD METHOD (averaging individual percentages)
    cursor.execute("""
        SELECT acl_event_cnt, acl_null_cnt 
        FROM read_rates 
        WHERE mds_fam_id = ? AND acl_event_cnt > 0
    """, ('674874972',))
    rows = cursor.fetchall()
    
    print(f"\nItem 674874972 has {len(rows)} records\n")
    
    # Calculate OLD way (wrong)
    old_percentages = [(null_cnt/event_cnt*100) for event_cnt, null_cnt in rows]
    old_avg_null_pct = sum(old_percentages) / len(old_percentages) if old_percentages else 0
    old_performance = 100 - old_avg_null_pct
    
    # Calculate NEW way (correct - weighted average)
    total_null_cnt = sum(row[1] for row in rows)
    total_event_cnt = sum(row[0] for row in rows)
    new_null_pct = (total_null_cnt / total_event_cnt * 100) if total_event_cnt > 0 else 0
    new_performance = 100 - new_null_pct
    
    print("OLD METHOD (averaging individual %):")
    print(f"  Average NULL %: {old_avg_null_pct:.2f}%")
    print(f"  Performance: {old_performance:.2f}%")
    print(f"  Would flag (< 85%): {old_performance < 85}")
    
    print("\nNEW METHOD (total nulls / total events):")
    print(f"  Total Events: {total_event_cnt}")
    print(f"  Total Nulls: {total_null_cnt}")
    print(f"  NULL %: {new_null_pct:.2f}%")
    print(f"  Performance: {new_performance:.2f}%")
    print(f"  WILL FLAG (< 85%): {new_performance < 85}")
    
    conn.close()
else:
    print(f"Database not found at {db_path}")

print("\n" + "=" * 60)
print("Now testing with actual functions...")
print("=" * 60 + "\n")

from delivery_analysis import get_delivery_po_data
from main import load_read_rates_for_items, get_avg_performance, get_recommendation

# Fetch delivery data
print("=" * 60)
print("DEBUGGING ITEM 674874972 on DELIVERY 11008711")
print("=" * 60)

delivery_result = get_delivery_po_data('11008711')
mds_ids = delivery_result.get('mds_fam_ids', [])
print(f"\n[1] Total unique MDS_FAM_IDs in delivery: {len(mds_ids)}")
print(f"[2] Item 674874972 in delivery: {'674874972' in mds_ids}")

# Load read rates
print(f"\n[3] Loading read rates for all {len(mds_ids)} items...")
read_rates = load_read_rates_for_items(mds_ids)
print(f"[4] Read rates loaded for {len(read_rates)} items")

# Check if item has read rates
has_item = '674874972' in read_rates
print(f"\n[5] Item 674874972 has read rates: {has_item}")

if has_item:
    item_rates = read_rates['674874972']
    print(f"[6] Item 674874972 has {len(item_rates)} rate records")
    
    # Calculate average performance
    avg_perf = get_avg_performance(item_rates)
    print(f"[7] Item 674874972 average performance: {avg_perf:.1f}%")
    
    # Get recommendation
    recommendation, color, gradient = get_recommendation(avg_perf, "")
    print(f"[8] Recommendation: {recommendation} (color: {color})")
    
    # Check if it should be flagged
    should_flag = avg_perf < 85
    print(f"[9] Should be flagged (< 85%): {should_flag}")
    
    # Show some recent data points
    print(f"\n[10] Recent rate data:")
    for i, rate in enumerate(item_rates[-5:]):
        print(f"     {rate['date']}: {rate['null_pct']:.1f}% performance")
else:
    print("[ERROR] Item 674874972 NOT found in read rates!")
    print("\nChecking database directly...")
    
    import sqlite3
    from pathlib import Path
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    db_path = os.getenv("DATABASE_PATH", "")
    if not db_path:
        db_path = str(Path(__file__).parent / "read_rates.db")
    
    print(f"Database path: {db_path}")
    
    if Path(db_path).exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM read_rates WHERE mds_fam_id = ?", ('674874972',))
        count = cursor.fetchone()[0]
        print(f"Direct database query: Item 674874972 has {count} records")
        
        if count > 0:
            print("\n[ERROR] Database has records but load_read_rates_for_didn't return them!")
            print("This indicates a bug in load_read_rates_for_items()")
        
        conn.close()
    else:
        print(f"[ERROR] Database file not found at {db_path}")

print("\n" + "=" * 60)
