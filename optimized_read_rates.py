"""Optimized read rates loading - only query items we need"""

def load_read_rates_for_items(mds_fam_ids: list) -> dict:
    """Load read rates ONLY for specific mds_fam_ids (SQL filtering).
    
    This is much faster than loading all 131k items and filtering in Python.
    
    Args:
        mds_fam_ids: List of mds_fam_id values to query
        
    Returns:
        dict[mds_fam_id] -> list of rate records
    """
    from pathlib import Path
    from collections import defaultdict
    import sqlite3
    
    if not mds_fam_ids:
        return {}
    
    db_path = "L:\\Engineering\\DAR Docktag Cards\\read_rates.db"
    
    if not Path(db_path).exists():
        print(f"[WARNING] Database not found at {db_path}")
        return {}
    
    rates_by_family = defaultdict(list)
    
    try:
        conn = sqlite3.connect(db_path)
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
        
        cursor.execute(query, mds_fam_ids)
        
        for row in cursor.fetchall():
            mds_fam_id, insert_date, event_cnt, null_cnt = row
            if mds_fam_id and event_cnt and event_cnt > 0:
                null_pct = (null_cnt / event_cnt) * 100 if null_cnt else 0
                rates_by_family[str(mds_fam_id)].append({
                    "date": str(insert_date),
                    "null_pct": null_pct,
                    "event_cnt": event_cnt,
                    "null_cnt": null_cnt
                })
        
        conn.close()
        print(f"[OPTIMIZED] Loaded {len(rates_by_family)} items (queried only {len(mds_fam_ids)} specific items)")
        
    except Exception as e:
        print(f"[ERROR] Loading read rates for items: {e}")
        return {}
    
    return rates_by_family


# Add this function to main.py after the load_read_rates() function
