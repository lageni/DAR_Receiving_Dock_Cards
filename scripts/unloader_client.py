"""Unloader Client - Display deliveries filtered by door range with rolodex view.

Port: 8061
Cache Source: L:\Engineering\DAR Docktag Cards\cache_data_unloader\
Door Range: 430-450 (default)
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Setup logging
log_dir = Path(r"L:\Engineering\DAR Docktag Cards\cache_data_unloader\logs")
log_dir.mkdir(parents=True, exist_ok=True)

log_file = log_dir / f"unloader_client_{datetime.now().strftime('%Y%m%d')}.log"
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
logger.info(f"UNLOADER CLIENT STARTED - Logging to {log_file.as_posix()}")
logger.info("=" * 60)

# Cache directory
CACHE_DIR = Path(r"L:\Engineering\DAR Docktag Cards\cache_data_unloader")

# FastAPI app
app = FastAPI(title="Unloader Client", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import department band function from main
sys.path.insert(0, str(Path(__file__).parent))
from main import get_department_band


# ============================================================================
# Door Assignment Query
# ============================================================================

def get_door_assignments() -> Dict[str, int]:
    """Get door assignments for all active trailers.
    
    Returns dict of {delivery_number: door_number}
    """
    try:
        from google.cloud import bigquery
        client = bigquery.Client()
        
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
# Cache Reading
# ============================================================================

def get_deliveries_from_cache(door_start: int = 425, door_end: int = 500) -> List[Dict]:
    """Read deliveries from cache filtered by door range.
    
    Strategy:
    1. Query TRAILER table to get ALL deliveries at these doors
    2. Try to load cached data for each delivery
    3. If no cache, show delivery with "No item data available" placeholder
    """
    cache_dir = CACHE_DIR / "deliveries"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Get door assignments from TRAILER table
    logger.info(f"[CACHE] Getting door assignments...")
    door_map = get_door_assignments()
    logger.info(f"[CACHE] Got {len(door_map)} door assignments")
    
    # Get deliveries at these doors
    deliveries_at_doors = {}
    for delivery_nbr, door in door_map.items():
        if door_start <= door <= door_end:
            deliveries_at_doors[delivery_nbr] = door
    
    logger.info(f"[CACHE] Found {len(deliveries_at_doors)} deliveries at doors {door_start}-{door_end}")
    
    deliveries = []
    
    # Try to load cache for each delivery
    for delivery_nbr, door in deliveries_at_doors.items():
        cache_file = cache_dir / f"delivery_{delivery_nbr}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    delivery = json.load(f)
                    delivery["door_number"] = door
                    deliveries.append(delivery)
                    logger.info(f"[CACHE] Loaded cached data for delivery {delivery_nbr} at door {door}")
            except Exception as e:
                logger.error(f"[CACHE-ERROR] Failed to read {cache_file}: {e}")
                # Show delivery anyway with placeholder
                deliveries.append(create_placeholder_delivery(delivery_nbr, door))
        else:
            # No cache yet - show placeholder
            logger.warning(f"[CACHE] No cache for delivery {delivery_nbr} at door {door} - using placeholder")
            deliveries.append(create_placeholder_delivery(delivery_nbr, door))
    
    # Sort by door number
    deliveries.sort(key=lambda d: d.get("door_number", 0))
    
    logger.info(f"[CACHE] Returning {len(deliveries)} deliveries for doors {door_start}-{door_end}")
    return deliveries


def create_placeholder_delivery(delivery_nbr: str, door: int) -> Dict:
    """Create placeholder delivery when cache doesn't exist yet."""
    return {
        "delivery_nbr": delivery_nbr,
        "trailer_nbr": "Unknown",
        "trailer_status_desc": "Loading...",
        "door_number": door,
        "arrival_time": "",
        "items": [{
            "mds_fam_id": "N/A",
            "item_name": "No item data available",
            "cases": 0,
            "estimated_bad_cases": 0.0,
            "estimated_good_cases": 0.0,
            "estimated_unknown_cases": 0.0,
            "avg_read_rate": 100.0,
            "dept_nbr": "",
            "dept_category": "",
            "show_department_band": False
        }],
        "cached_at": None
    }


# ============================================================================
# Display Logic
# ============================================================================

def generate_department_band_html(supplier_dept: str, item_name: str, category: str = "") -> str:
    """Generate HTML for department band display (3 bands).
    
    Used for ICC Drop items instead of product images.
    """
    dept_band = get_department_band(supplier_dept)
    if not dept_band:
        return ""
    
    rgb = dept_band["rgb"]
    color = f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"
    
    category_text = category or dept_band.get("name", "Category")
    
    return f"""
    <div class="department-bands">
        <!-- Band 1: Department Number -->
        <div class="dept-band" style="background-color: {color}; color: #000; padding: 8px; font-weight: bold; font-size: 14px; border: 2px solid #000;">
            Dept. {supplier_dept}
        </div>
        
        <!-- Band 2: Category -->
        <div class="dept-band" style="background-color: rgb(196, 165, 123); color: #000; padding: 8px; font-weight: bold; font-size: 14px; border: 2px solid #000; border-top: none;">
            {category_text}
        </div>
        
        <!-- Band 3: Item Description -->
        <div class="dept-band" style="background-color: rgb(196, 165, 123); color: #000; padding: 6px; font-weight: bold; font-size: 12px; border: 2px solid #000; border-top: none;">
            {item_name[:50]}
        </div>
    </div>
    """


# ============================================================================
# Main Page
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root(door_start: int = 425, door_end: int = 500):
    """Main client page with delivery rolodex."""
    
    deliveries = get_deliveries_from_cache(door_start, door_end)
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unloader Monitor - Doors {door_start}-{door_end}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        .delivery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }}
        
        .carousel-page {{
            display: none;
        }}
        
        .carousel-page.active {{
            display: flex;
        }}
        
        .dev-only {{
            display: none;
        }}
        
        body.dev-view .dev-only {{
            display: block;
        }}
        
        .department-bands {{
            margin: 1rem 0;
        }}
    </style>
</head>
<body class="bg-gray-900 text-white">
    <!-- Header -->
    <div class="bg-blue-600 px-4 py-3 flex justify-between items-center">
        <div>
            <h1 class="text-2xl font-bold">Unloader Monitor</h1>
            <p class="text-sm">Doors {door_start}-{door_end} | Auto-refresh: 30s</p>
        </div>
        <div class="flex gap-2">
            <button onclick="toggleDevView()" class="px-4 py-2 bg-white text-blue-600 rounded font-semibold hover:bg-gray-100">
                Toggle Dev View
            </button>
            <a href="http://localhost:8060" class="px-4 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700">
                Server
            </a>
        </div>
    </div>
    
    <!-- Content Area -->
    <div id="contentArea" class="p-4">
        <!-- Populated by JavaScript -->
    </div>
    
    <script>
        let devViewEnabled = false;
        
        function toggleDevView() {{
            devViewEnabled = !devViewEnabled;
            document.body.classList.toggle('dev-view', devViewEnabled);
        }}
        
        // Load deliveries data
        const deliveriesData = {json.dumps(deliveries)};
        
        function renderDeliveries() {{
            const container = document.getElementById('contentArea');
            
            if (deliveriesData.length === 0) {{
                container.innerHTML = '<div class="text-center text-gray-400 text-2xl mt-20">No deliveries found for doors {door_start}-{door_end}</div>';
                return;
            }}
            
            let html = '<div class="delivery-grid">';
            
            deliveriesData.forEach((delivery, idx) => {{
                const items = delivery.items || [];
                const deliveryNum = delivery.delivery_nbr;
                const trailer = delivery.trailer_nbr;
                const trailerStatus = delivery.trailer_status_desc || 'Unknown';
                const door = delivery.door_number;
                
                // Calculate case totals
                let totalUnknown = 0;
                let totalBad = 0;
                let totalGood = 0;
                
                items.forEach(item => {{
                    totalUnknown += item.estimated_unknown_cases || 0;
                    totalBad += item.estimated_bad_cases || 0;
                    totalGood += item.estimated_good_cases || 0;
                }});
                
                // Round to integers
                totalUnknown = Math.round(totalUnknown);
                totalBad = Math.round(totalBad);
                totalGood = Math.round(totalGood);
                const totalCases = totalUnknown + totalBad + totalGood;
                
                // Determine header color based on bad cases
                let headerBg = 'bg-gray-700';
                if (totalBad > 100) headerBg = 'bg-red-600';
                else if (totalBad > 50) headerBg = 'bg-yellow-600';
                else if (totalBad > 0) headerBg = 'bg-orange-600';
                else headerBg = 'bg-green-600';
                
                html += `
                    <div class="delivery-card bg-gray-800 rounded-lg shadow-lg border-2 border-gray-700 overflow-hidden">
                        <div class="${{headerBg}} px-3 py-2">
                            <div class="flex justify-between items-center">
                                <h3 class="font-bold text-lg">Door ${{door}}</h3>
                                <span class="text-sm">Delivery #${{deliveryNum}}</span>
                            </div>
                            <div class="flex justify-between items-center mt-1">
                                <span class="text-xs">Trailer: ${{trailer}}</span>
                                <span class="text-xs font-semibold">${{trailerStatus}}</span>
                            </div>
                            <div class="text-xs mt-1">
                                <span class="font-semibold">Cases:</span> 
                                <span class="text-green-300">Good: ${{totalGood}}</span> | 
                                <span class="text-red-300">Bad: ${{totalBad}}</span>
                                ${{totalUnknown > 0 ? ` | <span class="text-gray-300">Unknown: ${{totalUnknown}}</span>` : ''}}
                            </div>
                            <div class="dev-only text-xs mt-1">
                                Total Items: ${{items.length}} | Total Cases: ${{totalCases}}
                            </div>
                        </div>
                        
                        <div class="carousel-container p-3" data-delivery="${{idx}}">
                            <div class="carousel-items">
                                ${{renderItemPages(items, trailerStatus)}}
                            </div>
                        </div>
                    </div>
                `;
            }});
            
            html += '</div>';
            container.innerHTML = html;
            
            // Start auto-scroll
            startAutoScroll();
        }}
        
        function renderItemPages(items, trailerStatus) {{
            if (items.length === 0) {{
                return '<div class="text-center text-gray-400 py-8">No items</div>';
            }}
            
            // Show 2 items per page
            const itemsPerPage = 2;
            let html = '';
            
            for (let i = 0; i < items.length; i += itemsPerPage) {{
                const pageItems = items.slice(i, i + itemsPerPage);
                const isActive = i === 0 ? 'active' : '';
                
                html += `<div class="carousel-page ${{isActive}}" style="flex-direction: column; gap: 1rem;">`;
                
                pageItems.forEach(item => {{
                    const itemName = item.item_name || 'Unknown Item';
                    const readRate = item.avg_read_rate || 0;
                    const badCases = Math.round(item.estimated_bad_cases || 0);
                    const imageUrl = item.image_url || '';
                    const showBand = item.show_department_band || false;
                    const mdsId = item.mds_fam_id || '';
                    const supplierDept = item.supplier_dept || item.dept_nbr || '';
                    const deptCategory = item.dept_category || 'Category';
                    
                    // Determine color based on read rate
                    let perfColor = '#6b7280';
                    if (readRate >= 85) perfColor = '#16a34a';
                    else if (readRate >= 50) perfColor = '#eab308';
                    else perfColor = '#dc2626';
                    
                    html += `
                        <div class="item-card bg-gray-700 rounded p-3 border-2" style="border-color: ${{perfColor}};">
                            <div class="dev-only text-xs text-gray-400 mb-1">MDS: ${{mdsId}}</div>
                            <div class="text-sm font-bold mb-2">${{itemName.substring(0, 40)}}</div>
                            
                            <div class="flex items-center justify-center mb-2" style="min-height: 150px;">
                                ${{showBand ? generateDepartmentBandHTML(supplierDept, itemName, deptCategory) : generateImageHTML(imageUrl, itemName)}}
                            </div>
                            
                            <div class="text-center">
                                <div class="text-4xl font-bold" style="color: ${{perfColor}};">${{readRate.toFixed(0)}}%</div>
                                ${{badCases > 0 ? `<div class="text-red-400 font-bold text-xl">${{badCases}} bad case${{badCases !== 1 ? 's' : ''}}</div>` : ''}}
                            </div>
                        </div>
                    `;
                }});
                
                html += '</div>';
            }}
            
            return html;
        }}
        
        function generateDepartmentBandHTML(dept, itemName, deptCategory) {{
            if (!dept) return '<div class="text-gray-400">No dept band data</div>';
            
            // Use actual category from BQ data
            const category = deptCategory || 'Category';
            
            return `
                <div class="w-full">
                    <div style="background-color: #ff8c00; color: #000; padding: 8px; font-weight: bold; border: 2px solid #000;">
                        Dept. ${{dept}}
                    </div>
                    <div style="background-color: rgb(196, 165, 123); color: #000; padding: 8px; font-weight: bold; border: 2px solid #000; border-top: none;">
                        ${{category}}
                    </div>
                    <div style="background-color: rgb(196, 165, 123); color: #000; padding: 6px; font-weight: bold; font-size: 12px; border: 2px solid #000; border-top: none;">
                        ${{itemName.substring(0, 40)}}
                    </div>
                </div>
            `;
        }}
        
        function generateImageHTML(url, name) {{
            if (!url) return '<div class="text-gray-400">No Image</div>';
            return `<img src="${{url}}" alt="${{name}}" class="max-w-full max-h-40 object-contain rounded" onerror="this.style.display='none'; this.parentElement.innerHTML='<div class=\\'text-gray-400\\'>Image Error</div>';" />`;
        }}
        
        function startAutoScroll() {{
            setInterval(() => {{
                document.querySelectorAll('.carousel-items').forEach(container => {{
                    const pages = container.querySelectorAll('.carousel-page');
                    if (pages.length <= 1) return;
                    
                    let currentIndex = -1;
                    pages.forEach((page, idx) => {{
                        if (page.classList.contains('active')) {{
                            currentIndex = idx;
                            page.classList.remove('active');
                        }}
                    }});
                    
                    const nextIndex = (currentIndex + 1) % pages.length;
                    pages[nextIndex].classList.add('active');
                }});
            }}, 5000); // 5 seconds per page
        }}
        
        // Auto-refresh page every 30 seconds
        setTimeout(() => location.reload(), 30000);
        
        // Initial render
        renderDeliveries();
    </script>
</body>
</html>"""


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/api/deliveries")
async def api_deliveries(door_start: int = 425, door_end: int = 500):
    """Get deliveries from cache."""
    deliveries = get_deliveries_from_cache(door_start, door_end)
    return {"deliveries": deliveries, "count": len(deliveries)}


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8061)
