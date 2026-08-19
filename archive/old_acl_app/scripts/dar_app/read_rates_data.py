"""Read-rate data access: DB path resolution + SQLite loading/caching."""
import os
import sqlite3
from collections import defaultdict
from pathlib import Path

from dar_app.logging_setup import logger

def get_database_path():
    """Get read_rates.db path from .env (DATABASE_PATH) or use default.
    
    Priority:
    1. DATABASE_PATH from .env (absolute or relative)
    2. Default: read_rates.db in same directory as app
    """
    db_path = os.getenv("DATABASE_PATH", "").strip()
    
    # Use repr() to safely log paths with backslashes
    logger.info(f"[DB-PATH] DATABASE_PATH from env: {repr(db_path)}")
    logger.info(f"[DB-PATH] __file__ location: {Path(__file__).parent.as_posix()}")
    
    if not db_path:
        # Default to local directory
        db_path = str(Path(__file__).parent / "read_rates.db")
        logger.info(f"[DB-PATH] Using default path: {Path(db_path).as_posix()}")
    elif not os.path.isabs(db_path):
        # Relative path - make it absolute from app directory
        db_path = str(Path(__file__).parent / db_path)
        logger.info(f"[DB-PATH] Converted relative to absolute: {Path(db_path).as_posix()}")
    else:
        logger.info(f"[DB-PATH] Using absolute path from .env: {Path(db_path).as_posix()}")
    
    return db_path

# Cache for read rates data
_read_rates_cache = None
def load_read_rates():
    """Load read rates from read_rates.db (SQLite). Returns dict[mds_fam_id] -> list of records."""
    global _read_rates_cache
    if _read_rates_cache is not None:
        print("[DB-READ] Using cached read rates (already loaded)")
        return _read_rates_cache
    
    db_path = get_database_path()
    print(f"[DB-READ-ALL] Loading ALL items from database: {db_path}")
    
    if not Path(db_path).exists():
        print(f"[DB-READ-ALL-ERROR] Database not found at {db_path}")
        return {}
    
    rates_by_family = defaultdict(list)
    try:
        # Use context manager with read-only mode and timeout
        db_uri = f"file:{db_path}?mode=ro&timeout=20000"
        
        with sqlite3.connect(db_uri, uri=True, timeout=20.0) as conn:
            conn.row_factory = None
            cursor = conn.cursor()
            
            print("[DB-READ-ALL] Executing query to load all read rates...")
            # Query: get all rows grouped by mds_fam_id, sorted by date
            cursor.execute("""
                SELECT mds_fam_id, acl_insert_date, acl_event_cnt, acl_null_cnt
                FROM read_rates
                ORDER BY mds_fam_id, acl_insert_date
            """)
            
            rows = cursor.fetchall()
            print(f"[DB-READ-ALL] Fetched {len(rows)} total rows from database")
            
            row_count = 0
            for row in rows:
                mds_fam_id, insert_date, event_cnt, null_cnt = row
                if mds_fam_id and event_cnt and event_cnt > 0:
                    null_pct = (null_cnt / event_cnt) * 100 if null_cnt else 0
                    rates_by_family[str(mds_fam_id)].append({
                        "date": str(insert_date),
                        "null_pct": null_pct,
                        "event_cnt": event_cnt,
                        "null_cnt": null_cnt
                    })
                    row_count += 1
            
            print(f"[DB-READ-ALL] Processed {row_count} valid rows into {len(rates_by_family)} items")
        
        _read_rates_cache = rates_by_family
        print(f"[DB-READ-ALL] SUCCESS - Cached {len(rates_by_family)} items for future use")
        
    except sqlite3.OperationalError as e:
        print(f"[DB-READ-ALL-ERROR] SQLite operational error (possibly locked): {e}")
        import traceback
        traceback.print_exc()
        _read_rates_cache = {}
    except Exception as e:
        print(f"[DB-READ-ALL-ERROR] Unexpected error: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        _read_rates_cache = {}
    
    return _read_rates_cache


def load_read_rates_for_items(mds_fam_ids: list) -> dict:
    """Load read rates ONLY for specific mds_fam_ids (SQL filtering - MUCH FASTER!).
    
    This avoids loading all 131k items when we only need a few hundred.
    
    Args:
        mds_fam_ids: List of mds_fam_id values to query
        
    Returns:
        dict[mds_fam_id] -> list of rate records
    """
    if not mds_fam_ids:
        logger.info("[DB-READ] No items requested - returning empty dict")
        return {}
    
    # CRITICAL: Convert all IDs to strings (database stores as TEXT)
    mds_fam_ids = [str(item_id) for item_id in mds_fam_ids]
    
    db_path = get_database_path()
    logger.info(f"[DB-READ] Querying database: {Path(db_path).as_posix()}")
    
    if not Path(db_path).exists():
        logger.error(f"[DB-READ-ERROR] Database file not found at {Path(db_path).as_posix()}")
        return {}
    
    logger.info(f"[DB-READ] Requesting data for {len(mds_fam_ids)} items")
    logger.info(f"[DB-READ] First 10 items: {mds_fam_ids[:10]}")
    logger.info(f"[DB-READ] Sample ID type: {type(mds_fam_ids[0]).__name__} (should be 'str')")
    
    rates_by_family = defaultdict(list)
    
    try:
        # Use context manager for automatic connection cleanup
        # URI mode with timeout and read-only for multi-process safety
        db_uri = f"file:{db_path}?mode=ro&timeout=20000"  # 20 second timeout, read-only
        
        with sqlite3.connect(db_uri, uri=True, timeout=20.0) as conn:
            conn.row_factory = None  # Use tuples for speed
            cursor = conn.cursor()
            
            # Create placeholders for SQL IN clause
            placeholders = ','.join('?' * len(mds_fam_ids))
            
            # Query ONLY the items we need (SQL-level filtering!)
            query = f"""
                SELECT mds_fam_id, acl_insert_date, acl_event_cnt, acl_null_cnt
                FROM read_rates
                WHERE mds_fam_id IN ({placeholders})
                ORDER BY mds_fam_id, acl_insert_date
            """
            
            logger.info(f"[DB-READ] Executing query with {len(mds_fam_ids)} parameters...")
            cursor.execute(query, mds_fam_ids)
            
            rows = cursor.fetchall()
            logger.info(f"[DB-READ] Query returned {len(rows)} total rows")
            
            if len(rows) == 0:
                # DEBUG: Test with a few known IDs to see if DB is readable
                logger.warning(f"[DB-READ-DEBUG] Testing with known items...")
                test_query = "SELECT COUNT(*) FROM read_rates WHERE mds_fam_id IN (?, ?, ?)"
                cursor.execute(test_query, ('550508254', '674874972', '570741739'))
                test_count = cursor.fetchone()[0]
                logger.warning(f"[DB-READ-DEBUG] Known items test: {test_count} records found")
                logger.warning(f"[DB-READ-DEBUG] First 20 IDs we tried: {mds_fam_ids[:20]}")
            
            row_count = 0
            for row in rows:
                mds_fam_id, insert_date, event_cnt, null_cnt = row
                if mds_fam_id and event_cnt and event_cnt > 0:
                    null_pct = (null_cnt / event_cnt) * 100 if null_cnt else 0
                    rates_by_family[str(mds_fam_id)].append({
                        "date": str(insert_date),
                        "null_pct": null_pct,
                        "event_cnt": event_cnt,
                        "null_cnt": null_cnt
                    })
                    row_count += 1
            
            logger.info(f"[DB-READ] Processed {row_count} valid rows into {len(rates_by_family)} items")
            
            # Log sample data for verification
            if rates_by_family:
                sample_id = list(rates_by_family.keys())[0]
                sample_count = len(rates_by_family[sample_id])
                logger.info(f"[DB-READ] Sample: Item {sample_id} has {sample_count} records")
            else:
                logger.warning(f"[DB-READ-WARNING] No data found for any of the {len(mds_fam_ids)} requested items!")
        
        # Connection auto-closed by context manager
        logger.info(f"[DB-READ] SUCCESS - Loaded {len(rates_by_family)} items from database")
        
    except sqlite3.OperationalError as e:
        logger.error(f"[DB-READ-ERROR] SQLite operational error (possibly locked): {e}")
        logger.error(f"[DB-READ-ERROR] Database path: {db_path}")
        import traceback
        logger.error(traceback.format_exc())
        return {}
    except Exception as e:
        logger.error(f"[DB-READ-ERROR] Unexpected error loading read rates: {type(e).__name__} - {e}")
        logger.error(f"[DB-READ-ERROR] Database path: {db_path}")
        import traceback
        logger.error(traceback.format_exc())
        return {}
    
    return rates_by_family
