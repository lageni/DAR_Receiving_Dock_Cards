#!/usr/bin/env python
"""
SQLite Database initialization and migration from read_rates.csv
"""
import sqlite3
import csv
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Use DATABASE_PATH from .env if set, otherwise default to local
db_path_env = os.getenv('DATABASE_PATH', '')
if db_path_env:
    DB_PATH = Path(db_path_env)
else:
    DB_PATH = Path(__file__).parent / "read_rates.db"

# Create parent directories if they don't exist
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def create_database():
    """Create SQLite database schema for read_rates"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table with same structure as CSV
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS read_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acl_insert_date DATE NOT NULL,
            ts_date DATE NOT NULL,
            mds_fam_id TEXT NOT NULL,
            item1_desc TEXT,
            pick_type_code TEXT,
            slot_id TEXT,
            vnpk_gtin_t TEXT,
            acl_event_cnt INTEGER,
            acl_null_cnt INTEGER,
            acl_bypass_cnt INTEGER,
            good_read_cnt_null INTEGER,
            good_read_cnt_bypass INTEGER,
            item_num_read_cnt_null INTEGER,
            item_num_read_cnt_bypass INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(acl_insert_date, ts_date, mds_fam_id, slot_id)
        )
    ''')
    
    # Create indexes for faster lookups
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_mds_fam_id ON read_rates(mds_fam_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_acl_insert_date ON read_rates(acl_insert_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ts_date ON read_rates(ts_date)')
    
    conn.commit()
    conn.close()
    print(f"[OK] Database created: {DB_PATH}")

def migrate_from_csv(csv_path: str = "read_rates.csv"):
    """Migrate data from CSV to SQLite database"""
    csv_file = Path(csv_path)
    
    if not csv_file.exists():
        print(f"[ERROR] {csv_path} not found")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"[INFO] Migrating from {csv_path}...")
    
    rows_inserted = 0
    rows_skipped = 0
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    cursor.execute('''
                        INSERT INTO read_rates (
                            acl_insert_date, ts_date, mds_fam_id, item1_desc,
                            pick_type_code, slot_id, vnpk_gtin_t, acl_event_cnt,
                            acl_null_cnt, acl_bypass_cnt, good_read_cnt_null,
                            good_read_cnt_bypass, item_num_read_cnt_null,
                            item_num_read_cnt_bypass
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row.get('ACL_INSERT_DATE', ''),
                        row.get('TS_DATE', ''),
                        row.get('MDS_FAM_ID', ''),
                        row.get('ITEM1_DESC', ''),
                        row.get('PICK_TYPE_CODE', ''),
                        row.get('SLOT_ID', ''),
                        row.get('VNPK_GTIN_T', ''),
                        int(row.get('ACL_EVENT_CNT', 0)) if row.get('ACL_EVENT_CNT') else 0,
                        int(row.get('ACL_NULL_CNT', 0)) if row.get('ACL_NULL_CNT') else 0,
                        int(row.get('ACL_BYPASS_CNT', 0)) if row.get('ACL_BYPASS_CNT') else 0,
                        int(row.get('GOOD_READ_CNT_NULL', 0)) if row.get('GOOD_READ_CNT_NULL') else 0,
                        int(row.get('GOOD_READ_CNT_BYPASS', 0)) if row.get('GOOD_READ_CNT_BYPASS') else 0,
                        int(row.get('ITEM_NUM_READ_CNT_NULL', 0)) if row.get('ITEM_NUM_READ_CNT_NULL') else 0,
                        int(row.get('ITEM_NUM_READ_CNT_BYPASS', 0)) if row.get('ITEM_NUM_READ_CNT_BYPASS') else 0,
                    ))
                    rows_inserted += 1
                    
                    if rows_inserted % 10000 == 0:
                        print(f"  Processed {rows_inserted} rows...")
                
                except sqlite3.IntegrityError:
                    # Skip duplicates
                    rows_skipped += 1
                except Exception as e:
                    print(f"  [WARN] Row error: {e}")
                    rows_skipped += 1
        
        conn.commit()
        print(f"[OK] Migration complete!")
        print(f"  Inserted: {rows_inserted} rows")
        print(f"  Skipped: {rows_skipped} rows (duplicates)")
        return True
    
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()

def get_latest_date():
    """Get the latest ACL_INSERT_DATE in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT MAX(acl_insert_date) FROM read_rates')
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result[0] else None

def get_item_rates(item_id: str):
    """Get ACL rates for a specific item (by MDS_FAM_ID)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT ts_date, acl_event_cnt, acl_null_cnt
        FROM read_rates
        WHERE mds_fam_id = ?
        ORDER BY ts_date ASC
    ''', (item_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Convert to list of dicts for compatibility with existing code
    result = []
    for row in rows:
        if row['acl_event_cnt'] > 0:
            null_pct = (row['acl_null_cnt'] / row['acl_event_cnt']) * 100
            result.append({
                'date': row['ts_date'],
                'null_pct': null_pct,
                'event_cnt': row['acl_event_cnt'],
                'null_cnt': row['acl_null_cnt']
            })
    
    return result

def get_database_stats():
    """Get database statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM read_rates')
    total_rows = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT mds_fam_id) FROM read_rates')
    unique_items = cursor.fetchone()[0]
    
    cursor.execute('SELECT MIN(acl_insert_date), MAX(acl_insert_date) FROM read_rates')
    min_date, max_date = cursor.fetchone()
    
    conn.close()
    
    return {
        'total_rows': total_rows,
        'unique_items': unique_items,
        'min_date': min_date,
        'max_date': max_date
    }

def get_missing_partition_dates(days_back: int = 7):
    """Get list of dates from last N days that are missing from the database
    
    Useful for checking which recent partitions need to be synced from BigQuery
    """
    from datetime import datetime, timedelta
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all dates in the last N days that exist in database
    today = datetime.now().date()
    start_date = today - timedelta(days=days_back)
    
    cursor.execute('''
        SELECT DISTINCT acl_insert_date FROM read_rates
        WHERE acl_insert_date >= ?
        ORDER BY acl_insert_date DESC
    ''', (str(start_date),))
    
    existing_dates = set(row[0] for row in cursor.fetchall())
    conn.close()
    
    # Generate all dates in the range
    all_dates = set()
    current = start_date
    while current <= today:
        all_dates.add(str(current))
        current += timedelta(days=1)
    
    # Find missing dates
    missing_dates = sorted(list(all_dates - existing_dates), reverse=True)
    
    return {
        'missing_dates': missing_dates,
        'date_range': f"{start_date} to {today}",
        'days_missing': len(missing_dates),
        'existing_dates': sorted(list(existing_dates), reverse=True)
    }

if __name__ == "__main__":
    print("\n" + "="*60)
    print("CodePuppyDAR - SQLite Database Setup")
    print("="*60 + "\n")
    
    # Create database
    create_database()
    
    # Check if CSV exists
    csv_path = Path("read_rates.csv")
    if csv_path.exists():
        # Migrate from CSV
        migrate_from_csv()
        
        # Show stats
        stats = get_database_stats()
        print(f"\nDatabase Statistics:")
        print(f"  Total Rows: {stats['total_rows']:,}")
        print(f"  Unique Items: {stats['unique_items']:,}")
        print(f"  Date Range: {stats['min_date']} to {stats['max_date']}")
    else:
        print(f"\n[INFO] {csv_path} not found - skipping migration")
        print(f"[INFO] Database ready for Google Cloud sync")
    
    print("\n" + "="*60 + "\n")
