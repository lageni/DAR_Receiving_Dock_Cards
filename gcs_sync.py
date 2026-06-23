#!/usr/bin/env python
"""
Google Cloud BigQuery sync for read_rates data
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict

DB_PATH = Path(__file__).parent / "read_rates.db"

class GoogleCloudSync:
    """Handle syncing ACL data from Google Cloud BigQuery"""
    
    def __init__(self):
        # Hard-coded defaults
        self.project_id = "wmt-ambient-centeng"
        self.dataset_id = "6068_Engineering"
        self.table_id = "ACL_READ_RATE"
        self.client = None
        self.last_sync = None
    
    def initialize(self, project_id: str = None, dataset_id: str = None, table_id: str = None):
        """Initialize BigQuery connection (uses defaults if not specified)"""
        try:
            from google.cloud import bigquery
            # Use provided values or fall back to defaults
            self.project_id = project_id or "wmt-ambient-centeng"
            self.dataset_id = dataset_id or "6068_Engineering"
            self.table_id = table_id or "ACL_READ_RATE"
            self.client = bigquery.Client(project=self.project_id)
            print(f"[OK] BigQuery client initialized")
            return True
        except ImportError:
            print(f"[ERROR] google-cloud-bigquery not installed")
            print(f"  Run: pip install google-cloud-bigquery")
            return False
        except Exception as e:
            print(f"[ERROR] Failed to initialize BigQuery: {e}")
            return False
    
    def test_connection(self) -> Dict:
        """Test BigQuery connection and return status"""
        if not self.client:
            return {'status': 'error', 'message': 'Client not initialized'}
        
        try:
            # Try a simple query to list tables
            dataset = self.client.get_dataset(self.dataset_id)
            tables = list(self.client.list_tables(dataset))
            
            # Check if our target table exists
            table_exists = any(t.table_id == self.table_id for t in tables)
            
            if table_exists:
                # Try a simple query to get row count
                query = f"SELECT COUNT(*) as cnt FROM `{self.project_id}.{self.dataset_id}.{self.table_id}` LIMIT 1"
                query_job = self.client.query(query)
                result = query_job.result()
                row_count = next(result).cnt
                
                return {
                    'status': 'ok',
                    'message': f'Connected successfully',
                    'project_id': self.project_id,
                    'dataset_id': self.dataset_id,
                    'table_id': self.table_id,
                    'table_rows': row_count
                }
            else:
                return {
                    'status': 'error',
                    'message': f'Table {self.table_id} not found in dataset {self.dataset_id}'
                }
        
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_latest_local_date(self) -> str:
        """Get the latest ACL_INSERT_DATE from local SQLite database"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT MAX(acl_insert_date) FROM read_rates')
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result[0] else '2000-01-01'
    
    def fetch_new_rows(self, since_date: str = None) -> List[Dict]:
        """Fetch new rows from Google Cloud BigQuery since a date"""
        if not self.client:
            print("[ERROR] BigQuery client not initialized")
            return []
        
        if since_date is None:
            since_date = self.get_latest_local_date()
        
        print(f"[INFO] Fetching rows from BigQuery since {since_date}...")
        
        try:
            query = f"""
                SELECT 
                    ACL_INSERT_DATE, TS_DATE, MDS_FAM_ID, ITEM1_DESC,
                    PICK_TYPE_CODE, SLOT_ID, VNPK_GTIN_T, ACL_EVENT_CNT,
                    ACL_NULL_CNT, ACL_BYPASS_CNT, GOOD_READ_CNT_NULL,
                    GOOD_READ_CNT_BYPASS, ITEM_NUM_READ_CNT_NULL,
                    ITEM_NUM_READ_CNT_BYPASS
                FROM `{self.project_id}.{self.dataset_id}.{self.table_id}`
                WHERE ACL_INSERT_DATE > '{since_date}'
                ORDER BY ACL_INSERT_DATE DESC
            """
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            rows = []
            for row in results:
                rows.append({
                    'acl_insert_date': row.ACL_INSERT_DATE,
                    'ts_date': row.TS_DATE,
                    'mds_fam_id': row.MDS_FAM_ID,
                    'item1_desc': row.ITEM1_DESC,
                    'pick_type_code': row.PICK_TYPE_CODE,
                    'slot_id': row.SLOT_ID,
                    'vnpk_gtin_t': row.VNPK_GTIN_T,
                    'acl_event_cnt': row.ACL_EVENT_CNT,
                    'acl_null_cnt': row.ACL_NULL_CNT,
                    'acl_bypass_cnt': row.ACL_BYPASS_CNT,
                    'good_read_cnt_null': row.GOOD_READ_CNT_NULL,
                    'good_read_cnt_bypass': row.GOOD_READ_CNT_BYPASS,
                    'item_num_read_cnt_null': row.ITEM_NUM_READ_CNT_NULL,
                    'item_num_read_cnt_bypass': row.ITEM_NUM_READ_CNT_BYPASS,
                })
            
            print(f"[OK] Fetched {len(rows)} rows from BigQuery")
            return rows
        
        except Exception as e:
            print(f"[ERROR] BigQuery fetch failed: {e}")
            return []
    
    def append_to_database(self, rows: List[Dict]) -> Dict:
        """Append rows to SQLite database"""
        if not rows:
            print("[INFO] No rows to append")
            return {'inserted': 0, 'skipped': 0, 'errors': 0}
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        inserted = 0
        skipped = 0
        errors = 0
        
        for row in rows:
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
                    row['acl_insert_date'],
                    row['ts_date'],
                    row['mds_fam_id'],
                    row.get('item1_desc'),
                    row.get('pick_type_code'),
                    row.get('slot_id'),
                    row.get('vnpk_gtin_t'),
                    row.get('acl_event_cnt', 0),
                    row.get('acl_null_cnt', 0),
                    row.get('acl_bypass_cnt', 0),
                    row.get('good_read_cnt_null', 0),
                    row.get('good_read_cnt_bypass', 0),
                    row.get('item_num_read_cnt_null', 0),
                    row.get('item_num_read_cnt_bypass', 0),
                ))
                inserted += 1
                
                if inserted % 1000 == 0:
                    print(f"  Inserted {inserted} rows...")
            
            except sqlite3.IntegrityError:
                skipped += 1
            except Exception as e:
                errors += 1
                print(f"  [WARN] Row insert error: {e}")
        
        conn.commit()
        conn.close()
        
        self.last_sync = datetime.now()
        
        print(f"[OK] Append complete!")
        print(f"  Inserted: {inserted} rows")
        print(f"  Skipped: {skipped} rows (duplicates)")
        print(f"  Errors: {errors} rows")
        
        return {'inserted': inserted, 'skipped': skipped, 'errors': errors}
    
    def sync_specific_dates(self, dates: List[str]) -> Dict:
        """Sync specific dates from BigQuery using the ACL_READ_RATE table
        
        Args:
            dates: List of dates in YYYY-MM-DD format to sync
        
        Returns:
            Dict with sync results
        """
        if not self.client:
            return {'status': 'error', 'message': 'BigQuery not initialized'}
        
        if not dates:
            return {'status': 'error', 'message': 'No dates provided'}
        
        try:
            # Format dates as SQL IN clause: {"2026-01-01", "2026-01-02"}
            date_list = ', '.join([f'"{d}"' for d in sorted(dates)])
            
            # Use the provided query
            query = f"""
                SELECT * FROM `{self.project_id}.{self.dataset_id}.{self.table_id}`
                WHERE PICK_TYPE_CODE NOT IN ('DPAL', 'LBSS')
                AND ACL_INSERT_DATE IN ({date_list})
            """
            
            print(f"[INFO] Fetching {len(dates)} date partitions from BigQuery...")
            query_job = self.client.query(query)
            results = query_job.result()
            
            # Convert results to list of dicts
            rows = []
            for row in results:
                rows.append({
                    'acl_insert_date': str(row.ACL_INSERT_DATE),
                    'ts_date': str(row.TS_DATE),
                    'mds_fam_id': row.MDS_FAM_ID,
                    'item1_desc': row.ITEM1_DESC,
                    'pick_type_code': row.PICK_TYPE_CODE,
                    'slot_id': row.SLOT_ID,
                    'vnpk_gtin_t': row.VNPK_GTIN_T,
                    'acl_event_cnt': row.ACL_EVENT_CNT,
                    'acl_null_cnt': row.ACL_NULL_CNT,
                    'acl_bypass_cnt': row.ACL_BYPASS_CNT,
                    'good_read_cnt_null': row.GOOD_READ_CNT_NULL,
                    'good_read_cnt_bypass': row.GOOD_READ_CNT_BYPASS,
                    'item_num_read_cnt_null': row.ITEM_NUM_READ_CNT_NULL,
                    'item_num_read_cnt_bypass': row.ITEM_NUM_READ_CNT_BYPASS,
                })
            
            print(f"[OK] Fetched {len(rows)} rows from BigQuery")
            result = self.append_to_database(rows)
            result['status'] = 'success'
            result['last_sync'] = self.last_sync.isoformat() if self.last_sync else None
            return result
        
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def sync(self, since_date: str = None) -> Dict:
        """Full sync: fetch from BigQuery and append to database"""
        if not self.client:
            return {'status': 'error', 'message': 'BigQuery not initialized'}
        
        rows = self.fetch_new_rows(since_date)
        result = self.append_to_database(rows)
        result['status'] = 'success'
        result['last_sync'] = self.last_sync.isoformat() if self.last_sync else None
        
        return result

# Global instance
_sync_client = GoogleCloudSync()

def initialize_google_cloud(project_id: str, dataset_id: str, table_id: str) -> bool:
    """Initialize Google Cloud connection"""
    return _sync_client.initialize(project_id, dataset_id, table_id)

def sync_from_google_cloud(since_date: str = None) -> Dict:
    """Sync data from Google Cloud BigQuery"""
    return _sync_client.sync(since_date)

def get_sync_status() -> Dict:
    """Get sync status information"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT MAX(acl_insert_date) FROM read_rates')
    latest_date = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM read_rates')
    total_rows = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'gcs_initialized': _sync_client.client is not None,
        'last_sync': _sync_client.last_sync.isoformat() if _sync_client.last_sync else None,
        'latest_data_date': latest_date,
        'total_rows': total_rows
    }

def test_gcs_connection(project_id: str = None, dataset_id: str = None, table_id: str = None) -> Dict:
    """Test Google Cloud BigQuery connection"""
    if project_id and dataset_id and table_id:
        # Initialize if credentials provided
        _sync_client.initialize(project_id, dataset_id, table_id)
    
    return _sync_client.test_connection()

def sync_specific_dates_from_gcs(dates: List[str]) -> Dict:
    """Sync specific date partitions from BigQuery
    
    Args:
        dates: List of dates in YYYY-MM-DD format
    
    Returns:
        Sync result dict
    """
    # Ensure client is initialized
    if not _sync_client.client:
        _sync_client.initialize()
    
    return _sync_client.sync_specific_dates(dates)
