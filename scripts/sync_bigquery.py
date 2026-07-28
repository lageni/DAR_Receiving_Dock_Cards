#!/usr/bin/env python3
"""
BigQuery to SQLite Sync - Standalone CLI Script

Syncs missing dates from BigQuery ACL_READ_RATE table to local SQLite database.
Automatically detects missing dates and syncs only new data.

Usage:
    python sync_bigquery.py

Requirements:
    - Google Cloud credentials configured
    - VPN connection to Walmart network
    - .env file with DATABASE_PATH
    - BigQuery access to wmt-ambient-centeng.6068_Engineering.ACL_READ_RATE
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", r"L:\Engineering\DAR Docktag Cards\read_rates.db")


def get_database_stats():
    """Get current database statistics."""
    if not Path(DATABASE_PATH).exists():
        return {
            'total_rows': 0,
            'unique_items': 0,
            'min_date': 'N/A',
            'max_date': 'N/A'
        }
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Total rows
    cursor.execute("SELECT COUNT(*) FROM read_rates")
    total_rows = cursor.fetchone()[0]
    
    # Unique items
    cursor.execute("SELECT COUNT(DISTINCT mds_fam_id) FROM read_rates")
    unique_items = cursor.fetchone()[0]
    
    # Date range
    cursor.execute("SELECT MIN(acl_insert_date), MAX(acl_insert_date) FROM read_rates")
    min_date, max_date = cursor.fetchone()
    
    conn.close()
    
    return {
        'total_rows': total_rows,
        'unique_items': unique_items,
        'min_date': min_date or 'N/A',
        'max_date': max_date or 'N/A'
    }


def initialize_bigquery():
    """Initialize BigQuery client."""
    try:
        from google.cloud import bigquery
        
        print("[INIT] Initializing BigQuery client...")
        client = bigquery.Client()
        print("[OK] BigQuery client initialized")
        return client
    except Exception as e:
        print(f"[ERROR] Failed to initialize BigQuery: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure you're connected to Walmart VPN")
        print("  2. Check Google Cloud credentials are configured")
        print("  3. Verify you have access to wmt-ambient-centeng project")
        return None


def get_missing_dates(conn):
    """Calculate dates missing from database."""
    cursor = conn.cursor()
    
    # Get existing dates
    cursor.execute("SELECT DISTINCT acl_insert_date FROM read_rates ORDER BY acl_insert_date")
    existing_dates = {row[0] for row in cursor.fetchall()}
    
    # Get max date
    cursor.execute("SELECT MAX(acl_insert_date) FROM read_rates")
    max_date_str = cursor.fetchone()[0]
    
    if max_date_str:
        last_date = datetime.strptime(max_date_str, '%Y-%m-%d')
    else:
        # No data, start from 90 days ago
        last_date = datetime.now() - timedelta(days=90)
    
    # Find missing dates from last_date to today
    today = datetime.now()
    missing_dates = []
    current = last_date + timedelta(days=1)
    
    while current <= today:
        date_str = current.strftime('%Y-%m-%d')
        if date_str not in existing_dates:
            missing_dates.append(date_str)
        current += timedelta(days=1)
    
    return missing_dates


def sync_from_bigquery(client, missing_dates, conn):
    """Sync missing dates from BigQuery."""
    if not missing_dates:
        print("[OK] Database is current, no missing dates")
        return 0
    
    print(f"\n[SYNC] Found {len(missing_dates)} missing dates")
    print(f"       Range: {missing_dates[0]} to {missing_dates[-1]}")
    
    # Build BigQuery query
    dates_list = ", ".join([f'"{d}"' for d in missing_dates])
    query = f"""
        SELECT 
            acl_insert_date, 
            ts_date, 
            mds_fam_id, 
            slot_id, 
            acl_event_cnt, 
            acl_null_cnt, 
            acl_bypass_cnt, 
            good_read_cnt_null, 
            good_read_cnt_bypass, 
            item_num_read_cnt_null, 
            item_num_read_cnt_bypass, 
            item1_desc, 
            pick_type_code, 
            vnpk_gtin_t
        FROM `wmt-ambient-centeng.6068_Engineering.ACL_READ_RATE`
        WHERE PICK_TYPE_CODE NOT IN ('DPAL', 'LBSS')
        AND acl_insert_date IN ({dates_list})
    """
    
    print(f"\n[QUERY] Executing BigQuery query...")
    print(f"        Filtering: PICK_TYPE_CODE NOT IN ('DPAL', 'LBSS')")
    
    try:
        query_job = client.query(query)
        results = query_job.result()
        results_list = list(results)
        
        print(f"[OK] Query returned {len(results_list)} rows")
        
        if len(results_list) == 0:
            print(f"\n[WARNING] BigQuery returned 0 rows")
            print(f"          This may mean the dates only contain DPAL/LBSS pick types")
            return 0
        
        # Insert rows
        cursor = conn.cursor()
        inserted = 0
        duplicates = 0
        errors = 0
        
        insert_sql = '''
            INSERT OR IGNORE INTO read_rates (
                acl_insert_date, ts_date, mds_fam_id, slot_id, 
                acl_event_cnt, acl_null_cnt, acl_bypass_cnt, 
                good_read_cnt_null, good_read_cnt_bypass, 
                item_num_read_cnt_null, item_num_read_cnt_bypass, 
                item1_desc, pick_type_code, vnpk_gtin_t
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        print(f"\n[INSERT] Processing {len(results_list)} rows...")
        
        for i, row in enumerate(results_list, 1):
            try:
                values = (
                    str(row.acl_insert_date),
                    str(row.ts_date) if row.ts_date else None,
                    str(row.mds_fam_id),
                    str(row.slot_id) if row.slot_id else None,
                    int(row.acl_event_cnt) if row.acl_event_cnt else 0,
                    int(row.acl_null_cnt) if row.acl_null_cnt else 0,
                    int(row.acl_bypass_cnt) if row.acl_bypass_cnt else 0,
                    int(row.good_read_cnt_null) if row.good_read_cnt_null else 0,
                    int(row.good_read_cnt_bypass) if row.good_read_cnt_bypass else 0,
                    int(row.item_num_read_cnt_null) if row.item_num_read_cnt_null else 0,
                    int(row.item_num_read_cnt_bypass) if row.item_num_read_cnt_bypass else 0,
                    str(row.item1_desc) if row.item1_desc else None,
                    str(row.pick_type_code) if row.pick_type_code else None,
                    str(row.vnpk_gtin_t) if row.vnpk_gtin_t else None
                )
                
                cursor.execute(insert_sql, values)
                
                if cursor.rowcount > 0:
                    inserted += 1
                else:
                    duplicates += 1
                
                if i % 500 == 0:
                    print(f"         Progress: {i}/{len(results_list)} rows ({inserted} new, {duplicates} duplicates)")
            
            except Exception as e:
                errors += 1
                if errors <= 3:  # Only print first 3 errors
                    print(f"[ERROR] Row {i} failed: {e}")
        
        # Commit changes
        conn.commit()
        
        print(f"\n[RESULTS]")
        print(f"  Dates synced: {len(missing_dates)}")
        print(f"  BigQuery rows: {len(results_list)}")
        print(f"  Inserted: {inserted}")
        print(f"  Duplicates: {duplicates}")
        print(f"  Errors: {errors}")
        
        return inserted
    
    except Exception as e:
        print(f"\n[ERROR] BigQuery sync failed: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    """Main sync workflow."""
    print("\n" + "="*70)
    print("BigQuery to SQLite Sync - Standalone")
    print("="*70 + "\n")
    
    # Step 1: Check database
    print(f"[1/5] Checking database: {DATABASE_PATH}")
    if not Path(DATABASE_PATH).exists():
        print(f"[ERROR] Database not found at: {DATABASE_PATH}")
        print("\nPlease:")
        print("  1. Update DATABASE_PATH in .env file")
        print("  2. Or create the database first")
        sys.exit(1)
    
    stats = get_database_stats()
    print(f"[OK] Database found")
    print(f"     Total rows: {stats['total_rows']:,}")
    print(f"     Unique items: {stats['unique_items']:,}")
    print(f"     Date range: {stats['min_date']} to {stats['max_date']}")
    
    # Step 2: Initialize BigQuery
    print(f"\n[2/5] Initializing BigQuery...")
    client = initialize_bigquery()
    if not client:
        sys.exit(1)
    
    # Step 3: Connect to database
    print(f"\n[3/5] Connecting to database...")
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        print(f"[OK] Connected")
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        sys.exit(1)
    
    # Step 4: Find missing dates
    print(f"\n[4/5] Calculating missing dates...")
    missing_dates = get_missing_dates(conn)
    
    if not missing_dates:
        print("[OK] Database is up to date!")
        conn.close()
        print("\n" + "="*70)
        print("SYNC COMPLETE - No changes needed")
        print("="*70 + "\n")
        return
    
    # Step 5: Sync from BigQuery
    print(f"\n[5/5] Syncing from BigQuery...")
    inserted = sync_from_bigquery(client, missing_dates, conn)
    
    conn.close()
    
    # Final summary
    print("\n" + "="*70)
    if inserted > 0:
        print(f"SYNC COMPLETE - {inserted} rows added!")
    else:
        print("SYNC COMPLETE - No rows added")
    print("="*70 + "\n")
    
    # Show updated stats
    updated_stats = get_database_stats()
    print("Updated Database Stats:")
    print(f"  Total rows: {updated_stats['total_rows']:,}")
    print(f"  Unique items: {updated_stats['unique_items']:,}")
    print(f"  Date range: {updated_stats['min_date']} to {updated_stats['max_date']}")
    print()


if __name__ == "__main__":
    main()
