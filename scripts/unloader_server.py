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


def query_deliveries(door_start: int = 430, door_end: int = 450, days_back: int = 7) -> List[Dict]:
    """Query BigQuery for delivery data filtered by door range.
    
    Args:
        door_start: Starting door number (default: 430)
        door_end: Ending door number (default: 450)
        days_back: How many days to look back (default: 7)
    
    Returns:
        List of delivery records with items
    """
    client = get_bigquery_client()
    if not client:
        logger.error("[BQ] No BigQuery client available")
        return []
    
    query = f"""
    SELECT 
      delivery_nbr,
      trailer_nbr,
      trailer_status_desc,
      door_number,
      mds_fam_id,
      estimated_unknown_cases,
      estimated_bad_cases,
      estimated_good_cases,
      avg_read_rate,
      delivery_date
    FROM `wmt-ambient-centeng.6068_Engineering.DAR_DELIVERIES_CACHE`
    WHERE door_number BETWEEN {door_start} AND {door_end}
      AND delivery_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days_back} DAY)
    ORDER BY delivery_nbr, mds_fam_id
    """
    
    logger.info(f"[BQ] Querying deliveries for doors {door_start}-{door_end}")
    
    try:
        query_job = client.query(query)
        results = list(query_job.result())
        
        logger.info(f"[BQ] Query returned {len(results)} rows")
        
        # Convert to list of dicts
        deliveries = []
        for row in results:
            deliveries.append({
                "delivery_nbr": row.delivery_nbr,
                "trailer_nbr": row.trailer_nbr,
                "trailer_status_desc": row.trailer_status_desc,
                "door_number": row.door_number,
                "mds_fam_id": str(row.mds_fam_id),
                "estimated_unknown_cases": row.estimated_unknown_cases or 0,
                "estimated_bad_cases": row.estimated_bad_cases or 0,
                "estimated_good_cases": row.estimated_good_cases or 0,
                "avg_read_rate": float(row.avg_read_rate) if row.avg_read_rate else 0.0,
                "delivery_date": str(row.delivery_date)
            })
        
        return deliveries
    
    except Exception as e:
        logger.error(f"[BQ-ERROR] Query failed: {e}")
        return []


def group_deliveries_by_number(raw_data: List[Dict]) -> Dict[str, Dict]:
    """Group raw BQ rows by delivery_nbr.
    
    Returns:
        Dict of {delivery_nbr: {delivery_info, items: [...]}}
    """
    deliveries = {}
    
    for row in raw_data:
        delivery_nbr = row["delivery_nbr"]
        
        if delivery_nbr not in deliveries:
            deliveries[delivery_nbr] = {
                "delivery_nbr": delivery_nbr,
                "trailer_nbr": row["trailer_nbr"],
                "trailer_status_desc": row["trailer_status_desc"],
                "door_number": row["door_number"],
                "delivery_date": row["delivery_date"],
                "items": []
            }
        
        deliveries[delivery_nbr]["items"].append({
            "mds_fam_id": row["mds_fam_id"],
            "estimated_unknown_cases": row["estimated_unknown_cases"],
            "estimated_bad_cases": row["estimated_bad_cases"],
            "estimated_good_cases": row["estimated_good_cases"],
            "avg_read_rate": row["avg_read_rate"]
        })
    
    return deliveries


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
        except:
            pass
    
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
        with open(cache_file, 'w') as f:
            json.dump(item_data, f, indent=2)
        
        logger.info(f"[MDM] Cached data for item {mds_id}")
        return item_data
    
    except Exception as e:
        logger.error(f"[MDM-ERROR] Failed to fetch item {mds_id}: {e}")
        return None


def extract_mdm_fields(mdm_data: Dict) -> Dict:
    """Extract key fields from MDM API response."""
    try:
        prod_def = mdm_data.get("productDefinition", {})
        
        # Item name
        item_name = "Unknown Item"
        if isinstance(prod_def, dict) and "description" in prod_def:
            item_name = prod_def["description"]
        
        # Image URL
        image_url = ""
        if isinstance(prod_def, dict) and "imageDimension" in prod_def:
            img_dim = prod_def["imageDimension"]
            for size in ["medium", "large", "small"]:
                if size in img_dim and img_dim[size]:
                    image_url = img_dim[size]
                    break
        
        # Catalog GTIN
        catalog_gtin = ""
        if isinstance(prod_def, dict) and "gtin" in prod_def:
            catalog_gtin = str(prod_def["gtin"])
        
        # Orderable GTIN
        gtin = ""
        if "gtin" in mdm_data:
            gtin = str(mdm_data["gtin"])
        
        # Supplier department
        supplier_dept = ""
        supp_info = mdm_data.get("supplierInformation", {})
        if isinstance(supp_info, dict) and "department" in supp_info:
            dept = supp_info["department"]
            if isinstance(dept, dict) and "number" in dept:
                supplier_dept = str(dept["number"])
        
        return {
            "item_name": item_name,
            "image_url": image_url,
            "catalog_gtin": catalog_gtin,
            "gtin": gtin,
            "supplier_dept": supplier_dept
        }
    
    except Exception as e:
        logger.error(f"[MDM-EXTRACT-ERROR] {e}")
        return {
            "item_name": "Error",
            "image_url": "",
            "catalog_gtin": "",
            "gtin": "",
            "supplier_dept": ""
        }


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


def update_cache_incremental(door_start: int = 430, door_end: int = 450):
    """Update cache with only NEW deliveries from BigQuery."""
    logger.info(f"[CACHE-UPDATE] Starting incremental update for doors {door_start}-{door_end}")
    
    # Get current cached deliveries
    cached_nbrs = set(get_cached_deliveries())
    logger.info(f"[CACHE-UPDATE] Found {len(cached_nbrs)} cached deliveries")
    
    # Query BigQuery
    raw_data = query_deliveries(door_start, door_end)
    if not raw_data:
        logger.warning("[CACHE-UPDATE] No data from BigQuery")
        return
    
    # Group by delivery
    deliveries = group_deliveries_by_number(raw_data)
    logger.info(f"[CACHE-UPDATE] Found {len(deliveries)} total deliveries in BQ")
    
    # Find NEW deliveries
    new_deliveries = {k: v for k, v in deliveries.items() if k not in cached_nbrs}
    logger.info(f"[CACHE-UPDATE] {len(new_deliveries)} NEW deliveries to cache")
    
    # Process new deliveries
    for delivery_nbr, delivery_data in new_deliveries.items():
        logger.info(f"[CACHE-UPDATE] Processing delivery {delivery_nbr}")
        
        # Enrich items with MDM data for problematic items
        enriched_items = []
        for item in delivery_data["items"]:
            mds_id = item["mds_fam_id"]
            avg_read_rate = item["avg_read_rate"]
            
            # Only fetch MDM for problematic items (< 85% read rate)
            if avg_read_rate < 85.0:
                mdm_data = fetch_mdm_data(mds_id)
                if mdm_data:
                    item.update(mdm_data)
                    item["trailer_status_desc"] = delivery_data["trailer_status_desc"]
                    item["show_department_band"] = should_show_department_band(item)
            else:
                item["show_department_band"] = False
            
            enriched_items.append(item)
        
        delivery_data["items"] = enriched_items
        delivery_data["cached_at"] = datetime.now().isoformat()
        
        # Write to cache
        cache_file = CACHE_DIR / "deliveries" / f"delivery_{delivery_nbr}.json"
        with open(cache_file, 'w') as f:
            json.dump(delivery_data, f, indent=2)
        
        logger.info(f"[CACHE-UPDATE] Cached delivery {delivery_nbr} ({len(enriched_items)} items)")
    
    logger.info("[CACHE-UPDATE] Incremental update complete")


# ============================================================================
# API Endpoints
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
        update_cache_incremental()
        return {"status": "success", "message": "Cache updated successfully"}
    except Exception as e:
        logger.error(f"[API-ERROR] Cache update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/deliveries")
async def api_get_deliveries(door_start: int = 430, door_end: int = 450):
    """Get cached deliveries filtered by door range."""
    try:
        cache_dir = CACHE_DIR / "deliveries"
        deliveries = []
        
        for cache_file in cache_dir.glob("delivery_*.json"):
            with open(cache_file) as f:
                delivery = json.load(f)
                
                # Filter by door range
                door = delivery.get("door_number", 0)
                if door_start <= door <= door_end:
                    deliveries.append(delivery)
        
        # Sort by door number
        deliveries.sort(key=lambda d: d.get("door_number", 0))
        
        return {"deliveries": deliveries, "count": len(deliveries)}
    
    except Exception as e:
        logger.error(f"[API-ERROR] Failed to get deliveries: {e}")
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
            update_cache_incremental()
            logger.info("[BACKGROUND] Cache update complete - sleeping 10 minutes")
        except Exception as e:
            logger.error(f"[BACKGROUND-ERROR] {e}")
        
        await asyncio.sleep(600)  # 10 minutes


@app.on_event("startup")
async def startup_event():
    """Run initial cache update on startup."""
    import asyncio
    logger.info("[STARTUP] Running initial cache update")
    update_cache_incremental()
    
    # Start background worker
    asyncio.create_task(background_cache_updater())
    logger.info("[STARTUP] Background cache updater started")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8060)
