"""Delivery Analysis - Query Informix and apply batching to all mds_fam_ids"""
import os
from pathlib import Path
from informix_connect import InformixConnection
from batch_report import get_item_read_rate_data


def get_delivery_po_data(delivery_number: str) -> dict:
    """Query Informix for all PO lines for a given delivery number.
    
    Returns dict with:
    - success: bool
    - data: list of rows (each with mds_fam_id, po_nbr, etc.)
    - error: error message if failed
    - record_count: number of rows returned
    """
    
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
        conn = InformixConnection()
        conn.connect()
        results = conn.execute_query(query)
        conn.disconnect()
        
        # Extract unique mds_fam_ids for batching
        mds_fam_ids = list(set(str(row['mds_fam_id']) for row in results if row.get('mds_fam_id')))
        
        return {
            "success": True,
            "data": results,
            "record_count": len(results),
            "mds_fam_ids": mds_fam_ids,
            "error": None
        }
    
    except Exception as e:
        return {
            "success": False,
            "data": [],
            "record_count": 0,
            "mds_fam_ids": [],
            "error": f"Query failed: {str(e)}"
        }


def apply_batching_to_delivery(delivery_data: dict) -> dict:
    """Take delivery query results and apply batching to all mds_fam_ids.
    
    Augments the delivery_data with read rate data for each mds_fam_id.
    """
    
    if not delivery_data.get("success"):
        return delivery_data
    
    # Build a mapping: mds_fam_id -> read rate data
    batching_data = {}
    for mds_fam_id in delivery_data.get("mds_fam_ids", []):
        try:
            rate_data = get_item_read_rate_data(mds_fam_id)
            batching_data[mds_fam_id] = rate_data
        except Exception as e:
            batching_data[mds_fam_id] = {
                "mds_fam_id": mds_fam_id,
                "record_count": 0,
                "records": [],
                "error": str(e)
            }
    
    # Augment each row in delivery data with batching info
    enriched_data = []
    for row in delivery_data["data"]:
        mds_fam_id = str(row.get("mds_fam_id", ""))
        row["batching_info"] = batching_data.get(mds_fam_id, {})
        enriched_data.append(row)
    
    delivery_data["data"] = enriched_data
    delivery_data["batching_data"] = batching_data
    
    return delivery_data
