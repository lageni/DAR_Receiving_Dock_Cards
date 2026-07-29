"""Unloader Server - BigQuery-based delivery monitoring for unloader doors.

Port: 8060
Data Source: BigQuery wmt-ambient-centeng.6068_Engineering.DAR_DELIVERIES_CACHE
Cache: L:\Engineering\DAR Docktag Cards\cache_data_unloader\
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Setup logging
log_dir = Path(r"L:\Engineering\DAR Docktag Cards\cache_data_unloader\logs")
log_dir.mkdir(parents=True, exist_ok=True)

log_file = log_dir / f"unloader_server_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info(f"UNLOADER SERVER STARTED - Logging to {log_file.as_posix()}")
logger.info("=" * 60)

# Cache directory
CACHE_DIR = Path(r"L:\Engineering\DAR Docktag Cards\cache_data_unloader")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
(CACHE_DIR / "deliveries").mkdir(exist_ok=True)
(CACHE_DIR / "items").mkdir(exist_ok=True)
(CACHE_DIR / "trailers").mkdir(exist_ok=True)

# FastAPI app
app = FastAPI(title="Unloader Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# BigQuery Integration
# ============================================================================

def get_bigquery_client():
    """Get authenticated BigQuery client."""
    try:
        from google.cloud import bigquery
        
        # Try to use default credentials
        client = bigquery.Client()
        logger.info("[BQ] BigQuery client initialized")
        return client
    except Exception as e:
        logger.error(f"[BQ-ERROR] Failed to initialize BigQuery client: {e}")
        return None


def query_all_deliveries(days_back: int = 7) -> List[Dict]:
    """Query BigQuery for ALL delivery/item data from DAR_DELIVERIES_CACHE.
    
    NO door filtering - server caches everything, client filters by door.
    
    Args:
        days_back: How many days to look back (default: 7)
    
    Returns:
        List of all delivery/item records
    """
    client = get_bigquery_client()
    if not client:
        logger.error("[BQ-ERROR] No BigQuery client available")
        return []
    
    # Query DAR_DELIVERIES_CACHE directly - NO door filtering
    # We get ALL deliveries and let the client filter by door
    query = f"""
    SELECT 
      delivery_number,
      TRAILER_ID,
      TRAILER_STATUS_DESC,
      ITEM_NUMBER,
      ITEM1_DESC,
      Cases,
      ESTIMATED_BAD_CASES,
      ESTIMATED_GOOD_CASES,
      ESTIMATED_UNKNOWN_CASES,
      ACL_PCT,
      DEPT_NBR,
      DEPT_CATEGORY_DESC,
      VNPK_LENGTH_QTY,
      VNPK_WIDTH_QTY,
      VNPK_HEIGHT_QTY,
      VNPK_QTY,
      WHPK_QTY,
      PO_NUMBER,
      PO_TYPE
    FROM `wmt-ambient-centeng.6068_Engineering.DAR_DELIVERIES_CACHE`
    WHERE delivery_number IS NOT NULL
      AND ITEM_NUMBER IS NOT NULL
    ORDER BY delivery_number, ITEM_NUMBER
    LIMIT 10000
    """
    
    logger.info(f"[BQ] Querying ALL deliveries from DAR_DELIVERIES_CACHE (last {days_back} days)")
    logger.info(f"[BQ] NO door filtering - caching everything, client will filter")
    
    try:
        query_job = client.query(query)
        results = list(query_job.result())
        
        logger.info(f"[BQ] Query returned {len(results)} item records")
        
        # Convert to list of dicts
        deliveries = []
        for row in results:
            try:
                # Calculate avg_read_rate from ACL_PCT (0.0-1.0 to percentage)
                acl_pct = float(row.ACL_PCT) if row.ACL_PCT is not None else 1.0
                avg_read_rate = acl_pct * 100  # Convert to percentage
                
                deliveries.append({
                    "delivery_nbr": str(row.delivery_number),
                    "trailer_nbr": str(row.TRAILER_ID) if row.TRAILER_ID else "Unknown",
                    "trailer_status_desc": str(row.TRAILER_STATUS_DESC) if row.TRAILER_STATUS_DESC else "Unknown",
                    # Item-level data
                    "mds_fam_id": str(row.ITEM_NUMBER),
                    "item_name": str(row.ITEM1_DESC) if row.ITEM1_DESC else "Unknown Item",
                    "cases": int(row.Cases) if row.Cases else 0,
                    "estimated_bad_cases": float(row.ESTIMATED_BAD_CASES) if row.ESTIMATED_BAD_CASES else 0.0,
                    "estimated_good_cases": float(row.ESTIMATED_GOOD_CASES) if row.ESTIMATED_GOOD_CASES else 0.0,
                    "estimated_unknown_cases": float(row.ESTIMATED_UNKNOWN_CASES) if row.ESTIMATED_UNKNOWN_CASES else 0.0,
                    "avg_read_rate": avg_read_rate,
                    "dept_nbr": str(row.DEPT_NBR) if row.DEPT_NBR else "",
                    "dept_category": str(row.DEPT_CATEGORY_DESC) if row.DEPT_CATEGORY_DESC else "",
                    "vnpk_length": str(row.VNPK_LENGTH_QTY) if row.VNPK_LENGTH_QTY else "",
                    "vnpk_width": str(row.VNPK_WIDTH_QTY) if row.VNPK_WIDTH_QTY else "",
                    "vnpk_height": str(row.VNPK_HEIGHT_QTY) if row.VNPK_HEIGHT_QTY else "",
                    "vnpk_qty": str(row.VNPK_QTY) if row.VNPK_QTY else "",
                    "whpk_qty": str(row.WHPK_QTY) if row.WHPK_QTY else "",
                    "po_number": str(row.PO_NUMBER) if row.PO_NUMBER else "",
                    "po_type": int(row.PO_TYPE) if row.PO_TYPE else 0
                })
            except Exception as e:
                logger.error(f"[BQ-ROW-ERROR] Failed to process row: {e}")
                continue
        
        logger.info(f"[BQ] Successfully processed {len(deliveries)} item records")
        
        # Count problematic items
        problematic = [d for d in deliveries if d['avg_read_rate'] < 85.0]
        logger.info(f"[BQ] Found {len(problematic)} PROBLEMATIC items (< 85% read rate)")
        
        return deliveries
    
    except Exception as e:
        logger.error(f"[BQ-ERROR] Query failed: {e}")
        import traceback
        logger.error(f"[BQ-ERROR-TRACE] {traceback.format_exc()}")
        return []


def group_deliveries_by_number(raw_data: List[Dict]) -> Dict[str, Dict]:
    """Group raw BQ rows by delivery_nbr.
    
    Now that we have item-level data from the JOIN, we group items by delivery.
    
    Returns:
        Dict of {delivery_nbr: {delivery_info, items: [...]}}
    """
    deliveries = {}
    
    try:
        for row in raw_data:
            delivery_nbr = row.get("delivery_nbr", "Unknown")
            
            if delivery_nbr == "Unknown":
                logger.warning("[GROUP] Skipping row with unknown delivery_nbr")
                continue
            
            # Create delivery entry if doesn't exist
            if delivery_nbr not in deliveries:
                deliveries[delivery_nbr] = {
                    "delivery_nbr": delivery_nbr,
                    "trailer_nbr": row.get("trailer_nbr", "Unknown"),
                    "trailer_status_desc": row.get("trailer_status_desc", "Unknown"),
                    "door_number": row.get("door_number", 0),
                    "arrival_time": row.get("arrival_time", ""),
                    "items": []
                }
                logger.debug(f"[GROUP] Created delivery entry for {delivery_nbr}")
            
            # Add item to delivery (skip if no item data)
            mds_id = row.get("mds_fam_id", "N/A")
            if mds_id != "N/A":
                item = {
                    "mds_fam_id": mds_id,
                    "item_name": row.get("item_name", "Unknown Item"),
                    "cases": row.get("cases", 0),
                    "estimated_bad_cases": row.get("estimated_bad_cases", 0.0),
                    "estimated_good_cases": row.get("estimated_good_cases", 0.0),
                    "estimated_unknown_cases": row.get("estimated_unknown_cases", 0.0),
                    "avg_read_rate": row.get("avg_read_rate", 0.0),
                    "dept_nbr": row.get("dept_nbr", ""),
                    "dept_category": row.get("dept_category", ""),
                    "vnpk_length": row.get("vnpk_length", ""),
                    "vnpk_width": row.get("vnpk_width", ""),
                    "vnpk_height": row.get("vnpk_height", ""),
                    "vnpk_qty": row.get("vnpk_qty", ""),
                    "whpk_qty": row.get("whpk_qty", "")
                }
                deliveries[delivery_nbr]["items"].append(item)
        
        logger.info(f"[GROUP] Grouped {len(deliveries)} unique deliveries with items")
        for del_nbr, del_data in deliveries.items():
            logger.info(f"[GROUP] Delivery {del_nbr}: {len(del_data['items'])} items")
        
        return deliveries
    
    except Exception as e:
        logger.error(f"[GROUP-ERROR] Failed to group deliveries: {e}")
        import traceback
        logger.error(f"[GROUP-ERROR-TRACE] {traceback.format_exc()}")
        return {}


# ============================================================================
# MDM Integration
# ============================================================================

def get_mdm_headers():
    """Get MDM API headers from environment."""
    return {
        "Api-Key": os.getenv("MDM_API_KEY", ""),
        "Facilitynum": os.getenv("MDM_FACILITY_NUM", "6068"),
        "Facilitycountrycode": os.getenv("MDM_FACILITY_COUNTRY_CODE", "US"),
        "Wmt-Userid": os.getenv("MDM_WMT_USERID", "mdm-ui")
    }


def fetch_mdm_data(mds_id: str) -> Optional[Dict]:
    """Fetch MDM data for a single item.
    
    Returns:
        Dict with item_name, image_url, catalog_gtin, supplier_dept, etc.
    """
    # Check cache first
    cache_file = CACHE_DIR / "items" / f"mdm_{mds_id}.json"
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                cached = json.load(f)
                logger.info(f"[MDM-CACHE-HIT] Item {mds_id}")
                return cached
        except Exception as e:
            logger.error(f"[MDM-CACHE-ERROR] Failed to read cache for {mds_id}: {e}")
    
    logger.info(f"[MDM] Fetching data for item {mds_id}")
    
    try:
        url = f"https://uwms-item.prod.us.walmart.net/items/wm/{mds_id}/?xrefItemInfo=false"
        
        with httpx.Client(verify=False, timeout=30.0) as client:
            response = client.get(url, headers=get_mdm_headers())
            response.raise_for_status()
            mdm_data = response.json()
        
        # Extract relevant fields
        item_data = extract_mdm_fields(mdm_data)
        
        # Cache the result
        try:
            with open(cache_file, 'w') as f:
                json.dump(item_data, f, indent=2)
            logger.info(f"[MDM] Cached data for item {mds_id}")
        except Exception as e:
            logger.error(f"[MDM-CACHE-WRITE-ERROR] Failed to cache {mds_id}: {e}")
        
        return item_data
    
    except httpx.HTTPStatusError as e:
        logger.error(f"[MDM-HTTP-ERROR] HTTP {e.response.status_code} for item {mds_id}: {e}")
        return None
    except httpx.TimeoutException as e:
        logger.error(f"[MDM-TIMEOUT-ERROR] Timeout fetching item {mds_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"[MDM-ERROR] Failed to fetch item {mds_id}: {e}")
        import traceback
        logger.error(f"[MDM-ERROR-TRACE] {traceback.format_exc()}")
        return None


def extract_mdm_fields(mdm_data: Dict) -> Dict:
    """Extract key fields from MDM API response.
    
    Returns only fields that are available. Does NOT return 'Unknown Item'
    so we don't overwrite good data from BQ.
    """
    try:
        prod_def = mdm_data.get("productDefinition", {})
        result = {}
        
        # Item name - only include if found
        if isinstance(prod_def, dict) and "description" in prod_def and prod_def["description"]:
            result["item_name"] = prod_def["description"]
            logger.debug(f"[MDM-EXTRACT] Item name: {prod_def['description']}")
        
        # Image URL - use same order as old ACL app
        image_url = ""
        if isinstance(prod_def, dict) and "imageDimension" in prod_def:
            img_dim = prod_def["imageDimension"]
            if isinstance(img_dim, dict):
                # Try different sizes in order of preference
                for size in ["IMAGE_SIZE_450", "IMAGE_SIZE_200", "IMAGE_SIZE_100", "IMAGE_SIZE_60"]:
                    if size in img_dim and img_dim[size]:
                        image_url = img_dim[size]
                        logger.debug(f"[MDM-EXTRACT] Image URL ({size}): {image_url[:50]}...")
                        break
        if image_url:
            result["image_url"] = image_url
        
        # Catalog GTIN
        if isinstance(prod_def, dict) and "gtin" in prod_def and prod_def["gtin"]:
            result["catalog_gtin"] = str(prod_def["gtin"])
            logger.debug(f"[MDM-EXTRACT] Catalog GTIN: {prod_def['gtin']}")
        
        # Orderable GTIN
        if "gtin" in mdm_data and mdm_data["gtin"]:
            result["gtin"] = str(mdm_data["gtin"])
            logger.debug(f"[MDM-EXTRACT] Orderable GTIN: {mdm_data['gtin']}")
        
        # Supplier department
        supp_info = mdm_data.get("supplierInformation", {})
        if isinstance(supp_info, dict) and "department" in supp_info:
            dept = supp_info["department"]
            if isinstance(dept, dict) and "number" in dept and dept["number"]:
                result["supplier_dept"] = str(dept["number"])
                logger.debug(f"[MDM-EXTRACT] Supplier Dept: {dept['number']}")
        
        return result
    
    except KeyError as e:
        logger.error(f"[MDM-EXTRACT-ERROR] Missing key: {e}")
        return {}
    except Exception as e:
        logger.error(f"[MDM-EXTRACT-ERROR] Unexpected error: {e}")
        import traceback
        logger.error(f"[MDM-EXTRACT-ERROR-TRACE] {traceback.format_exc()}")
        return {}


def should_show_department_band(item: Dict) -> bool:
    """Determine if department band should replace image.
    
    Criteria:
    1. trailer_status_desc == "ICC Drop"
    2. Item is problematic (avg_read_rate < 85)
    3. Has MDM data with supplier_dept
    """
    trailer_status = item.get("trailer_status_desc", "")
    avg_read_rate = item.get("avg_read_rate", 100.0)
    supplier_dept = item.get("supplier_dept", "")
    
    return (
        trailer_status == "ICC Drop"
        and avg_read_rate < 85.0
        and supplier_dept != ""
    )


# ============================================================================
# Cache Management
# ============================================================================

def get_cached_deliveries() -> List[str]:
    """Get list of delivery numbers already in cache."""
    cache_files = (CACHE_DIR / "deliveries").glob("delivery_*.json")
    delivery_nbrs = []
    
    for file in cache_files:
        # Extract delivery_nbr from filename: delivery_12345678.json
        nbr = file.stem.replace("delivery_", "")
        delivery_nbrs.append(nbr)
    
    return delivery_nbrs


def update_cache_all_deliveries():
    """Update cache with ALL deliveries from BigQuery (no door filtering).
    
    Server caches EVERYTHING. Client filters by door when displaying.
    """
    logger.info(f"[CACHE-UPDATE] Starting cache update for ALL deliveries")
    
    try:
        # Get current cached deliveries
        cached_nbrs = set(get_cached_deliveries())
        logger.info(f"[CACHE-UPDATE] Found {len(cached_nbrs)} cached deliveries")
        
        # Query BigQuery for ALL deliveries (no door filter)
        raw_data = query_all_deliveries()
        if not raw_data:
            logger.warning("[CACHE-UPDATE] No data from BigQuery")
            return
        
        # Group by delivery
        deliveries = group_deliveries_by_number(raw_data)
        logger.info(f"[CACHE-UPDATE] Found {len(deliveries)} total deliveries in BQ")
        
        # Find NEW deliveries
        new_deliveries = {k: v for k, v in deliveries.items() if k not in cached_nbrs}
        logger.info(f"[CACHE-UPDATE] {len(new_deliveries)} NEW deliveries to cache")
        
        if len(new_deliveries) == 0:
            logger.info("[CACHE-UPDATE] No new deliveries - cache is up to date")
            return
        
        # Process new deliveries
        for delivery_nbr, delivery_data in new_deliveries.items():
            logger.info(f"[CACHE-UPDATE] Processing delivery {delivery_nbr}")
            
            try:
                items = delivery_data.get("items", [])
                
                # Log item summary
                total_items = len(items)
                problematic_items = [i for i in items if i.get("avg_read_rate", 100) < 85.0]
                logger.info(f"[CACHE-UPDATE] Delivery {delivery_nbr}: {total_items} items, {len(problematic_items)} problematic")
                
                # Enrich ONLY problematic items with MDM data
                enriched_items = []
                for item in items:
                    try:
                        mds_id = item.get("mds_fam_id")
                        avg_read_rate = item.get("avg_read_rate", 100.0)
                        
                        # Only fetch MDM for problematic items (< 85% read rate)
                        if avg_read_rate < 85.0:
                            logger.info(f"[CACHE-UPDATE] PROBLEMATIC: Item {mds_id} ({avg_read_rate:.1f}%) - Fetching MDM")
                            
                            # Save BQ data before MDM merge
                            bq_item_name = item.get("item_name")
                            bq_dept_nbr = item.get("dept_nbr")
                            bq_dept_category = item.get("dept_category")
                            
                            mdm_data = fetch_mdm_data(mds_id)
                            if mdm_data:
                                # Merge MDM data ONLY for fields MDM provides
                                # Preserve BQ data for fields MDM doesn't have
                                
                                # Keep BQ item_name if MDM didn't provide one
                                if not mdm_data.get("item_name") and bq_item_name:
                                    mdm_data["item_name"] = bq_item_name
                                
                                # Keep BQ dept if MDM doesn't have supplier_dept
                                if not mdm_data.get("supplier_dept") and bq_dept_nbr:
                                    mdm_data["supplier_dept"] = bq_dept_nbr
                                
                                item.update(mdm_data)
                                item["trailer_status_desc"] = delivery_data["trailer_status_desc"]
                                item["show_department_band"] = should_show_department_band(item)
                                logger.info(f"[CACHE-UPDATE] Item {mds_id} - MDM fetched, show_band={item['show_department_band']}")
                            else:
                                # MDM fetch failed, use dept_nbr from BQ if available
                                logger.warning(f"[CACHE-UPDATE] MDM fetch failed for {mds_id}, keeping BQ data")
                                if bq_dept_nbr:
                                    item["supplier_dept"] = bq_dept_nbr
                                    item["trailer_status_desc"] = delivery_data["trailer_status_desc"]
                                    item["show_department_band"] = should_show_department_band(item)
                                else:
                                    item["show_department_band"] = False
                        else:
                            # Good items don't need MDM data
                            item["show_department_band"] = False
                        
                        enriched_items.append(item)
                    
                    except Exception as e:
                        logger.error(f"[CACHE-UPDATE-ITEM-ERROR] Failed to enrich item {item.get('mds_fam_id')}: {e}")
                        item["show_department_band"] = False
                        enriched_items.append(item)
                
                delivery_data["items"] = enriched_items
                delivery_data["cached_at"] = datetime.now().isoformat()
                
                # Write to cache
                cache_file = CACHE_DIR / "deliveries" / f"delivery_{delivery_nbr}.json"
                try:
                    with open(cache_file, 'w') as f:
                        json.dump(delivery_data, f, indent=2)
                    logger.info(f"[CACHE-UPDATE]  Cached delivery {delivery_nbr} ({len(enriched_items)} items)")
                except Exception as e:
                    logger.error(f"[CACHE-WRITE-ERROR] Failed to write cache file for {delivery_nbr}: {e}")
            
            except Exception as e:
                logger.error(f"[CACHE-UPDATE-DELIVERY-ERROR] Failed to process delivery {delivery_nbr}: {e}")
                import traceback
                logger.error(f"[CACHE-UPDATE-DELIVERY-ERROR-TRACE] {traceback.format_exc()}")
                continue
        
        logger.info("[CACHE-UPDATE]  Incremental update complete")
    
    except Exception as e:
        logger.error(f"[CACHE-UPDATE-ERROR] Critical failure in cache update: {e}")
        import traceback
        logger.error(f"[CACHE-UPDATE-ERROR-TRACE] {traceback.format_exc()}")


def get_door_assignments() -> Dict[str, int]:
    """Get door assignments for all active trailers.
    
    Returns dict of {delivery_number: door_number}
    """
    client = get_bigquery_client()
    if not client:
        logger.error("[BQ-ERROR] No BigQuery client available for door assignments")
        return {}
    
    query = """
    SELECT DISTINCT 
        DELIVERY_NUMBER,
        CAST(DOOR_NUM AS INTEGER) AS DOOR_NUM
    FROM `wmt-edw-prod.US_SUPPLY_CHAIN_SCT_NONCAT_VM.TRAILER`
    WHERE CAST(DC_NUMBER AS INT64) = 6068
        AND GATE_IN_STATUS = 'ACCEPTED'
        AND GATE_OUT_STATUS IS NULL
        AND ARRIVAL_TIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
    """
    
    try:
        logger.info("[BQ-DOORS] Fetching door assignments for active trailers")
        query_job = client.query(query)
        results = list(query_job.result())
        
        door_map = {}
        for row in results:
            if row.DELIVERY_NUMBER and row.DOOR_NUM:
                door_map[str(row.DELIVERY_NUMBER)] = int(row.DOOR_NUM)
        
        logger.info(f"[BQ-DOORS] Found {len(door_map)} delivery-to-door mappings")
        return door_map
    
    except Exception as e:
        logger.error(f"[BQ-DOORS-ERROR] Failed to get door assignments: {e}")
        import traceback
        logger.error(f"[BQ-DOORS-ERROR-TRACE] {traceback.format_exc()}")
        return {}


# ============================================================================
# Group Deliveries
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Server status page."""
    cached_deliveries = get_cached_deliveries()
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Unloader Server</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 p-8">
    <div class="max-w-4xl mx-auto">
        <h1 class="text-4xl font-bold text-blue-600 mb-4">Unloader Server</h1>
        <p class="text-gray-700 mb-6">Port 8060 - BigQuery-based delivery monitoring</p>
        
        <div class="bg-white rounded-lg shadow p-6 mb-6">
            <h2 class="text-2xl font-bold mb-4">Status</h2>
            <p class="text-green-600 font-semibold">Server Running</p>
            <p class="text-gray-600 mt-2">Cached Deliveries: {len(cached_deliveries)}</p>
            <p class="text-gray-600">Cache Location: {CACHE_DIR.as_posix()}</p>
        </div>
        
        <div class="bg-white rounded-lg shadow p-6">
            <h2 class="text-2xl font-bold mb-4">Actions</h2>
            <button onclick="updateCache()" class="px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700">
                Update Cache
            </button>
            <p class="text-sm text-gray-500 mt-2">Pulls new deliveries from BigQuery (doors 430-450)</p>
        </div>
        
        <div class="bg-white rounded-lg shadow p-6 mt-6">
            <h2 class="text-2xl font-bold mb-4">Client</h2>
            <a href="http://localhost:8061" class="inline-block px-4 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700">
                Open Client Viewer (Port 8061)
            </a>
        </div>
    </div>
    
    <script>
        async function updateCache() {{
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = 'Updating...';
            
            try {{
                const response = await fetch('/api/update-cache');
                const result = await response.json();
                alert(result.message || 'Cache updated!');
            }} catch (error) {{
                alert('Update failed: ' + error);
            }} finally {{
                btn.disabled = false;
                btn.textContent = 'Update Cache';
                location.reload();
            }}
        }}
    </script>
</body>
</html>"""


@app.get("/api/update-cache")
async def api_update_cache():
    """API endpoint to trigger cache update."""
    try:
        logger.info("[API] Manual cache update triggered")
        update_cache_all_deliveries()
        return {"status": "success", "message": "Cache updated successfully"}
    except Exception as e:
        logger.error(f"[API-ERROR] Cache update failed: {e}")
        import traceback
        logger.error(f"[API-ERROR-TRACE] {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/deliveries")
async def api_get_deliveries(door_start: int = 425, door_end: int = 500):
    """Get cached deliveries filtered by door range.
    
    Server caches ALL deliveries. This endpoint filters by door on-demand.
    """
    try:
        logger.info(f"[API] Fetching deliveries for doors {door_start}-{door_end}")
        
        # Get door assignments from TRAILER table
        door_map = get_door_assignments()
        logger.info(f"[API] Got {len(door_map)} door assignments")
        
        cache_dir = CACHE_DIR / "deliveries"
        deliveries = []
        
        if not cache_dir.exists():
            logger.warning(f"[API] Cache directory does not exist: {cache_dir}")
            return {"deliveries": [], "count": 0}
        
        for cache_file in cache_dir.glob("delivery_*.json"):
            try:
                with open(cache_file) as f:
                    delivery = json.load(f)
                    
                    delivery_nbr = delivery.get("delivery_nbr")
                    
                    # Get door number from door_map
                    door = door_map.get(delivery_nbr, 0)
                    delivery["door_number"] = door
                    
                    # Filter by door range
                    if door_start <= door <= door_end:
                        deliveries.append(delivery)
                        logger.debug(f"[API] Including delivery {delivery_nbr} at door {door}")
            except Exception as e:
                logger.error(f"[API-FILE-ERROR] Failed to read {cache_file}: {e}")
                continue
        
        # Sort by door number
        deliveries.sort(key=lambda d: d.get("door_number", 0))
        
        logger.info(f"[API] Returning {len(deliveries)} deliveries for doors {door_start}-{door_end}")
        return {"deliveries": deliveries, "count": len(deliveries), "door_range": f"{door_start}-{door_end}"}
    
    except Exception as e:
        logger.error(f"[API-ERROR] Failed to get deliveries: {e}")
        import traceback
        logger.error(f"[API-ERROR-TRACE] {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Background Worker
# ============================================================================

async def background_cache_updater():
    """Background task to update cache every 10 minutes."""
    import asyncio
    
    while True:
        try:
            logger.info("[BACKGROUND] Starting cache update cycle")
            update_cache_all_deliveries()
            logger.info("[BACKGROUND] Cache update complete - sleeping 10 minutes")
        except Exception as e:
            logger.error(f"[BACKGROUND-ERROR] Cache update failed: {e}")
            import traceback
            logger.error(f"[BACKGROUND-ERROR-TRACE] {traceback.format_exc()}")
        
        await asyncio.sleep(600)  # 10 minutes


@app.on_event("startup")
async def startup_event():
    """Run initial cache update on startup."""
    import asyncio
    
    try:
        logger.info("[STARTUP] Running initial cache update (ALL deliveries, no door filter)")
        update_cache_all_deliveries()
        logger.info("[STARTUP] Initial cache update complete")
    except Exception as e:
        logger.error(f"[STARTUP-ERROR] Initial cache update failed: {e}")
        import traceback
        logger.error(f"[STARTUP-ERROR-TRACE] {traceback.format_exc()}")
    
    # Start background worker
    try:
        asyncio.create_task(background_cache_updater())
        logger.info("[STARTUP] Background cache updater started")
    except Exception as e:
        logger.error(f"[STARTUP-ERROR] Failed to start background worker: {e}")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8060)
