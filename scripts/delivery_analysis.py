"""Delivery Analysis - Query Informix and apply batching to all mds_fam_ids"""
import os
import time
import sqlite3
from pathlib import Path
from informix_connect import InformixConnection
from batch_report import get_item_read_rate_data
from cache_manager import get_cache_manager


class ProgressTracker:
    """Track and log progress through the analysis"""
    
    def __init__(self):
        self.stages = []
        self.start_time = time.time()
    
    def log(self, stage: str, message: str):
        """Log a stage with elapsed time"""
        elapsed = time.time() - self.start_time
        entry = {
            "time": elapsed,
            "stage": stage,
            "message": message
        }
        self.stages.append(entry)
        print(f"[DELIVERY-ANALYSIS] [{stage}] {message} (elapsed: {elapsed:.2f}s)")
    
    def get_logs(self) -> str:
        """Get all logs formatted for browser console"""
        lines = ["\n=== DELIVERY ANALYSIS PROGRESS ==="]
        for entry in self.stages:
            lines.append(f"{entry['time']:.2f}s [{entry['stage']}] {entry['message']}")
        lines.append("="*35 + "\n")
        return "\n".join(lines)


def get_delivery_po_data(delivery_number: str, progress: ProgressTracker = None) -> dict:
    """Query Informix for all PO lines for a given delivery number.
    
    Returns dict with:
    - success: bool
    - data: list of rows (each with mds_fam_id, po_nbr, etc.)
    - error: error message if failed
    - record_count: number of rows returned
    """
    
    if not progress:
        progress = ProgressTracker()
    
    progress.log("QUERY", "Starting delivery analysis for: " + str(delivery_number))
    
    # Check cache first
    cache = get_cache_manager()
    cache_key = f"delivery_{delivery_number}"
    cached_result = cache.get(cache_key, category="deliveries")
    
    if cached_result:
        progress.log("QUERY", "Using cached data (2 days fresh)")
        cached_result['progress'] = progress
        return cached_result
    
    progress.log("QUERY", "Cache miss - querying Informix")
    
    # Build the query (updated to include freight_bill_qty and trailer info)
    query = f"""
    select
        rcv.appointment_nbr as delivery_nbr,
        bill.freight_bill_qty,
        bill.tr_visual_trailer as trailer,
        po.po_type_code,
        po.po_dept_nbr,
        po.po_order_date,
        po.event,
        po.vndr_nbr,
        po.ship_date,
        po.cancel_date,
        po.status,
        po.pur_ord_id,
        po.po_nbr,
        po.must_arrive_by_dt,
        line.po_line_nbr,
        line.mds_fam_id,
        line.vendor_stock_id,
        line.whpk_order_qty,
        line.whpk_max_rcv_qty,
        line.status as line_status
    from dc_common:informix.purchase_order po
    inner join dc_common:informix.po_line line on po.pur_ord_id = line.pur_ord_id
    left join rdc_db:informix.dc_receiver rcv on po.po_nbr = rcv.po_nbr
        and po.pur_ord_id = rcv.pur_ord_id
    left join dc_common:informix.dc_freight_bill bill on bill.appointment_nbr = rcv.appointment_nbr
        and bill.frt_bill_nbr = rcv.frt_bill_nbr
    where po.must_arrive_by_dt > today - 60
    and mod(po.po_type_code, 2) = 1
    and rcv.appointment_nbr = {delivery_number}
    """
    
    try:
        query_start = time.time()
        conn = InformixConnection()
        conn.connect()
        progress.log("QUERY", "Connected to Informix")
        
        results = conn.execute_query(query)
        conn.disconnect()
        
        query_elapsed = time.time() - query_start
        progress.log("QUERY", f"Query completed: {len(results)} rows in {query_elapsed:.2f}s")
        
        # Extract unique mds_fam_ids for batching
        mds_fam_ids = list(set(str(row['mds_fam_id']) for row in results if row.get('mds_fam_id')))
        progress.log("EXTRACT", f"Found {len(mds_fam_ids)} unique mds_fam_ids")
        
        result = {
            "success": True,
            "data": results,
            "record_count": len(results),
            "mds_fam_ids": mds_fam_ids,
            "error": None,
            "progress": progress
        }
        
        # Cache the result (without progress object)
        cache_data = {k: v for k, v in result.items() if k != 'progress'}
        cache.set(cache_key, cache_data, category="deliveries")
        progress.log("CACHE", "Data cached for 2 days")
        
        return result
    
    except Exception as e:
        progress.log("ERROR", f"Informix query failed: {str(e)}")
        return {
            "success": False,
            "data": [],
            "record_count": 0,
            "mds_fam_ids": [],
            "error": f"Query failed: {str(e)}",
            "progress": progress
        }


def batch_get_read_rates(mds_fam_ids: list, progress: ProgressTracker) -> dict:
    """Efficiently batch-load read rate data - SQL FILTERING (FAST!)
    
    Pre-filters at SQL level to only load items with avg performance < 85%.
    This avoids loading data for ACL-approved items.
    """
    batching_data = {}
    
    if not mds_fam_ids:
        return batching_data
    
    progress.log("BATCH", f"Loading read rate data for {len(mds_fam_ids)} items (SQL-optimized)")
    batch_start = time.time()
    
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path("L:\Engineering\DAR Docktag Cards\read_rates.db")
        if not db_path.exists():
            progress.log("BATCH", f"Database not found at {db_path} - skipping read rates")
            return batching_data
        
        progress.log("BATCH", f"Opening database (read-only): {db_path}")
        
        # Use context manager with read-only mode and timeout
        db_uri = f"file:{db_path}?mode=ro&timeout=20000"
        
        with sqlite3.connect(db_uri, uri=True, timeout=20.0) as conn:
            conn.row_factory = None
            cursor = conn.cursor()
            
            # Create placeholders for SQL IN clause
            placeholders = ','.join('?' * len(mds_fam_ids))
            
            # Query with PERFORMANCE PRE-FILTERING at SQL level!
            # Only loads items where avg(null_pct) < 85 (problematic items)
            query = f"""
                WITH item_performance AS (
                    SELECT 
                        mds_fam_id,
                        AVG(CAST(acl_null_cnt AS FLOAT) / CAST(acl_event_cnt AS FLOAT) * 100) as avg_performance
                    FROM read_rates
                    WHERE mds_fam_id IN ({placeholders})
                      AND acl_event_cnt > 0
                    GROUP BY mds_fam_id
                    HAVING avg_performance < 85  -- Only load problematic items!
                )
                SELECT r.mds_fam_id, r.acl_insert_date, r.acl_event_cnt, r.acl_null_cnt
                FROM read_rates r
                INNER JOIN item_performance p ON r.mds_fam_id = p.mds_fam_id
                WHERE r.acl_event_cnt > 0
                ORDER BY r.mds_fam_id, r.acl_insert_date
            """
            
            progress.log("BATCH", f"Executing query for {len(mds_fam_ids)} items...")
            cursor.execute(query, mds_fam_ids)
            
            rows = cursor.fetchall()
            progress.log("BATCH", f"Query returned {len(rows)} rows")
            
            # Group results by mds_fam_id
            from collections import defaultdict
            rates_by_id = defaultdict(list)
            
            for row in rows:
                mds_fam_id, insert_date, event_cnt, null_cnt = row
                if event_cnt and event_cnt > 0:
                    null_pct = (null_cnt / event_cnt) * 100 if null_cnt else 0
                    rates_by_id[str(mds_fam_id)].append({
                        "date": str(insert_date),
                        "null_pct": null_pct,
                        "event_cnt": event_cnt,
                        "null_cnt": null_cnt
                    })
        
        # Connection auto-closed by context manager
        progress.log("BATCH", "Database connection closed")
        
        # Build batching_data structure
        for mds_id, records in rates_by_id.items():
            batching_data[mds_id] = {
                "mds_fam_id": mds_id,
                "record_count": len(records),
                "records": records
            }
        
        batch_elapsed = time.time() - batch_start
        progress.log("BATCH", f"SQL-optimized: Loaded {len(batching_data)} problematic items (< 85% perf) in {batch_elapsed:.2f}s")
        progress.log("BATCH", f"Skipped {len(mds_fam_ids) - len(batching_data)} ACL-approved items (no DB query!)")
        
    except Exception as e:
        progress.log("BATCH", f"Error in SQL batch load: {str(e)}")
        # Fall back to empty data
    
    return batching_data



def apply_freight_proportions(data: list) -> list:
    """Adjust whpk_order_qty based on freight_bill_qty proportions.
    
    When a PO is split, each line shows full PO qty, but freight_bill_qty 
    shows only THIS delivery's share. Calculates adjusted qty per delivery.
    """
    if not data:
        return data
    
    # Group by po_nbr
    po_groups = {}
    for row in data:
        po_nbr = row.get('po_nbr')
        if po_nbr not in po_groups:
            po_groups[po_nbr] = {'lines': [], 'freight': 0, 'total_whpk': 0}
        po_groups[po_nbr]['lines'].append(row)
        po_groups[po_nbr]['freight'] = row.get('freight_bill_qty', 0)
        try:
            whpk = int(row.get('whpk_order_qty', 0)) if isinstance(row.get('whpk_order_qty'), (int, str)) else 0
            po_groups[po_nbr]['total_whpk'] += whpk
        except:
            pass
    
    # Apply adjustment
    for row in data:
        po_nbr = row.get('po_nbr')
        group = po_groups.get(po_nbr, {})
        freight = group.get('freight', 0)
        total_whpk = group.get('total_whpk', 1)
        try:
            original_qty = int(row.get('whpk_order_qty', 0)) if isinstance(row.get('whpk_order_qty'), (int, str)) else 0
            if total_whpk > 0 and original_qty > 0:
                row['whpk_adjusted_qty'] = int(original_qty * freight / total_whpk)
            else:
                row['whpk_adjusted_qty'] = original_qty
        except:
            row['whpk_adjusted_qty'] = row.get('whpk_order_qty', 0)
    
    return data


def apply_batching_to_delivery(delivery_data: dict) -> dict:
    """Apply batching and freight proportions to delivery data."""
    
    progress = delivery_data.get("progress", ProgressTracker())
    
    if not delivery_data.get("success"):
        progress.log("ERROR", "Skipping batching due to query failure")
        return delivery_data
    
    # Apply freight proportions first
    progress.log("FREIGHT", "Applying freight proportions to line quantities")
    delivery_data["data"] = apply_freight_proportions(delivery_data.get("data", []))
    
    # Then load batching data
    progress.log("BATCH", "Starting batch load of read rate data")
    batching_data = batch_get_read_rates(delivery_data.get("mds_fam_ids", []), progress)
    
    # Augment rows
    progress.log("AUGMENT", f"Augmenting {len(delivery_data['data'])} rows with batching data")
    enriched_data = []
    for row in delivery_data["data"]:
        mds_fam_id = str(row.get("mds_fam_id", ""))
        row["batching_info"] = batching_data.get(mds_fam_id, {})
        enriched_data.append(row)
    
    delivery_data["data"] = enriched_data
    delivery_data["batching_data"] = batching_data
    
    progress.log("AUGMENT", f"All {len(enriched_data)} rows augmented")
    progress.log("COMPLETE", "Delivery analysis complete")
    
    return delivery_data
