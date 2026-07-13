"""Delivery Analysis - Query Informix and apply batching to all mds_fam_ids"""
import os
import time
import sqlite3
from pathlib import Path
from informix_connect import InformixConnection
from batch_report import get_item_read_rate_data


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
    
    progress.log("QUERY", "Starting Informix query for delivery: " + str(delivery_number))
    
    # Build the query (replace rcv.appointment_nbr with the delivery number)
    query = f"""
    select
        rcv.appointment_nbr as delivery_nbr,
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
    from rdc_db:informix.purchase_order po
    inner join dc_common:informix.po_line line on po.pur_ord_id = line.pur_ord_id
    left join rdc_db:informix.dc_receiver rcv on po.po_nbr = rcv.po_nbr
    where po.must_arrive_by_dt > today - 60
    and rcv.receiver_final_ts > today - 60
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
        
        return {
            "success": True,
            "data": results,
            "record_count": len(results),
            "mds_fam_ids": mds_fam_ids,
            "error": None,
            "progress": progress
        }
    
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
    """Efficiently batch-load read rate data for multiple mds_fam_ids.
    
    This is faster than calling get_item_read_rate_data() individually.
    """
    batching_data = {}
    
    progress.log("BATCH", f"Loading read rate data for {len(mds_fam_ids)} items")
    batch_start = time.time()
    
    for idx, mds_fam_id in enumerate(mds_fam_ids, 1):
        try:
            # Use the existing function
            rate_data = get_item_read_rate_data(mds_fam_id)
            batching_data[mds_fam_id] = rate_data
            
            # Log progress every 5 items
            if idx % 5 == 0 or idx == len(mds_fam_ids):
                elapsed = time.time() - batch_start
                progress.log("BATCH", f"Loaded {idx}/{len(mds_fam_ids)} items ({elapsed:.2f}s)")
        
        except Exception as e:
            batching_data[mds_fam_id] = {
                "mds_fam_id": mds_fam_id,
                "record_count": 0,
                "records": [],
                "error": str(e)
            }
            progress.log("BATCH", f"Error loading {mds_fam_id}: {str(e)}")
    
    batch_elapsed = time.time() - batch_start
    progress.log("BATCH", f"All read rate data loaded in {batch_elapsed:.2f}s")
    
    return batching_data


def apply_batching_to_delivery(delivery_data: dict) -> dict:
    """Take delivery query results and apply batching to all mds_fam_ids.
    
    Augments the delivery_data with read rate data for each mds_fam_id.
    """
    
    progress = delivery_data.get("progress", ProgressTracker())
    
    if not delivery_data.get("success"):
        progress.log("ERROR", "Skipping batching due to query failure")
        return delivery_data
    
    # Build a mapping: mds_fam_id -> read rate data (efficiently)
    progress.log("BATCH", "Starting batch load of read rate data")
    batching_data = batch_get_read_rates(delivery_data.get("mds_fam_ids", []), progress)
    
    # Augment each row in delivery data with batching info
    progress.log("AUGMENT", f"Augmenting {len(delivery_data['data'])} rows with batching data")
    enriched_data = []
    for idx, row in enumerate(delivery_data["data"], 1):
        mds_fam_id = str(row.get("mds_fam_id", ""))
        row["batching_info"] = batching_data.get(mds_fam_id, {})
        enriched_data.append(row)
    
    delivery_data["data"] = enriched_data
    delivery_data["batching_data"] = batching_data
    
    progress.log("AUGMENT", f"All {len(enriched_data)} rows augmented")
    progress.log("COMPLETE", "Delivery analysis complete")
    
    return delivery_data
