"""Multi-item batch reporting - TESTING FEATURE"""
import random
import sqlite3
import os
from pathlib import Path

def get_random_items(count: int = 3) -> list:
    """Randomly select N unique MDS_FAM_IDs from read_rates.db"""
    db_path = os.getenv("DATABASE_PATH", "read_rates.db")
    if not os.path.isabs(db_path):
        db_path = str(Path(__file__).parent / db_path)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all unique MDS_FAM_IDs
        cursor.execute("SELECT DISTINCT mds_fam_id FROM read_rates")
        all_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if len(all_ids) < count:
            return all_ids
        
        # Randomly select N unique IDs
        selected = random.sample(all_ids, count)
        return selected
    
    except Exception as e:
        print(f"[ERROR] get_random_items: {str(e)}")
        return []


def get_item_read_rate_data(mds_fam_id: str) -> dict:
    """Get all read rate data for an MDS_FAM_ID"""
    db_path = os.getenv("DATABASE_PATH", "read_rates.db")
    if not os.path.isabs(db_path):
        db_path = str(Path(__file__).parent / db_path)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all columns for this MDS_FAM_ID
        cursor.execute("""
            SELECT 
                id, acl_insert_date, ts_date, mds_fam_id, item1_desc, 
                pick_type_code, slot_id, vnpk_gtin_t,
                acl_event_cnt, acl_null_cnt, acl_bypass_cnt,
                good_read_cnt_null, good_read_cnt_bypass,
                item_num_read_cnt_null, item_num_read_cnt_bypass,
                created_at
            FROM read_rates 
            WHERE mds_fam_id = ?
            ORDER BY ts_date DESC
        """, (str(mds_fam_id),))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Convert to list of dicts
        columns = [
            'id', 'acl_insert_date', 'ts_date', 'mds_fam_id', 'item1_desc',
            'pick_type_code', 'slot_id', 'vnpk_gtin_t',
            'acl_event_cnt', 'acl_null_cnt', 'acl_bypass_cnt',
            'good_read_cnt_null', 'good_read_cnt_bypass',
            'item_num_read_cnt_null', 'item_num_read_cnt_bypass',
            'created_at'
        ]
        
        data = [dict(zip(columns, row)) for row in rows]
        return {
            "mds_fam_id": mds_fam_id,
            "record_count": len(data),
            "records": data
        }
    
    except Exception as e:
        print(f"[ERROR] get_item_read_rate_data: {str(e)}")
        return {"mds_fam_id": mds_fam_id, "record_count": 0, "records": []}
