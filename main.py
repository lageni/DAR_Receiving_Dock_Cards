import os
import json
import csv
import io
import sqlite3
import uuid
import asyncio
from pathlib import Path
from urllib.parse import urlencode
from io import BytesIO
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse, RedirectResponse
import httpx
from fpdf import FPDF
from dotenv import load_dotenv
from cache_manager import get_cache_manager
from acl_background_worker import acl_monitor

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="CodePuppy DAR")

@app.on_event("startup")
async def startup_event():
    print("[STARTUP] Starting ACL background monitor...")
    asyncio.create_task(acl_monitor.start())  # Don't block server startup!
    print("[STARTUP] ACL monitor running in background")

# Get database path from .env or default to local
def get_database_path():
    """Get read_rates.db path from .env (DATABASE_PATH) or use default.
    
    Priority:
    1. DATABASE_PATH from .env (absolute or relative)
    2. Default: read_rates.db in same directory as app
    """
    db_path = os.getenv("DATABASE_PATH", "").strip()
    
    if not db_path:
        # Default to local directory
        db_path = str(Path(__file__).parent / "read_rates.db")
    elif not os.path.isabs(db_path):
        # Relative path - make it absolute from app directory
        db_path = str(Path(__file__).parent / db_path)
    # else: absolute path, use as-is
    
    return db_path

# Cache for read rates data
_read_rates_cache = None

# Cache for delivery analysis to avoid re-querying for PDF
_delivery_cache = {}


def load_read_rates():
    """Load read rates from read_rates.db (SQLite). Returns dict[mds_fam_id] -> list of records."""
    global _read_rates_cache
    if _read_rates_cache is not None:
        return _read_rates_cache
    
    db_path = get_database_path()
    
    if not Path(db_path).exists():
        print(f"[WARNING] Database not found at {db_path}")
        return {}
    
    rates_by_family = defaultdict(list)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query: get all rows grouped by mds_fam_id, sorted by date
        cursor.execute("""
            SELECT mds_fam_id, acl_insert_date, acl_event_cnt, acl_null_cnt
            FROM read_rates
            ORDER BY mds_fam_id, acl_insert_date
        """)
        
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
        _read_rates_cache = rates_by_family
        print(f"[INFO] Loaded {len(rates_by_family)} items from {db_path}")
    except Exception as e:
        print(f"[ERROR] Loading read_rates.db: {e}")
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
        return {}
    
    db_path = get_database_path()
    
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
        print(f"[OPTIMIZED] Loaded {len(rates_by_family)} items (queried only {len(mds_fam_ids)} specific items from DB)")
        
    except Exception as e:
        print(f"[ERROR] Loading read rates for items: {e}")
        return {}
    
    return rates_by_family


def format_date_for_chart(date_str: str) -> str:
    """Convert YYYY-MM-DD to abbreviated month+year (e.g., 'Dec 2025')."""
    try:
        parts = date_str.split('-')
        if len(parts) == 3:
            year, month, day = parts
            months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            month_int = int(month)
            return f"{months[month_int]} {year}"
    except:
        pass
    return date_str


def get_avg_performance(item_rates: list) -> float:
    """Calculate average ACL Performance using total(acl_null_cnt) / total(acl_event_cnt).
    
    This is a WEIGHTED average - more accurate than averaging individual percentages.
    
    Returns:
        Performance percentage (0-100), where:
        - 100% = all reads successful
        - 0% = all reads failed/null
    """
    if not item_rates:
        return 0
    
    # Sum ALL null counts and ALL event counts (weighted average)
    total_null_cnt = sum(r['null_cnt'] for r in item_rates)
    total_event_cnt = sum(r['event_cnt'] for r in item_rates)
    
    if total_event_cnt == 0:
        return 0
    
    # Calculate null percentage: total(acl_null_cnt) / total(acl_event_cnt) * 100
    acl_null_pct = (total_null_cnt / total_event_cnt) * 100
    
    # Return PERFORMANCE (inverse of null %)
    return 100 - acl_null_pct


def get_trend_status(item_rates: list) -> str:
    """Determine trend: Improving, Consistent, Inconsistent, or Declining."""
    if len(item_rates) < 2:
        return "N/A"
    
    # Calculate trend by comparing first half to second half
    mid = len(item_rates) // 2
    first_half = item_rates[:mid]
    second_half = item_rates[mid:]
    
    avg_first = sum(r['null_pct'] for r in first_half) / len(first_half) if first_half else 0
    avg_second = sum(r['null_pct'] for r in second_half) / len(second_half) if second_half else 0
    
    # Check for consistency
    first_values = [r['null_pct'] for r in first_half]
    second_values = [r['null_pct'] for r in second_half]
    first_std = max(first_values) - min(first_values) if first_values else 0
    second_std = max(second_values) - min(second_values) if second_values else 0
    
    # Determine status
    if first_std < 1 and second_std < 1:  # Both halves stable
        return "Consistent"
    elif avg_second > avg_first:  # Getting better
        return "Improving"
    elif abs(avg_second - avg_first) < 2:  # Similar trend
        return "Consistent"
    else:  # Getting worse
        return "Declining"


def get_color_for_performance(pct: float) -> str:
    """Get gradient color from red (0%) to green (100%)."""
    if pct < 25:
        return "#dc2626"  # Red
    elif pct < 50:
        return "#f59e0b"  # Amber
    elif pct < 75:
        return "#eab308"  # Yellow
    else:
        return "#16a34a"  # Green

def load_department_bands() -> dict:
    """Load department band info from JSON file."""
    bands_file = Path("department_bands.json")
    if not bands_file.exists():
        return []
    try:
        with open(bands_file) as f:
            data = json.load(f)
        return data.get("departments", [])
    except Exception as e:
        print(f"[WARNING] Failed to load department bands: {str(e)}")
        return []

def get_department_band(dept_number: str) -> dict:
    """Get department band info by department number."""
    if not dept_number:
        return None
    bands = load_department_bands()
    dept_clean = dept_number.lstrip("D.").lstrip("0") if isinstance(dept_number, str) else str(dept_number)
    for band in bands:
        band_code = band.get("code", "").lstrip("D.").split("/")[0].lstrip("0")
        if band_code == dept_clean:
            return band
    return None

def check_non_conveyable(length: str, width: str, height: str) -> tuple:
    """Check if item is non-conveyable based on dimensions."""
    try:
        length_val = float(length) if length else 999
        width_val = float(width) if width else 999
        height_val = float(height) if height else 999
        
        # Sort dimensions to get longest, middle, smallest
        sides = sorted([length_val, width_val, height_val], reverse=True)
        if sides[0] < 7 or sides[1] < 5 or sides[2] < 2:
            return True, "WORKSTATION: NON-CONVEYABLE", "#dc2626"
    except (ValueError, TypeError):
        pass
    return False, "", ""

def get_recommendation(avg_perf: float, trend_status: str, catalog_gtin: str = "", orderable_gtin: str = "") -> tuple:
    """Get ACL recommendation based on performance and trend.
    
    Special case: If performance < 50% AND catalog_gtin is DIFFERENT from orderable_gtin,
    this indicates a catalog mismatch issue -> "INSPECT CATALOG; TAKE TO PROBLEMS"
    
    If catalog_gtin == orderable_gtin, treat as if there's no catalog GTIN (it's just the normal GTIN).
    """
    # Check if catalog GTIN is truly different from orderable (real catalog issue)
    has_catalog_issue = catalog_gtin and catalog_gtin != orderable_gtin
    
    if avg_perf < 50 and has_catalog_issue:
        return "INSPECT CATALOG; TAKE TO PROBLEMS", "#dc2626", "from-red-50 via-red-50 to-red-100 border-red-300"
    elif avg_perf >= 85:
        return "ACL APPROVED", "#16a34a", "from-green-50 via-green-50 to-green-100 border-green-300"
    elif avg_perf < 50:
        return "WORKSTATION RECOMMENDED", "#dc2626", "from-red-50 via-red-50 to-red-100 border-red-300"
    elif avg_perf < 85:
        if trend_status == "Improving":
            return "ADEQUATE PERFORMANCE", "#eab308", "from-yellow-50 via-yellow-50 to-yellow-100 border-yellow-300"
        else:
            return "REQUIRES MANUAL INSPECTION", "#eab308", "from-yellow-50 via-yellow-50 to-yellow-100 border-yellow-300"
    return "UNKNOWN", "#6b7280", "from-gray-50 via-gray-50 to-gray-100 border-gray-300"

def get_read_rate_chart(mds_fam_id: str, length: str = "", width: str = "", height: str = "") -> str:
    """Generate Chart.js HTML for read rate trend from read_rates.db."""
    is_non_convey, non_convey_text, _ = check_non_conveyable(length, width, height)
    if is_non_convey:
        print(f"[RECOMMENDATION] Item {mds_fam_id}: {non_convey_text}")
        return f'''<div class="mt-4 bg-white p-4 rounded border max-w-md mx-auto">
            <h2 class="text-2xl font-bold text-center text-blue-600 mb-3">ACL Performance %</h2>
            <div class="bg-red-50 border-2 border-red-300 p-6 rounded-xl text-center shadow-lg">
                <div class="text-3xl font-black text-red-600">{non_convey_text}</div>
            </div>
            <div class="mt-3 text-xs text-gray-600 text-center border-t pt-2">
                <p>Total PO Qty: <strong>{total_po_qty:,}</strong></p>
            </div>
        </div>'''
    
    rates = load_read_rates()
    data = rates.get(str(mds_fam_id), [])
    
    # Debug: if no data, show message
    if not data or len(data) == 0:
        return f'''<div class="mt-4 bg-yellow-50 p-4 rounded border-2 border-yellow-300">
            <p class="text-yellow-700 text-sm">No ACL Performance data available for MDS_FAM_ID: {mds_fam_id}</p>
        </div>'''
    
    # Format data for Chart.js - use abbreviated month+year for labels
    labels = [format_date_for_chart(d["date"]) for d in data]
    values = [d["null_pct"] for d in data]
    
    # Calculate metrics
    avg_perf = get_avg_performance(data)
    trend_status = get_trend_status(data)
    color = get_color_for_performance(avg_perf)
    
    # Create chart ID
    chart_id = f"chart_{mds_fam_id}"
    
    # Get recommendation based on performance and trend
    recommendation, rec_color, rec_bg = get_recommendation(avg_perf, trend_status)
    
    # Safely build the data JSON string
    labels_json = json.dumps(labels)
    values_json = json.dumps(values)
    
    # Create performance cards (prettier, much bigger)
    perf_card = f'''<div class="grid grid-cols-2 gap-4 mb-4">
        <div class="bg-gradient-to-br from-amber-50 via-yellow-50 to-yellow-100 p-6 rounded-xl border-2 border-yellow-300 shadow-lg hover:shadow-xl transition transform hover:scale-105">
            <div class="text-center">
                <div class="text-sm text-yellow-700 font-bold uppercase tracking-widest">Avg Performance</div>
                <div class="text-5xl font-black mt-3" style="color: {color};">{avg_perf:.1f}%</div>
            </div>
        </div>
        <div class="bg-gradient-to-br from-purple-50 via-indigo-50 to-indigo-100 p-6 rounded-xl border-2 border-purple-300 shadow-lg hover:shadow-xl transition transform hover:scale-105">
            <div class="text-center">
                <div class="text-sm text-purple-700 font-bold uppercase tracking-widest">Trend</div>
                <div class="text-4xl font-black mt-3 text-purple-900">{trend_status}</div>
            </div>
        </div>
    </div>'''
    
    # Create recommendation card (big and bold)
    rec_card = f'''<div class="bg-gradient-to-br {rec_bg} p-8 rounded-xl border-2 shadow-lg mb-4">
        <div class="text-center">
            <div class="text-5xl font-black" style="color: {rec_color};">{recommendation}</div>
        </div>
    </div>'''
    
    return f'''<div class="mt-4 bg-white p-4 rounded border max-w-md mx-auto">
        <h2 class="text-2xl font-bold text-center text-blue-600 mb-3">ACL Performance %</h2>
        {rec_card}
        {perf_card}
        <div style="height: 300px; position: relative; max-width: 400px; margin: 0 auto;">
            <canvas id="{chart_id}"></canvas>
        </div>
        <script>
            (function() {{
                // Wait for Chart.js to be ready
                if (typeof Chart === 'undefined') {{
                    setTimeout(arguments.callee, 100);
                    return;
                }}
                var ctx = document.getElementById("{chart_id}").getContext("2d");
                var labels = {labels_json};
                var values = {values_json};
                new Chart(ctx, {{
                    type: "line",
                    data: {{
                        labels: labels,
                        datasets: [{{
                            label: "ACL Performance %",
                            data: values,
                            borderColor: "#0053e2",
                            backgroundColor: "rgba(0, 83, 226, 0.1)",
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3,
                            pointRadius: 3,
                            pointBackgroundColor: "#0053e2"
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                display: false
                            }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                max: 100
                            }}
                        }}
                    }}
                }});
            }})();
        </script>
    </div>'''


@app.get("/item-analysis", response_class=HTMLResponse)
async def item_analysis_page():
    return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodePuppy DAR</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
</head>
<body class="bg-gray-50">
    <header class="bg-white border-b px-4 py-6 flex justify-between items-center">
        <div>
            <h1 class="text-3xl font-bold text-blue-600">CodePuppy DAR</h1>
            <p class="text-sm text-gray-600">Inventory Search</p>
        </div>
        <a href="/admin" class="px-4 py-2 bg-gray-600 text-white rounded font-semibold hover:bg-gray-700">Admin</a>
    </header>
    <main class="w-full px-2 py-4">
        <!-- ACL Directive Actions Ruleset -->
        <details class="bg-blue-50 border-l-4 border-blue-600 p-4 mb-4 rounded cursor-pointer">
            <summary class="font-bold text-blue-700 select-none">ACL Directive Actions Ruleset (Click to expand)</summary>
            <div class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <div class="bg-green-50 border border-green-300 p-3 rounded">
                    <div class="font-bold text-green-700">ACL APPROVED</div>
                    <div class="text-green-600">Performance >= 85%</div>
                    <div class="text-xs text-gray-600 mt-1">No action needed</div>
                </div>
                <div class="bg-yellow-50 border border-yellow-300 p-3 rounded">
                    <div class="font-bold text-yellow-700">ADEQUATE PERFORMANCE</div>
                    <div class="text-yellow-600">Performance < 85% & Improving</div>
                    <div class="text-xs text-gray-600 mt-1">Monitor closely</div>
                </div>
                <div class="bg-yellow-50 border border-yellow-300 p-3 rounded">
                    <div class="font-bold text-yellow-700">REQUIRES MANUAL INSPECTION</div>
                    <div class="text-yellow-600">Performance < 85% & Declining</div>
                    <div class="text-xs text-gray-600 mt-1">Review needed</div>
                </div>
                <div class="bg-red-50 border border-red-300 p-3 rounded">
                    <div class="font-bold text-red-700">WORKSTATION RECOMMENDED</div>
                    <div class="text-red-600">Performance < 50%</div>
                    <div class="text-xs text-gray-600 mt-1">Immediate action required</div>
                </div>
                <div class="bg-red-50 border border-red-300 p-3 rounded">
                    <div class="font-bold text-red-700">WORKSTATION: NON-CONVEYABLE</div>
                    <div class="text-red-600">Longest side < 7" OR 2nd longest < 5" OR smallest < 2"</div>
                    <div class="text-xs text-gray-600 mt-1">Size-based constraint</div>
                </div>
                <div class="bg-red-50 border border-red-300 p-3 rounded">
                    <div class="font-bold text-red-700">INSPECT CATALOG; TAKE TO PROBLEMS</div>
                    <div class="text-red-600">Performance < 50% & Catalog GTIN exists</div>
                    <div class="text-xs text-gray-600 mt-1">Catalog mismatch requires review</div>
                </div>
            </div>
            <div class="mt-3 text-xs text-gray-600 italic">Note: These rules are directive guidelines subject to change</div>
        </details>
        
        <!-- Department Band Templates -->
        <details class="bg-purple-50 border-l-4 border-purple-600 p-4 mb-4 rounded cursor-pointer">
            <summary class="font-bold text-purple-700 select-none">Department Band Templates (Click to expand)</summary>
            <div class="mt-4 space-y-3">
                <div class="text-sm text-gray-700 mb-4">Sample department bands showing Dept # | Category | Item Description layout:</div>
                
                <!-- D.09 Sporting Goods Example -->
                <div class="space-y-0">
                    <div style="background-color: #00A4A6; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; font-size: 0.95rem;">Dept. 09</div>
                    <div style="background-color: #00A4A6; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.9rem;">Sporting Goods</div>
                    <div style="background-color: #C4A57B; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.85rem;">Example Item Description</div>
                </div>
                
                <!-- D.23 Mens Wear Example -->
                <div class="space-y-0" style="margin-top: 12px;">
                    <div style="background-color: #003DA5; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; font-size: 0.95rem;">Dept. 23</div>
                    <div style="background-color: #003DA5; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.9rem;">Mens Wear</div>
                    <div style="background-color: #C4A57B; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.85rem;">Example Item Description</div>
                </div>
                
                <!-- D.02 HBA Example -->
                <div class="space-y-0" style="margin-top: 12px;">
                    <div style="background-color: #FF8C00; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; font-size: 0.95rem;">Dept. 02</div>
                    <div style="background-color: #FF8C00; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.9rem;">HBA</div>
                    <div style="background-color: #C4A57B; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.85rem;">Example Item Description</div>
                </div>
            </div>
        </details>
        
        <!-- Search Bar at Top -->
        <div class="bg-white p-3 rounded border shadow-sm mb-4">
            <form id="searchForm" hx-get="/api/inventory/search" hx-target="#results" class="flex gap-2">
                <input type="text" id="itemIdInput" name="item_id" placeholder="Enter Item ID (e.g., 659608850)" required class="flex-1 px-3 py-2 border rounded text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                <input type="hidden" name="id_type" value="ITEM_NUMBER">
                <input type="hidden" name="node" value="6068">
                <button type="submit" class="bg-blue-600 text-white px-6 py-2 rounded font-semibold text-sm hover:bg-blue-700">Search</button>
                <button type="button" onclick="loadExample()" class="bg-gray-300 text-gray-800 px-4 py-2 rounded font-semibold text-sm hover:bg-gray-400">Example</button>
                <a href="/batch/random" class="inline-block bg-orange-500 text-white px-4 py-2 rounded font-semibold text-sm hover:bg-orange-600">Test Batch (3 Random)</a>
                <a href="/delivery-analysis" class="inline-block bg-purple-600 text-white px-4 py-2 rounded font-semibold text-sm hover:bg-purple-700">Delivery Analysis</a>
                <a href="/acl-freight-awareness" class="inline-block bg-teal-600 text-white px-4 py-2 rounded font-semibold text-sm hover:bg-teal-700">ACL Freight Awareness</a></form>
        </div>
        
        <!-- Results: Two-column layout (Image on left, Graph on right) -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-2">
            <!-- LEFT: Product Image + Details -->
            <div id="results" class="text-sm text-gray-500">Results appear here...</div>
            <!-- RIGHT: ACL Performance Graph -->
            <div id="results-chart" class="text-sm text-gray-500"></div>
        </div>
    </main>
    <script>
        function loadExample() {
            document.getElementById('itemIdInput').value = '659608850';
            htmx.ajax('GET', '/api/inventory/search?item_id=659608850&id_type=ITEM_NUMBER&node=6068', '#results');
        }
    </script>
</body>
</html>"""


@app.get("/api/inventory/search", response_class=HTMLResponse)
async def search_inventory(item_id: str, id_type: str = "ITEM_NUMBER", node: str = None):
    try:
        api_key = os.getenv("MDM_API_KEY")
        facility_num = os.getenv("MDM_FACILITY_NUM", "6068")
        facility_country = os.getenv("MDM_FACILITY_COUNTRY_CODE", "US")
        wmt_userid = os.getenv("MDM_WMT_USERID", "mdm-ui")

        if not api_key:
            return '<div class="text-red-600">Error: Missing MDM_API_KEY in .env</div>'

        api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{item_id}/?xrefItemInfo=false"
        headers = {
            "Api-Key": api_key,
            "Facilitynum": facility_num,
            "Facilitycountrycode": facility_country,
            "Wmt-Userid": wmt_userid
        }

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()
            data = response.json()

        return format_results(data, item_id)

    except httpx.HTTPStatusError as e:
        error_msg = f"API Error {e.response.status_code}"
        if e.response.status_code == 404:
            error_msg = "Item not found. Please check the Item ID and try again."
        elif e.response.status_code == 401:
            error_msg = "Unauthorized: Check your MDM_API_KEY in .env"
        return f'''<div class="bg-red-50 p-4 rounded border-2 border-red-300 text-center">
            <div class="text-red-700 font-bold text-lg">API Error</div>
            <p class="text-red-600 text-sm mt-2">{error_msg}</p>
        </div>'''
    except Exception as e:
        return f'''<div class="bg-red-50 p-4 rounded border-2 border-red-300 text-center">
            <div class="text-red-700 font-bold text-lg">Error</div>
            <p class="text-red-600 text-sm mt-2">{str(e)}</p>
        </div>'''


@app.get("/print-card", response_class=HTMLResponse)
async def print_card(item_id: str, product_id: str = "", gtin: str = "", supplier_dept: str = ""):
    try:
        api_key = os.getenv("MDM_API_KEY")
        facility_num = os.getenv("MDM_FACILITY_NUM", "6068")
        facility_country = os.getenv("MDM_FACILITY_COUNTRY_CODE", "US")
        wmt_userid = os.getenv("MDM_WMT_USERID", "mdm-ui")

        if not api_key:
            return '<div class="text-red-600">Error: Missing MDM_API_KEY in .env</div>'

        api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{item_id}/?xrefItemInfo=false"
        headers = {
            "Api-Key": api_key,
            "Facilitynum": facility_num,
            "Facilitycountrycode": facility_country,
            "Wmt-Userid": wmt_userid
        }

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()
            data = response.json()

        return generate_print_card(data, item_id)

    except Exception as e:
        return f'<div class="text-red-600">Error: {str(e)}</div>'


# ============================================================================
# ARCHIVED: PDF Generation Endpoints (deprecated in favor of client viewer)
# ============================================================================

@app.get("/print-card-pdf")
async def print_card_pdf(item_id: str, product_id: str = "", gtin: str = "", catalog_gtin: str = "", supplier_dept: str = ""):
    """[ARCHIVED] Generate PDF of the print card for download (MDM API)."""
    try:
        api_key = os.getenv("MDM_API_KEY")
        facility_num = os.getenv("MDM_FACILITY_NUM", "6068")
        facility_country = os.getenv("MDM_FACILITY_COUNTRY_CODE", "US")
        wmt_userid = os.getenv("MDM_WMT_USERID", "mdm-ui")

        if not api_key:
            return '<div class="text-red-600">Error: Missing MDM_API_KEY in .env</div>'

        api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{item_id}/?xrefItemInfo=false"
        headers = {
            "Api-Key": api_key,
            "Facilitynum": facility_num,
            "Facilitycountrycode": facility_country,
            "Wmt-Userid": wmt_userid
        }

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()
            data = response.json()

        item_data = extract_item_data(data)
        item_data["item_id"] = item_id  # Add the searched item_id
        pdf_bytes = generate_pdf(item_data)
        
        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in item_data["item_name"])
        safe_name = safe_name.replace(' ', '_').strip('_') + '.pdf'
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}"'}
        )

    except Exception as e:
        return f'<div class="text-red-600">Error: {str(e)}</div>'


def format_results(data: dict, item_id: str) -> str:
    json_str = json.dumps(data, indent=2)
    item_data = extract_item_data(data)
    item_name = item_data["item_name"]
    image_url = item_data["image_url"]
    gtin = item_data["gtin"]
    catalog_gtin = item_data.get("catalog_gtin", "")
    print(f"[PRINT-CARD] Item {item_id}: catalog_gtin='{catalog_gtin}'")
    
    # Load read rates for dropdown table
    rates = load_read_rates()
    product_id = item_data["product_id"]
    supplier_dept = item_data["supplier_dept"]

    image_html = ""
    if image_url:
        image_html = f'<img src="{image_url}" alt="{item_name}" class="w-full h-auto object-cover rounded border mb-2">'

    # Simple item details - minimal styling
    vnpk_len = item_data.get("vnpk_length", "")
    vnpk_wid = item_data.get("vnpk_width", "")
    vnpk_hgt = item_data.get("vnpk_height", "")
    casepack_type = item_data.get("casepack_type", "")
    vendor_qty = item_data.get("vendor_pack_qty", "")
    warehouse_qty = item_data.get("warehouse_pack_qty", "")
    
    item_details = f'<div class="text-center space-y-1 text-xs text-gray-700"><p><strong>Item:</strong> {item_id}</p>'
    if gtin:
        item_details += f'<p><strong>GTIN:</strong> {gtin}</p>'
    if catalog_gtin:
        item_details += f'<p><strong>Catalog GTIN:</strong> {catalog_gtin}</p>'
    if supplier_dept:
        item_details += f'<p><strong>Dept #:</strong> {supplier_dept}</p>'
    # Vendor/Warehouse Pack Ratio
    if vendor_qty and warehouse_qty:
        item_details += f'<p><strong>Pack Ratio:</strong> {vendor_qty}/{warehouse_qty}</p>'
    # Vendor Pack Dimensions
    if vnpk_len or vnpk_wid or vnpk_hgt:
        dims = []
        dims.append(vnpk_len if vnpk_len else "--")
        dims.append(vnpk_wid if vnpk_wid else "--")
        dims.append(vnpk_hgt if vnpk_hgt else "--")
        dims_str = " x ".join(dims)
        item_details += f'<p><strong>Pack Dims (L x W x H):</strong> {dims_str}"</p>'
    item_details += '</div>'

    print_params = urlencode({
        "item_id": item_id,
        "product_id": product_id,
        "gtin": gtin,
        "catalog_gtin": catalog_gtin,
        "supplier_dept": supplier_dept
    })
    print_card_html = f'<a href="/print-card-pdf?{print_params}" class="inline-block mt-2 px-4 py-2 bg-green-600 text-white text-sm rounded font-semibold hover:bg-green-700">Download PDF</a>'
    
    # Get the full chart/metrics/recommendation display
    right_html = get_read_rate_chart(item_id, vnpk_len, vnpk_wid, vnpk_hgt)

    # LEFT column: Product image and details
    # Build read rate table HTML with ALL schema columns
    read_rate_table_html = ""
    try:
        db_path = get_database_path()
        conn_db = sqlite3.connect(db_path)
        cursor_db = conn_db.cursor()
        cursor_db.execute("""
            SELECT id, acl_insert_date, ts_date, mds_fam_id, item1_desc,
                   pick_type_code, slot_id, vnpk_gtin_t,
                   acl_event_cnt, acl_null_cnt, acl_bypass_cnt,
                   good_read_cnt_null, good_read_cnt_bypass,
                   item_num_read_cnt_null, item_num_read_cnt_bypass, created_at
            FROM read_rates
            WHERE mds_fam_id = ?
            ORDER BY ts_date DESC
            LIMIT 30
        """, (str(item_id),))
        rows = cursor_db.fetchall()
        conn_db.close()
        
        if rows:
            # Build header
            cols = ['ID', 'Insert Date', 'TS Date', 'MDS Family', 'Item Desc', 'Pick Type', 'Slot', 'VNPK GTIN', 'Events', 'Nulls', 'Bypass', 'Good Read Null', 'Good Read Bypass', 'Item# Null', 'Item# Bypass', 'Created']
            read_rate_table_html = '<div class="overflow-x-auto"><table class="terder-collapse bg-white"><thead><tr class="bg-gray-200">'
            for col in cols:
                read_rate_table_html += f'<th class="border p-1 text-left">{col}</th>'
            read_rate_table_html += '</tr></thead><tbody>'
            # Add rows
            for row in rows:
                read_rate_table_html += '<tr class="hover:bg-gray-50">'
                for val in row:
                    read_rate_table_html += f'<td class="border p-1 text-xs">{val if val is not None else "-"}</td>'
                read_rate_table_html += '</tr>'
            read_rate_table_html += '</tbody></table></div>'
    except Exception as e:
        read_rate_table_html = f'<p class="text-red-600 text-xs">Error loading data: {str(e)[:100]}</p>'
    
    # Build casepack type card if available (will add to right section)
    casepack_card_html = ""
    if casepack_type:
        casepack_color = "#0ea5e9" if "CASEPACK" in casepack_type.upper() else "#ec4899"
        casepack_card_html = f'''<div class="bg-gradient-to-br from-blue-50 to-blue-100 p-6 rounded-xl border-2 border-blue-300 shadow-lg text-center mt-3">
            <div class="text-4xl font-black" style="color: {casepack_color};">{casepack_type}</div>
        </div>'''
    
    left_html = f"""<div class="space-y-3">
        <div class="bg-white p-3 rounded border">
            {image_html}
            <h2 class="font-bold text-xl text-blue-600 text-center mt-2 mb-1">{item_name}</h2>
            {item_details}
            <div class="text-center mt-2">{print_card_html}</div>
        </div>
        {'<details class="bg-white p-3 rounded border cursor-pointer group"><summary class="font-semibold text-xs text-gray-600 hover:text-gray-900 select-none">ACL Read Rate Data (Last 30 Days - All Columns)</summary><div class="mt-2 pt-2 border-t w-full">' + read_rate_table_html + '</div></details>' if read_rate_table_html else ''}
        <details class="bg-white p-3 rounded border cursor-pointer group">
            <summary class="font-semibold text-xs text-gray-600 hover:text-gray-900 select-none">Developer Info</summary>
            <div class="mt-2 pt-2 border-t">
                <pre class="text-xs bg-gray-50 p-2 rounded overflow-auto max-h-32 font-mono border">{json_str}</pre>
            </div>
        </details>
    </div>"""
    
    # Return grid with both columns
    return f'''<div class="grid grid-cols-1 lg:grid-cols-2 gap-2">
        {left_html}
        <div class="space-y-3">
            {right_html}
            {casepack_card_html}
        </div>
    </div>'''




def extract_item_data(data: dict) -> dict:
    """Extract product data from MDM API response."""
    item_data = {
        "item_name": "Unknown Item",
        "item_description": "Item Description",
        "item_id": "",
        "image_url": "",
        "gtin": "",
        "catalog_gtin": "",
        "product_id": "",
        "supplier_dept": "",
        "inventory_status": "Unknown",
        "vnpk_length": "",
        "vnpk_width": "",
        "vnpk_height": "",
        "casepack_type": "",
        "vendor_pack_qty": "",
        "warehouse_pack_qty": ""
    }
    
    # Debug: Show what's in the response
    if isinstance(data, dict):
        print(f"[EXTRACT] MDM response keys: {list(data.keys())}")
        # Log dcProperties structure if present
        if "dcProperties" in data and isinstance(data["dcProperties"], dict):
            dc_keys = list(data["dcProperties"].keys())
            print(f"[EXTRACT] dcProperties keys: {dc_keys}")
            if "supplyItem" in data["dcProperties"]:
                si_keys = list(data["dcProperties"]["supplyItem"].keys())
                print(f"[EXTRACT] supplyItem keys: {si_keys}")
    
    # MDM API response structure
    if isinstance(data, dict):
        # Item description/name
        if "description" in data and isinstance(data["description"], list) and len(data["description"]) > 0:
            desc = data["description"][0]
            if isinstance(desc, dict):
                item_data["item_name"] = desc.get("textValue", "Unknown Item").strip()
                # Use same as description for department band
                item_data["item_description"] = item_data["item_name"]
        
        # Item number
        if "number" in data:
            item_data["item_id"] = str(data["number"])
        
        # Image URL - use first available image size
        if "productDefinition" in data:
            prod_def = data["productDefinition"]
            if isinstance(prod_def, dict) and "imageDimension" in prod_def:
                img_dim = prod_def["imageDimension"]
                if isinstance(img_dim, dict):
                    # Try different sizes in order of preference
                    for size in ["IMAGE_SIZE_450", "IMAGE_SIZE_200", "IMAGE_SIZE_100", "IMAGE_SIZE_60"]:
                        if size in img_dim and img_dim[size]:
                            item_data["image_url"] = img_dim[size]
                            break
        
        # GTIN - use orderableGTIN (not consumableGTIN which is UPC)
        if "orderableGTIN" in data:
            item_data["gtin"] = data["orderableGTIN"]
        elif "consumableGTIN" in data:
            item_data["gtin"] = data["consumableGTIN"]
        
        # CatalogGTIN - dcProperties > supplyItem > catalogGTIN
        if "dcProperties" in data and isinstance(data["dcProperties"], dict):
            dc_props = data["dcProperties"]
            if "supplyItem" in dc_props and isinstance(dc_props["supplyItem"], dict):
                supply_item = dc_props["supplyItem"]
                if "catalogGTIN" in supply_item:
                    item_data["catalog_gtin"] = supply_item["catalogGTIN"]
        
        print(f"[EXTRACT] Item {item_data.get('item_id')}: catalog_gtin='{item_data['catalog_gtin']}'")
        
        # Product ID - use merchandiseFamilyID
        if "merchandiseFamilyID" in data:
            item_data["product_id"] = str(data["merchandiseFamilyID"])
        
        # Supplier Department
        if "supplierAgreement" in data:
            supp = data["supplierAgreement"]
            if isinstance(supp, dict) and "department" in supp:
                dept = supp["department"]
                if isinstance(dept, dict) and "number" in dept:
                    item_data["supplier_dept"] = str(dept["number"])
        
        # Vendorpack dimensions (Length, Width, Height)
        # Try multiple possible paths: vendorPackageDimension, dcProperties.supplyItem.tradeItems[0].dimensions, or productDefinition
        if "vendorPackageDimension" in data and isinstance(data["vendorPackageDimension"], dict):
            vpk_dim = data["vendorPackageDimension"]
            if "VNPK_LENGTH" in vpk_dim:
                item_data["vnpk_length"] = str(vpk_dim["VNPK_LENGTH"])
            if "VNPK_WIDTH" in vpk_dim:
                item_data["vnpk_width"] = str(vpk_dim["VNPK_WIDTH"])
            if "VNPK_HEIGHT" in vpk_dim:
                item_data["vnpk_height"] = str(vpk_dim["VNPK_HEIGHT"])
        # Fallback: Try dcProperties > supplyItem > tradeItems[0] > dimensions
        elif "dcProperties" in data and isinstance(data["dcProperties"], dict):
            dc = data["dcProperties"]
            if "supplyItem" in dc and isinstance(dc["supplyItem"], dict):
                si = dc["supplyItem"]
                # Extract vendor/warehouse pack quantities
                if "orderableQuantity" in si and isinstance(si["orderableQuantity"], dict):
                    item_data["vendor_pack_qty"] = str(si["orderableQuantity"].get("amount", ""))
                if "warehousePackQuantity" in si and isinstance(si["warehousePackQuantity"], dict):
                    item_data["warehouse_pack_qty"] = str(si["warehousePackQuantity"].get("amount", ""))
                
                # Extract dimensions from tradeItems
                if "tradeItems" in si and isinstance(si["tradeItems"], list) and len(si["tradeItems"]) > 0:
                    ti = si["tradeItems"][0]
                    if "dimensions" in ti and isinstance(ti["dimensions"], dict):
                        dims = ti["dimensions"]
                        # CORRECT mapping: depth=length, width=width, height=height
                        if "depth" in dims:
                            item_data["vnpk_length"] = str(dims["depth"])
                        if "width" in dims:
                            item_data["vnpk_width"] = str(dims["width"])
                        if "height" in dims:
                            item_data["vnpk_height"] = str(dims["height"])
        
        # Casepack type - from root level
        if "supplierCasePackType" in data and isinstance(data["supplierCasePackType"], dict):
            casepack = data["supplierCasePackType"]
            item_data["casepack_type"] = casepack.get("description", "").strip()
        
        # Status from status code
        if "status" in data:
            status = data["status"]
            if isinstance(status, dict):
                status_code = status.get("code", "")
                item_data["inventory_status"] = "Active" if status_code == "A" else f"Status: {status_code}"
    
    return item_data


def generate_print_card(data: dict, item_id: str) -> str:
    item_data = extract_item_data(data)
    item_name = item_data["item_name"]
    image_url = item_data["image_url"]
    gtin = item_data["gtin"]
    catalog_gtin = item_data.get("catalog_gtin", "")
    product_id = item_data["product_id"]
    supplier_dept = item_data["supplier_dept"]
    inventory_status = item_data["inventory_status"]
    
    # Get ACL recommendation if data available
    recommendation = "N/A"
    rec_color = "#6b7280"
    rates = load_read_rates()
    rate_data = rates.get(str(item_id), [])
    if rate_data and len(rate_data) > 0:
        avg_perf = get_avg_performance(rate_data)
        trend_status = get_trend_status(rate_data)
        recommendation, rec_color, _ = get_recommendation(avg_perf, trend_status, catalog_gtin, gtin)

    image_section = ""
    if image_url:
        image_section = f'<div class="card-image"><img src="{image_url}" alt="{item_name}"></div>'

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{item_name} - Print Card</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            padding: 20px;
            background: #f5f5f5;
        }}
        .print-container {{
            width: 100%;
            max-width: 11in;
            height: 8.5in;
            background: white;
            margin: 0 auto;
            padding: 40px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            display: grid;
            grid-template-columns: 3.5in 1fr;
            gap: 30px;
            align-items: start;
        }}
        .card-image {{
            width: 100%;
            height: 100%;
            max-height: 6.5in;
            overflow: hidden;
            border-radius: 8px;
            border: 2px solid #0071ce;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f9f9f9;
        }}
        .card-image img {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }}
        .card-content {{
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            gap: 16px;
        }}
        .product-name {{
            font-size: 24px;
            font-weight: bold;
            color: #0071ce;
            line-height: 1.3;
        }}
        .info-section {{
            border-top: 1px solid #ddd;
            padding-top: 12px;
        }}
        .info-row {{
            display: flex;
            margin-bottom: 10px;
            font-size: 13px;
        }}
        .info-label {{
            font-weight: 600;
            color: #333;
            width: 120px;
            flex-shrink: 0;
        }}
        .info-value {{
            color: #666;
            word-break: break-word;
            flex: 1;
        }}
        .status-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
            margin-top: 8px;
        }}
        .status-in-stock {{
            background: #d4edda;
            color: #155724;
        }}
        .status-unknown {{
            background: #fff3cd;
            color: #856404;
        }}
        .footer {{
            margin-top: 20px;
            font-size: 10px;
            color: #999;
            text-align: center;
            border-top: 1px solid #eee;
            padding-top: 10px;
        }}
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .print-container {{
                max-width: 100%;
                box-shadow: none;
                margin: 0;
            }}
            .no-print {{
                display: none;
            }}
        }}
        .no-print {{
            text-align: center;
            margin-top: 20px;
        }}
        .no-print button {{
            padding: 10px 24px;
            background: #0071ce;
            color: white;
            border: none;
            border-radius: 4px;
            font-weight: 600;
            cursor: pointer;
            margin: 0 8px;
        }}
        .no-print button:hover {{
            background: #005a9c;
        }}
    </style>
</head>
<body>
    <div class="print-container">
        {image_section}
        <div class="card-content">
            <div class="product-name">{item_name}</div>
            <div class="info-section">
                <div class="info-row">
                    <div class="info-label">Item ID:</div>
                    <div class="info-value">{item_id}</div>
                </div>
                {f'<div class="info-row"><div class="info-label">GTIN:</div><div class="info-value">{gtin}</div></div>' if gtin else ''}
                {'<div class="info-row"><div class="info-label">Catalog GTIN:</div><div class="info-value">' + catalog_gtin + '</div></div>' if catalog_gtin else ''}
                {f'<div class="info-row"><div class="info-label">Product ID:</div><div class="info-value">{product_id}</div></div>' if product_id else ''}
                {f'<div class="info-row"><div class="info-label">Supplier Dept:</div><div class="info-value">{supplier_dept}</div></div>' if supplier_dept else ''}
            </div>
            <div class="info-section">
                <div class="info-label">Inventory Status</div>
                <div class="status-badge {'status-in-stock' if 'In Stock' in inventory_status else 'status-unknown'}">{inventory_status}</div>
            </div>
            <div class="info-section" style="border: 3px solid {rec_color}; padding: 16px; border-radius: 6px; background: rgba(0,0,0,0.03); margin: 12px 0;">
                <div style="color: #333; font-weight: 700; font-size: 11px; text-align: center; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">ACL Directive Action</div>
                <div style="color: {rec_color}; font-weight: 900; font-size: 16px; text-align: center; line-height: 1.4;">{recommendation}</div>
            </div>
            <div class="footer">
                <p>CodePuppy DAR - Inventory Viewer</p>
                <p>Generated for quick reference</p>
            </div>
        </div>
    </div>
    <div class="no-print">
        <button onclick="window.print()">Print Card</button>
        <button onclick="window.history.back()">Back</button>
    </div>
</body>
</html>"""


def sanitize_for_pdf(text: str) -> str:
    """Remove Unicode chars that Helvetica font can't render."""
    if not text:
        return ""
    # Replace smart quotes and common Unicode chars with ASCII equivalents
    replacements = {
        "\u201c": '"',  # left double quote
        "\u201d": '"',  # right double quote
        "\u2018": "'",  # left single quote
        "\u2019": "'",  # right single quote
        "\u2013": "-",   # en dash
        "\u2014": "-",   # em dash
        "\u2022": "*",   # bullet
        "\u00a9": "(c)", # copyright
        "\u00ae": "(R)", # registered
        "\u2122": "(TM)", # trademark
    }
    result = str(text)
    for unicode_char, ascii_equiv in replacements.items():
        result = result.replace(unicode_char, ascii_equiv)
    # Strip any remaining non-ASCII characters
    return result.encode('ascii', errors='ignore').decode('ascii')


def generate_pdf(item_data: dict, master_pdf: FPDF = None, return_pdf_object: bool = False) -> bytes:
    """Generate a clean landscape PDF card with product information.
    
    If master_pdf is provided, add to that object instead of creating new.
    If return_pdf_object is True, return the FPDF object instead of bytes.
    """
    # Use provided PDF or create new one
    pdf = master_pdf if master_pdf else FPDF(orientation='L', unit='in', format='Letter')
    pdf.add_page()
    pdf.set_margins(0.4, 0.4, 0.4)
    
    item_name = sanitize_for_pdf(item_data.get("item_name", "Unknown Item"))
    image_url = item_data.get("image_url", "")
    gtin = sanitize_for_pdf(item_data.get("gtin", ""))
    catalog_gtin = sanitize_for_pdf(item_data.get("catalog_gtin", ""))
    product_id = sanitize_for_pdf(item_data.get("product_id", ""))
    supplier_dept = sanitize_for_pdf(item_data.get("supplier_dept", ""))
    inventory_status = sanitize_for_pdf(item_data.get("inventory_status", "Unknown"))
    vnpk_length = sanitize_for_pdf(item_data.get("vnpk_length", ""))
    vnpk_width = sanitize_for_pdf(item_data.get("vnpk_width", ""))
    vnpk_height = sanitize_for_pdf(item_data.get("vnpk_height", ""))
    casepack_type = sanitize_for_pdf(item_data.get("casepack_type", ""))
    vendor_qty = sanitize_for_pdf(item_data.get("vendor_pack_qty", ""))
    warehouse_qty = sanitize_for_pdf(item_data.get("warehouse_pack_qty", ""))
    # Keep original item_id for dictionary lookup, use sanitized version for PDF display
    item_id_orig = item_data.get("item_id", "")
    item_id = sanitize_for_pdf(item_id_orig)
    
    # DEBUG: Log what we extracted
    print(f"[PDF] Item {item_id_orig}: catalog_gtin='{catalog_gtin}', gtin='{gtin}', casepack='{casepack_type}'")
    
    # LEFT COLUMN: Product Image (larger)
    img_x = 0.4
    img_y = 0.4
    img_width = 3.2  # Wider
    img_height = 3.8  # Taller
    
    # Draw image border with shadow effect
    # Light shadow
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.01)
    pdf.rect(img_x + 0.05, img_y + 0.05, img_width, img_height)
    # Main border (Walmart Blue)
    pdf.set_draw_color(0, 83, 226)
    pdf.set_line_width(0.03)
    pdf.rect(img_x, img_y, img_width, img_height)
    
    if image_url:
        try:
            img_response = httpx.get(image_url, timeout=5)
            img_bytes = BytesIO(img_response.content)
            # Use unique temp file to avoid duplication
            temp_img = f"/tmp/product_{uuid.uuid4().hex[:8]}.jpg"
            with open(temp_img, 'wb') as f:
                f.write(img_bytes.getvalue())
            # Center image in the box
            pdf.image(temp_img, x=img_x+0.05, y=img_y+0.05, w=img_width-0.1, h=img_height-0.1)
        except Exception as e:
            print(f"[PDF] Image download failed: {str(e)}")
    
    # RIGHT COLUMN: Product Details (starting at x=3.8") - simpler layout
    content_x = 3.8
    current_y = 0.4
    
    # Product Name (title) - centered and larger, Walmart Blue
    pdf.set_xy(content_x, current_y)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 83, 226)  # Walmart Blue
    pdf.multi_cell(6.5, 0.32, item_name, align='C')
    current_y = pdf.get_y() + 0.1
    
    # Simple item details (small, plain text)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(content_x, current_y)
    
    details_text = f"Item: {item_id}"
    if gtin:
        details_text += f" | GTIN: {gtin}"
    if catalog_gtin:
        details_text += f" | Catalog GTIN: {catalog_gtin}"
    if supplier_dept:
        details_text += f" | Dept #: {supplier_dept}"
    
    # Add casepack type and pack ratio
    pack_info_text = ""
    if casepack_type:
        pack_info_text = f"Pack Type: {casepack_type}"
        if vendor_qty and warehouse_qty:
            pack_info_text += f" | Pack Ratio: {vendor_qty}/{warehouse_qty}"
    elif vendor_qty and warehouse_qty:
        pack_info_text = f"Pack Ratio: {vendor_qty}/{warehouse_qty}"
    
    # Add vendorpack dimensions if available
    dimensions_text = ""
    if vnpk_length or vnpk_width or vnpk_height:
        dims_list = []
        dims_list.append(vnpk_length if vnpk_length else "--")
        dims_list.append(vnpk_width if vnpk_width else "--")
        dims_list.append(vnpk_height if vnpk_height else "--")
        dimensions_text = "Vendor Pack Dims (L x W x H): " + " x ".join(dims_list)
    
    pdf.multi_cell(6.5, 0.2, details_text, align='C')
    current_y = pdf.get_y() + 0.1
    
    # Add pack info below details - WITH PROMINENT CARD FOR CASEPACK TYPE
    if casepack_type:
        # Draw colored box for pack type (bold card style)
        pdf.set_xy(content_x, current_y)
        # Background color for card
        if "CASEPACK" in casepack_type.upper():
            pdf.set_fill_color(224, 242, 254)  # Light blue
            pdf.set_text_color(0, 83, 226)  # Walmart blue
        else:
            pdf.set_fill_color(252, 231, 243)  # Light pink
            pdf.set_text_color(236, 72, 153)  # Pink
        
        # Draw box
        pdf.set_draw_color(0, 83, 226) if "CASEPACK" in casepack_type.upper() else pdf.set_draw_color(236, 72, 153)
        pdf.set_line_width(0.02)
        box_height = 0.4
        pdf.rect(content_x, current_y, 6.5, box_height, 'FD')  # F = fill, D = border
        
        # Add pack type text
        pdf.set_font("Helvetica", "B", 12)  # Bold, larger font
        pdf.set_xy(content_x + 0.1, current_y + 0.08)
        pdf.cell(6.3, 0.25, casepack_type, align='C')
        current_y += box_height + 0.05
    
    # Add pack ratio info if available
    if vendor_qty and warehouse_qty:
        pdf.set_xy(content_x, current_y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 100, 100)
        ratio_text = f"Pack Ratio: {vendor_qty}/{warehouse_qty}"
        pdf.multi_cell(6.5, 0.15, ratio_text, align='C')
        current_y = pdf.get_y() + 0.05
    
    # Add vendorpack dimensions below pack info
    if dimensions_text:
        pdf.set_xy(content_x, current_y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(6.5, 0.15, dimensions_text, align='C')
        current_y = pdf.get_y() + 0.1
    
    # Add Department Band Trio (3 bands: Dept # | Category | Description)
    dept_band = get_department_band(supplier_dept)
    if dept_band:
        band_height = 0.11  # HALF SIZE
        rgb = dept_band["rgb"]
        
        # Band 1: Department Number (COLORED)
        pdf.set_xy(content_x, current_y)
        pdf.set_fill_color(*rgb)
        pdf.set_draw_color(0, 0, 0)  # BLACK BORDER
        pdf.set_line_width(0.02)
        pdf.rect(content_x, current_y, 3.0, band_height, 'FD')
        pdf.set_xy(content_x + 0.05, current_y + 0.01)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(0, 0, 0)  # BLACK TEXT
        pdf.cell(2.9, band_height - 0.01, f"Dept. {supplier_dept}", align='L')
        current_y += band_height
        
        # Band 2: Category Name (CARDBOARD)
        pdf.set_xy(content_x, current_y)
        pdf.set_fill_color(196, 165, 123)  # Light brown/cardboard
        pdf.set_draw_color(0, 0, 0)  # BLACK BORDER
        pdf.set_line_width(0.02)
        pdf.rect(content_x, current_y, 3.0, band_height, 'FD')
        pdf.set_xy(content_x + 0.05, current_y + 0.01)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(0, 0, 0)  # BLACK TEXT
        pdf.cell(2.9, band_height - 0.01, dept_band['name'], align='L')
        current_y += band_height
        
        # Band 3: Item Description (CARDBOARD)
        item_desc = sanitize_for_pdf(item_data.get("item_description", "Item Description"))
        pdf.set_xy(content_x, current_y)
        pdf.set_fill_color(196, 165, 123)  # Light brown/cardboard
        pdf.set_draw_color(0, 0, 0)  # BLACK BORDER
        pdf.set_line_width(0.02)
        pdf.rect(content_x, current_y, 3.0, band_height, 'FD')
        pdf.set_xy(content_x + 0.05, current_y + 0.01)
        pdf.set_font("Helvetica", "B", 6)
        pdf.set_text_color(0, 0, 0)  # BLACK TEXT ON CARDBOARD
        pdf.cell(2.9, band_height - 0.01, item_desc, align='L')
        current_y += band_height + 0.05
    
    # Add Directive Action card (in right column, below product details)
    rates = load_read_rates()
    rate_data = rates.get(str(item_id_orig), [])
    recommendation = "N/A"
    rec_color_hex = "#6b7280"
    if rate_data and len(rate_data) > 0:
        avg_perf = get_avg_performance(rate_data)
        trend_status = get_trend_status(rate_data)
        recommendation, rec_color_hex, _ = get_recommendation(avg_perf, trend_status, catalog_gtin, gtin)
    
    # Color mapping - matching what get_recommendation() returns
    color_map = {
        "#16a34a": {  # Green (ACL APPROVED) - matches get_recommendation()
            "fill_bg": (220, 252, 231),     # Very light green background
            "border": (34, 197, 94),         # Bright green border
            "text": (34, 197, 94)            # Bright vibrant green text
        },
        "#eab308": {  # Amber (ADEQUATE/REQUIRES MANUAL)
            "fill_bg": (254, 243, 199),     # Light amber background
            "border": (245, 158, 11),        # Bright amber border
            "text": (245, 158, 11)           # Bright amber text
        },
        "#dc2626": {  # Red (WORKSTATION RECOMMENDED)
            "fill_bg": (254, 226, 226),     # Light red background
            "border": (220, 38, 38),         # Bright red border
            "text": (220, 38, 38)            # Bright red text
        },
        "#6b7280": {  # Gray (default)
            "fill_bg": (243, 244, 246),     # Light gray background
            "border": (107, 114, 128),       # Medium gray border
            "text": (107, 114, 128)          # Gray text
        }
    }
    
    colors = color_map.get(rec_color_hex, color_map["#6b7280"])
    print(f"[PDF] rec_color_hex={rec_color_hex}, using colors: {colors}")
    
    # Draw directive action box with colored background - matching web page
    pdf.set_xy(content_x, current_y)
    pdf.set_fill_color(colors["fill_bg"][0], colors["fill_bg"][1], colors["fill_bg"][2])
    pdf.set_draw_color(colors["border"][0], colors["border"][1], colors["border"][2])
    pdf.set_line_width(0.05)  # Thicker border
    pdf.rect(content_x, current_y, 6.5, 0.7, style='FD')
    
    # No title - just the action
    
    # Recommendation text - LARGE and BOLD, centered in box
    pdf.set_xy(content_x + 0.1, current_y + 0.15)
    pdf.set_font("Helvetica", "B", 16)  # Large bold text
    pdf.set_text_color(colors["text"][0], colors["text"][1], colors["text"][2])
    pdf.cell(6.3, 0.35, recommendation, align='C')
    
    current_y = current_y + 0.8
    
    # Move to bottom-left quadrant for ACL Performance section
    # Use a fixed position in the lower-left area only
    current_y = 5.2
    
    # Draw red dotted border box (bottom-left quadrant only)
    pdf.set_draw_color(255, 0, 0)  # Red
    pdf.set_line_width(0.02)
    # Dotted line using dashes
    box_x = 0.4
    box_y = 4.6
    box_width = 5.2  # Left half only, not full width
    box_height = 3.2
    
    # Draw dotted rectangle
    dash_length = 0.15
    gap_length = 0.1
    
    # Top line
    x = box_x
    while x < box_x + box_width:
        pdf.line(x, box_y, min(x + dash_length, box_x + box_width), box_y)
        x += dash_length + gap_length
    
    # Bottom line
    x = box_x
    while x < box_x + box_width:
        pdf.line(x, box_y + box_height, min(x + dash_length, box_x + box_width), box_y + box_height)
        x += dash_length + gap_length
    
    # Left line
    y = box_y
    while y < box_y + box_height:
        pdf.line(box_x, y, box_x, min(y + dash_length, box_y + box_height))
        y += dash_length + gap_length
    
    # Right line
    y = box_y
    while y < box_y + box_height:
        pdf.line(box_x + box_width, y, box_x + box_width, min(y + dash_length, box_y + box_height))
        y += dash_length + gap_length
    
    # Content inside box
    content_x_box = 0.6
    current_y_box = 5.0
    
    pdf.set_xy(content_x_box, current_y_box)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 83, 226)  # Walmart Blue
    pdf.cell(4.6, 0.3, "ACL Performance %", align='C')
    current_y_box += 0.4
    
    # Get read rates for this item (use original item_id for lookup)
    rates = load_read_rates()
    item_rates = rates.get(str(item_id_orig), [])
    
    if item_rates:
        # Calculate metrics
        avg_perf = get_avg_performance(item_rates)
        trend_status = get_trend_status(item_rates)
        color = get_color_for_performance(avg_perf)
        
        # Display metrics in two boxes side by side
        # AVG PERFORMANCE box
        pdf.set_fill_color(255, 250, 220)  # Light yellow
        pdf.set_draw_color(218, 165, 32)  # Goldenrod border
        pdf.set_line_width(0.02)
        pdf.rect(content_x_box, current_y_box, 2.1, 0.7, style='FD')
        
        pdf.set_xy(content_x_box + 0.1, current_y_box + 0.05)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(180, 140, 0)
        pdf.cell(1.9, 0.15, "AVG PERFORMANCE", align='C')
        
        pdf.set_xy(content_x_box + 0.1, current_y_box + 0.25)
        pdf.set_font("Helvetica", "B", 16)
        # Convert hex color to RGB
        if color == "#dc2626":
            pdf.set_text_color(220, 38, 38)
        elif color == "#f59e0b":
            pdf.set_text_color(245, 158, 11)
        elif color == "#eab308":
            pdf.set_text_color(234, 179, 8)
        else:  # green
            pdf.set_text_color(22, 163, 74)
        pdf.cell(1.9, 0.3, f"{avg_perf:.1f}%", align='C')
        
        # TREND box
        pdf.set_fill_color(240, 230, 255)  # Light purple
        pdf.set_draw_color(147, 112, 219)  # Medium purple border
        pdf.set_line_width(0.02)
        pdf.rect(content_x_box + 2.3, current_y_box, 2.1, 0.7, style='FD')
        
        pdf.set_xy(content_x_box + 2.4, current_y_box + 0.05)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(140, 100, 180)
        pdf.cell(1.9, 0.15, "TREND", align='C')
        
        pdf.set_xy(content_x_box + 2.4, current_y_box + 0.25)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(60, 20, 140)
        pdf.cell(1.9, 0.3, trend_status, align='C')
        
        current_y_box += 0.8
        
        # Draw trend visualization (smaller, compact)
        if len(item_rates) > 1:
            # Chart dimensions - compact
            chart_width = 2.8
            chart_height = 0.6
            chart_x = content_x_box + 0.2
            chart_y = current_y_box
            
            # Draw axes
            pdf.set_draw_color(100, 100, 100)
            pdf.set_line_width(0.015)
            pdf.line(chart_x, chart_y + chart_height, chart_x, chart_y)  # Y-axis
            pdf.line(chart_x, chart_y + chart_height, chart_x + chart_width, chart_y + chart_height)  # X-axis
            
            # Draw grid lines
            pdf.set_draw_color(200, 200, 200)
            pdf.set_line_width(0.008)
            for pct in [0, 50, 100]:
                y_pos = chart_y + chart_height - (pct / 100.0) * chart_height
                pdf.line(chart_x - 0.05, y_pos, chart_x + chart_width, y_pos)
            
            # Plot data points and connect with line
            pdf.set_draw_color(0, 83, 226)  # Walmart Blue
            pdf.set_line_width(0.02)
            
            points = []
            for rate in item_rates:
                x = chart_x + (len(points) / max(len(item_rates) - 1, 1)) * chart_width
                y = chart_y + chart_height - (rate['null_pct'] / 100.0) * chart_height
                points.append((x, y))
            
            # Draw line connecting points
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                pdf.line(x1, y1, x2, y2)
            
            # Draw points
            pdf.set_fill_color(0, 83, 226)
            for x, y in points:
                pdf.circle(x, y, 0.03, style='F')
    else:
        pdf.set_xy(content_x_box, current_y_box)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(6.8, 0.25, "No ACL data available", align='L')
    
    # Convert to bytes
    result = pdf.output(dest='S')
    return bytes(result) if isinstance(result, bytearray) else result




@app.post("/api/admin/set-database-path")
async def set_database_path(request: Request):
    """Update the DATABASE_PATH in .env file."""
    try:
        # Get path from JSON body
        body = await request.json()
        new_path = body.get("path")
        
        if not new_path:
            return JSONResponse({"status": "error", "message": "No path provided"}, status_code=400)
        
        # Update .env file
        env_path = Path(".env")
        env_content = ""
        
        # Read existing .env
        if env_path.exists():
            with open(env_path, "r") as f:
                lines = f.readlines()
                for line in lines:
                    if not line.startswith("DATABASE_PATH="):
                        env_content += line
        
        # Add/update DATABASE_PATH
        env_content += f"DATABASE_PATH={new_path}\n"
        
        # Write back
        with open(env_path, "w") as f:
            f.write(env_content)
        
        # Update .env in current process
        os.environ["DATABASE_PATH"] = new_path
        
        print(f"[ADMIN] Database path updated to: {new_path}")
        return JSONResponse({"status": "success", "message": f"Database path set to {new_path}", "path": new_path})
    
    except Exception as e:
        print(f"[ERROR] Failed to update database path: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/admin/sync-bigquery")
async def sync_bigquery():
    print("\n" + "="*70)
    print("[SYNC] BigQuery sync started")
    print("="*70)
    
    try:
        from gcs_sync import GoogleCloudSync
        from db import get_database_stats
        import sqlite3
        from datetime import datetime, timedelta
        
        print("[SYNC] Step 1: Initializing GoogleCloudSync...")
        sync = GoogleCloudSync()
        init_result = sync.initialize()
        if not init_result:
            print("[ERROR] Failed to initialize BigQuery")
            return JSONResponse({"status": "error", "message": "BigQuery init failed"}, status_code=400)
        print("[OK] BigQuery initialized")
        
        print("[SYNC] Step 2: Getting database stats...")
        stats = get_database_stats()
        max_date = stats.get('max_date', '2024-01-01')
        total_rows = stats.get('total_rows', 0)
        print(f"[OK] DB: {total_rows} rows, max_date={max_date}")
        
        print("[SYNC] Step 3: Connecting to database...")
        conn = sqlite3.connect("read_rates.db")
        cursor = conn.cursor()
        print("[OK] Connected")
        
        print("[SYNC] Step 4: Reading existing dates...")
        cursor.execute("SELECT DISTINCT acl_insert_date FROM read_rates ORDER BY acl_insert_date")
        existing_dates = {row[0] for row in cursor.fetchall()}
        print(f"[OK] Found {len(existing_dates)} dates in database")
        
        print("[SYNC] Step 5: Calculating missing dates...")
        if max_date and max_date != 'N/A':
            last_date = datetime.strptime(max_date, '%Y-%m-%d')
        else:
            last_date = datetime(2024, 1, 1)
        
        today = datetime.now()
        missing_dates = []
        current = last_date + timedelta(days=1)
        while current <= today:
            date_str = current.strftime('%Y-%m-%d')
            if date_str not in existing_dates:
                missing_dates.append(date_str)
            current += timedelta(days=1)
        
        print(f"[OK] Found {len(missing_dates)} missing dates")
        if missing_dates:
            print(f"     Range: {missing_dates[0]} to {missing_dates[-1]}")
        
        if not missing_dates:
            print("[OK] Database is current, no missing dates")
            conn.close()
            return JSONResponse({"status": "success", "message": "No missing dates", "rows_appended": 0, "dates_synced": 0})
        
        print(f"[SYNC] Step 6: Building BigQuery query...")
        print(f"[DEBUG] Missing {len(missing_dates)} dates to sync: {missing_dates}")
        # Use double quotes for BigQuery date strings
        dates_list = ", ".join([f'"{d}"' for d in missing_dates])
        query = f"""SELECT acl_insert_date, ts_date, mds_fam_id, slot_id, acl_event_cnt, acl_null_cnt, acl_bypass_cnt, good_read_cnt_null, good_read_cnt_bypass, item_num_read_cnt_null, item_num_read_cnt_bypass, item1_desc, pick_type_code, vnpk_gtin_t
            FROM `wmt-ambient-centeng.6068_Engineering.ACL_READ_RATE`
            WHERE PICK_TYPE_CODE NOT IN ('DPAL', 'LBSS')
            AND acl_insert_date IN ({dates_list})"""
        print("[OK] Query built with filter: PICK_TYPE_CODE NOT IN ('DPAL', 'LBSS')")
        print(f"[DEBUG] Query: {query[:250]}...")
        
        print(f"[SYNC] Step 7: Executing BigQuery query (may take 10-30 seconds)...")
        query_job = sync.client.query(query)
        results = query_job.result()
        print("[OK] Query executed")
        
        # Convert results to list to check length
        results_list = list(results)
        print(f"[IMPORTANT] BigQuery returned {len(results_list)} rows")
        
        if len(results_list) == 0:
            print(f"[WARNING] NO ROWS returned from BigQuery!")
            print(f"[WARNING] This means the 14 missing dates have NO data matching:")
            print(f"[WARNING]   WHERE PICK_TYPE_CODE NOT IN ('DPAL', 'LBSS')")
            print(f"[WARNING] The dates may only contain DPAL or LBSS pick types.")
            conn.close()
            return JSONResponse({"status": "success", "message": "BigQuery returned 0 rows (dates may only have DPAL/LBSS pick types)", "rows_appended": 0, "dates_synced": len(missing_dates)})
        
        print(f"[SYNC] Step 8: Processing and inserting {len(results_list)} rows...")
        inserted = 0
        total = 0
        duplicates = 0
        errors = 0
        
        for row in results_list:
            total += 1
            
            # Print details of first row
            if total == 1:
                print(f"[DEBUG] First row from BigQuery:")
                print(f"        acl_insert_date: {row.acl_insert_date}")
                print(f"        mds_fam_id: {row.mds_fam_id}")
                print(f"        acl_event_cnt: {row.acl_event_cnt}")
                print(f"        acl_null_cnt: {row.acl_null_cnt}")
            
            try:
                insert_sql = '''INSERT OR IGNORE INTO read_rates (acl_insert_date, ts_date, mds_fam_id, slot_id, acl_event_cnt, acl_null_cnt, acl_bypass_cnt, good_read_cnt_null, good_read_cnt_bypass, item_num_read_cnt_null, item_num_read_cnt_bypass, item1_desc, pick_type_code, vnpk_gtin_t) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
                insert_values = (str(row.acl_insert_date), str(row.ts_date) if row.ts_date else None, str(row.mds_fam_id), str(row.slot_id) if row.slot_id else None, int(row.acl_event_cnt) if row.acl_event_cnt else 0, int(row.acl_null_cnt) if row.acl_null_cnt else 0, int(row.acl_bypass_cnt) if row.acl_bypass_cnt else 0, int(row.good_read_cnt_null) if row.good_read_cnt_null else 0, int(row.good_read_cnt_bypass) if row.good_read_cnt_bypass else 0, int(row.item_num_read_cnt_null) if row.item_num_read_cnt_null else 0, int(row.item_num_read_cnt_bypass) if row.item_num_read_cnt_bypass else 0, str(row.item1_desc) if row.item1_desc else None, str(row.pick_type_code) if row.pick_type_code else None, str(row.vnpk_gtin_t) if row.vnpk_gtin_t else None)
                cursor.execute(insert_sql, insert_values)
                
                if cursor.rowcount > 0:
                    inserted += 1
                else:
                    duplicates += 1
                
                if total % 500 == 0:
                    print(f"     Processed {total} rows: {inserted} new, {duplicates} duplicates")
            
            except Exception as e:
                errors += 1
                print(f"[ERROR] Row {total} failed: {str(e)}")
                if errors <= 3:  # Only print first 3 errors
                    print(f"        Values: {insert_values}")
        
        print(f"\n[RESULTS]")
        print(f"  BigQuery returned: {total} rows")
        print(f"  Missing dates queried: {len(missing_dates)} dates ({missing_dates[0]} to {missing_dates[-1]})")
        print(f"  Inserted: {inserted} NEW rows")
        print(f"  Duplicates (already exist): {duplicates}")
        print(f"  Errors: {errors}")
        
        print("[SYNC] Step 9: Committing...")
        conn.commit()
        conn.close()
        print("[OK] Committed")
        
        print("\n" + "="*70)
        print(f"[SUCCESS] Sync complete: {len(missing_dates)} dates, {inserted} rows")
        print("="*70 + "\n")
        
        return JSONResponse({"status": "success", "message": f"Synced {len(missing_dates)} dates, {inserted} rows", "rows_appended": inserted, "dates_synced": len(missing_dates)})
    
    except Exception as e:
        print(f"\n[ERROR] Sync failed: {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*70 + "\n")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    # Get database path from configuration
    db_path = get_database_path()
    
    try:
        from db import get_database_stats
        stats = get_database_stats()
        total = stats.get('total_rows', 0)
        items = stats.get('unique_items', 0)
        min_d = stats.get('min_date', 'N/A')
        max_d = stats.get('max_date', 'N/A')
    except Exception as e:
        total = items = 'Error loading'
        min_d = max_d = str(e)
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodePuppy DAR - Admin</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <div class="max-w-2xl mx-auto p-6">
        <h1 class="text-3xl font-bold text-blue-600 mb-6">CodePuppy DAR - Admin</h1>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Database Status</h2>
            <table class="w-full text-sm">
                <tr class="border-b"><td class="py-2 font-semibold">Total Rows:</td><td class="py-2 text-right text-blue-600 font-bold">{total}</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">Unique Items:</td><td class="py-2 text-right text-blue-600 font-bold">{items}</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">Min Date:</td><td class="py-2 text-right font-mono">{min_d}</td></tr>
                <tr><td class="py-2 font-semibold">Max Date:</td><td class="py-2 text-right font-mono">{max_d}</td></tr>
            </table>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Database Path Settings</h2>
            <p class="text-sm text-gray-600 mb-3">Current path: <span class="font-mono bg-gray-100 px-2 py-1 text-blue-600">{db_path}</span></p>
            <div class="flex gap-2 mb-4">
                <input type="file" id="dbFileInput" accept=".db,.sqlite,.sqlite3" class="flex-1 px-3 py-2 border rounded text-sm" />
                <button onclick="updateDatabasePathFromFile()" class="px-4 py-2 bg-purple-600 text-white rounded font-semibold hover:bg-purple-700">Set From File</button>
            </div>
            <div id="path-status" class="text-sm hidden"></div>
            <p class="text-xs text-gray-500 mt-2">Click "Set From File" to browse and select your database file (.db, .sqlite, .sqlite3)</p>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">BigQuery Sync</h2>
            <p class="text-sm text-gray-600 mb-4">Synchronize missing dates from Google BigQuery ACL_READ_RATE table</p>
            <button onclick="syncBigQuery()" class="px-6 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700">Sync Missing Dates from BigQuery</button>
            <div id="sync-status" class="mt-4 text-sm hidden"></div>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">System Info</h2>
            <table class="w-full text-sm">
                <tr class="border-b"><td class="py-2 font-semibold">Database Path:</td><td class="py-2 text-right font-mono text-blue-600">{db_path}</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">Database Type:</td><td class="py-2 text-right">SQLite (read_rates.db)</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">API:</td><td class="py-2 text-right">MDM Item API</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">BigQuery:</td><td class="py-2 text-right font-mono text-sm">ACL_READ_RATE</td></tr>
                <tr><td class="py-2 font-semibold">Auth Method:</td><td class="py-2 text-right">MDM_API_KEY (.env)</td></tr>
            </table>
            <div class="mt-4 p-3 bg-blue-50 border-l-4 border-blue-400 rounded">
                <p class="text-xs text-blue-700"><strong>To change database path:</strong> Set <code>DATABASE_PATH</code> in .env (relative or absolute path)</p>
            </div>
        </div>
        
        <div class="bg-blue-50 border-l-4 border-blue-600 p-4 mb-6 rounded">
            <h3 class="font-bold text-blue-900 mb-2">Developer Tips</h3>
            <ul class="text-sm text-blue-800 space-y-1">
                <li>Press F12 to open Browser Console → Check [EXTRACT] logs</li>
                <li>Network tab → See MDM API responses in real-time</li>
                <li>See <strong>BROWSER_CONSOLE_DEBUGGING.md</strong> in the repo for detailed guide</li>
            </ul>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Scheduler.walmart.com</h2>
            <p class="text-sm text-gray-600 mb-4">Automatic authentication via PingFederate SSO</p>
            <div hx-get="/diagnostics/scheduler" hx-trigger="load" hx-swap="innerHTML"></div>
        </div>
        
        <div class="flex gap-3">
            <a href="/diagnostics/informix" class="inline-block px-4 py-2 bg-orange-600 text-white rounded font-semibold hover:bg-orange-700">Informix Connection Test</a>
            <a href="/" class="inline-block px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700">Back to Search</a>
        </div>
    </div>
    
    <script>
        async function updateDatabasePathFromFile() {{
            const fileInput = document.getElementById('dbFileInput');
            const file = fileInput.files[0];
            const statusDiv = document.getElementById('path-status');
            
            if (!file) {{
                statusDiv.classList.remove('hidden');
                statusDiv.innerHTML = '<div class="text-red-600">Please select a database file</div>';
                return;
            }}
            
            // Get full path from file
            const newPath = file.webkitRelativePath || file.name;
            
            statusDiv.classList.remove('hidden');
            statusDiv.innerHTML = '<div class="text-blue-600">Updating...</div>';
            
            try {{
                const response = await fetch('/api/admin/set-database-path', {{\n                    method: 'POST',\n                    headers: {{'Content-Type': 'application/json'}},\n                    body: JSON.stringify({{path: file.name, full_path: newPath}})\n                }});
                
                const result = await response.json();
                
                if (result.status === 'success') {{
                    statusDiv.innerHTML = `<div class="text-green-600 font-semibold">✓ Database path updated!</div>
                        <p class="text-sm text-gray-600 mt-2">New path: <code class="bg-gray-100 px-2">${{result.path}}</code></p>
                        <p class="text-sm text-gray-600">Refresh the page to apply changes.</p>`;
                    setTimeout(() => {{
                        location.reload();
                    }}, 2000);
                }} else {{
                    statusDiv.innerHTML = `<div class="text-red-600">✗ Error: ${{result.message}}</div>`;
                }}
            }} catch (err) {{
                statusDiv.innerHTML = `<div class="text-red-600">✗ Error: ${{err.message}}</div>`;
            }}
        }}
        
        async function syncBigQuery() {{
            const statusDiv = document.getElementById('sync-status');
            statusDiv.classList.remove('hidden');
            statusDiv.innerHTML = '<div class="text-blue-600">Syncing... please wait</div>';
            
            try {{
                const response = await fetch('/api/admin/sync-bigquery', {{\n                    method: 'POST',\n                    headers: {{'Content-Type': 'application/json'}}\n                }});
                
                const result = await response.json();
                
                if (result.status === 'success') {{
                    statusDiv.innerHTML = `
                        <div class="text-green-600 font-semibold">✓ Sync Complete</div>
                        <div class="text-sm text-gray-700 mt-2">
                            Rows appended: ${{result.rows_appended}}<br>
                            Dates synced: ${{result.dates_synced}}<br>
                            <a href="/admin" class="text-blue-600 underline mt-2 inline-block">Refresh page</a>
                        </div>
                    `;
                }} else {{
                    statusDiv.innerHTML = `<div class="text-red-600">✗ Error: ${{result.message}}</div>`;
                }}
            }} catch (err) {{
                statusDiv.innerHTML = `<div class="text-red-600">✗ Error: ${{err.message}}</div>`;
            }}
        }}
    </script>
    <script src="https://unpkg.com/htmx.org"></script>
</body>
</html>"""


@app.get("/diagnostics/informix", response_class=HTMLResponse)
async def informix_diagnostics():
    """Informix connection diagnostics page - NOT YET INTEGRATED"""
    import os
    
    # Get credentials from .env
    host = os.getenv("INFORMIX_HOST", "NOT SET")
    server = os.getenv("INFORMIX_SERVER", "NOT SET")
    port = os.getenv("INFORMIX_PORT", "NOT SET")
    database = os.getenv("INFORMIX_DATABASE", "NOT SET")
    user = os.getenv("INFORMIX_USER", "NOT SET")
    
    # Test connection
    connection_status = "Not Tested"
    status_color = "gray"
    error_msg = ""
    
    # Check pyodbc first
    try:
        import pyodbc
        from importlib.metadata import version as get_version
        pyodbc_available = True
        try:
            pyodbc_version = get_version('pyodbc')
        except Exception:
            pyodbc_version = "INSTALLED (version unknown)"
        odbc_drivers = pyodbc.drivers()
        odbc_driver_found = "IBM INFORMIX" in str(odbc_drivers) or "Informix" in str(odbc_drivers)
    except ImportError:
        pyodbc_available = False
        pyodbc_version = "NOT INSTALLED"
        odbc_drivers = []
        odbc_driver_found = False
    
    try:
        from informix_connect import InformixConnection
        conn = InformixConnection()
        conn.connect()
        connection_status = "Connected"
        status_color = "green"
        conn.disconnect()
    except ImportError as ie:
        connection_status = "Import Error"
        status_color = "yellow"
        error_msg = f"Module error: {str(ie)[:150]}"
    except Exception as e:
        connection_status = "Failed"
        status_color = "red"
        error_msg = str(e)[:200]  # First 200 chars
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Informix Diagnostics</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <div class="max-w-3xl mx-auto p-6">
        <h1 class="text-3xl font-bold text-blue-600 mb-6">Informix Connection Diagnostics</h1>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Connection Status</h2>
            <div class="flex items-center gap-3 mb-4">
                <div class="w-4 h-4 rounded-full bg-{status_color}-500"></div>
                <span class="text-lg font-semibold text-{status_color}-600">{connection_status}</span>
            </div>
            {f'<div class="bg-red-50 border border-red-300 rounded p-4 mt-4"><p class="text-red-800 text-sm font-mono">{error_msg}</p></div>' if error_msg else ''}
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">PyODBC & Driver Status</h2>
            <table class="w-full text-sm">
                <tr class="border-b"><td class="py-2 font-semibold">PyODBC Installed:</td><td class="py-2"><span class="{'text-green-600 font-semibold' if pyodbc_available else 'text-red-600 font-semibold'}">{pyodbc_version}</span></td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">ODBC Driver Found:</td><td class="py-2"><span class="{'text-green-600 font-semibold' if odbc_driver_found else 'text-red-600 font-semibold'}">{"YES - IBM INFORMIX" if odbc_driver_found else "NO - Need to install ODBC driver"}</span></td></tr>
                <tr><td class="py-2 font-semibold">Available Drivers:</td><td class="py-2 font-mono text-xs">{str(odbc_drivers)[:200] if odbc_drivers else "None detected"}</td></tr>
            </table>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Configuration</h2>
            <table class="w-full text-sm">
                <tr class="border-b"><td class="py-2 font-semibold">Host:</td><td class="py-2 font-mono text-gray-700">{host}</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">Server:</td><td class="py-2 font-mono text-gray-700">{server}</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">Port:</td><td class="py-2 font-mono text-gray-700">{port}</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">Database:</td><td class="py-2 font-mono text-gray-700">{database}</td></tr>
                <tr><td class="py-2 font-semibold">User:</td><td class="py-2 font-mono text-gray-700">{user}</td></tr>
            </table>
        </div>
        
        <div class="bg-yellow-50 border border-yellow-300 rounded-lg p-6 mb-6">
            <h3 class="font-bold text-yellow-900 mb-2">Status: NOT YET INTEGRATED</h3>
            <p class="text-sm text-yellow-800">This page is for testing Informix connections only. Integration with the search results is not yet active.</p>
            <p class="text-sm text-yellow-800 mt-2">Requires system sqlhosts configuration to connect.</p>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Test Query (When Connected)</h2>
            <p class="text-sm text-gray-600 mb-3">Query: <span class="font-mono bg-gray-100 px-2 py-1">SELECT * FROM rdc_db:informix.po_line LIMIT 10</span></p>
            <button hx-get="/test_informix_query" hx-target="#query-results" hx-swap="innerHTML" hx-indicator="#query-spinner" class="px-4 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700 mt-3">Execute Query</button>
            <div id="query-spinner" class="hidden mt-3"><span class="text-sm text-gray-600">Executing...</span></div>
            <div id="query-results" class="mt-4"></div>
        </div>
        
        <a href="/admin" class="inline-block px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700">Back to Admin</a>
    </div>
    <script src="https://unpkg.com/htmx.org"></script>
</body>
</html>
    """


@app.get("/diagnostics/scheduler", response_class=HTMLResponse)
async def scheduler_diagnostics():
    """Scheduler.walmart.com JWT token status."""
    from datetime import datetime
    import base64
    import json
    
    # Always read token directly from .env (not cached)
    token = os.getenv("SCHEDULER_JWT_TOKEN", "").strip()
    is_configured = bool(token)
    
    token_info = None
    if token:
        try:
            parts = token.split(".")
            if len(parts) == 3:
                payload_str = parts[1]
                padding = 4 - (len(payload_str) % 4)
                if padding != 4:
                    payload_str += "=" * padding
                token_info = json.loads(base64.urlsafe_b64decode(payload_str))
        except:
            pass
    html = '<div class="space-y-4">'
    
    # Token input
    html += '<div id="token-section" class="bg-blue-50 border-l-4 border-blue-400 rounded p-4">'
    html += '<h4 class="font-bold text-blue-900 mb-2">JWT Token</h4>'
    html += '<form hx-post="/api/scheduler/set-token" hx-target="#token-section" hx-swap="outerHTML" class="space-y-2">'
    html += '<textarea name="token" placeholder="Paste JWT token here" class="w-full px-3 py-2 border rounded text-xs font-mono" rows="3"></textarea>'
    html += '<button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700">Save Token</button>'
    html += '</form>'
    if is_configured:
        html += '<p class="text-sm text-green-700 mt-2">✓ Token loaded</p>'
    html += '</div>'
    
    # Search
    html += '<div class="bg-green-50 border-l-4 border-green-400 rounded p-4">'
    html += '<h4 class="font-bold text-green-900 mb-2">Search Deliveries</h4>'
    html += '<form hx-post="/api/scheduler/search" hx-target="#search-results" hx-swap="innerHTML" class="space-y-2">'
    html += '<input type="text" name="delivery_number" placeholder="Delivery number (globalSearchKeyword)" class="w-full px-3 py-2 border rounded" required>'
    html += '<button type="submit" class="px-4 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700">Search</button>'
    html += '</form>'
    html += '<div id="search-results" class="mt-4"></div>'
    html += '</div>'
    
    html += '</div>'
    return html
    
    # Search
    html += '<div class="bg-green-50 border-l-4 border-green-400 rounded p-4">'
    html += '<h4 class="font-bold text-green-900 mb-2">Search Deliveries</h4>'
    html += '<form hx-post="/api/scheduler/search" hx-target="#search-results" hx-swap="innerHTML" class="space-y-2">'
    html += '<input type="text" name="delivery_number" placeholder="Delivery number (globalSearchKeyword)" class="w-full px-3 py-2 border rounded" required>'
    html += '<button type="submit" class="px-4 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700">Search</button>'
    html += '</form>'
    html += '<div id="search-results" class="mt-4"></div>'
    html += '</div>'
    
    html += '</div>'
    return html


@app.post("/api/scheduler/set-token", response_class=HTMLResponse)
async def set_scheduler_token(request: Request):
    """Store JWT token in .env and return updated token section."""
    try:
        form = await request.form()
        token = form.get("token", "").strip()
        
        if not token:
            return '<p class="text-red-600">Token required</p>'
        
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        content = ""
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                content = f.read()
        
        lines = [l for l in content.split("\n") if not l.startswith("SCHEDULER_JWT_TOKEN=")]
        lines.append(f"SCHEDULER_JWT_TOKEN={token}")
        
        with open(env_file, "w") as f:
            f.write("\n".join(lines))
        
        # Return the entire token section with updated status
        html = '<div id="token-section" class="bg-blue-50 border-l-4 border-blue-400 rounded p-4">'
        html += '<h4 class="font-bold text-blue-900 mb-2">JWT Token</h4>'
        html += '<form hx-post="/api/scheduler/set-token" hx-target="#token-section" hx-swap="outerHTML" class="space-y-2">'
        html += '<textarea name="token" placeholder="Paste JWT token here" class="w-full px-3 py-2 border rounded text-xs font-mono" rows="3"></textarea>'
        html += '<button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700">Save Token</button>'
        html += '</form>'
        html += '<p class="text-sm text-green-700 mt-2">✓ Token loaded</p>'
        html += '</div>'
        return html
    except Exception as e:
        return f'<p class="text-red-600 text-sm">Error: {str(e)[:100]}</p>'


@app.post("/api/scheduler/search", response_class=HTMLResponse)
async def search_deliveries(request: Request):
    """Search scheduler using delivery number."""
    import json
    
    try:
        form = await request.form()
        delivery_number = form.get("delivery_number", "").strip()
        token = os.getenv("SCHEDULER_JWT_TOKEN", "").strip()
        
        if not delivery_number:
            return '<p class="text-red-600 text-sm">Delivery number required</p>'
        
        if not token:
            return '<p class="text-red-600 text-sm">Token not configured</p>'
        
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            resp = await client.post(
                "https://scheduler.walmart.com/ILP2/common-search-api/rest/delivery/search",
                headers={
                    "security_id": "d0h0pf7@ADLocal",
                    "wmt_sch_country": "US",
                    "country_code": "US",
                    "lang_code": "101",
                    "userType": "COMPANY",
                    "token": token,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={
                    "globalSearchKeyword": delivery_number,
                    "organization": "Walmart Stores Inc.",
                    "userName": "d0h0pf7@ADLocal"
                }
            )
        
        if resp.status_code == 401:
            return '<p class="text-red-600 text-sm">Token invalid/expired - update and try again</p>'
        
        if resp.status_code != 200:
            return f'<p class="text-red-600 text-sm">Error: HTTP {resp.status_code}</p>'
        
        data = resp.json()
        if not data or len(data) == 0:
            return '<p class="text-yellow-600 text-sm">No deliveries found</p>'
        
        delivery = data[0]  # First result
        
        # Format delivery details
        html = '<div class="space-y-4">'
        
        # Main delivery info
        html += '<div class="bg-white border rounded p-4">'
        html += '<h3 class="font-bold text-lg mb-3">Delivery Details</h3>'
        html += '<div class="grid grid-cols-2 gap-4 text-sm">'
        
        info_fields = [
            ('Delivery ID', delivery.get('deliveryId')),
            ('Load Number', delivery.get('loadNumber')),
            ('Status', delivery.get('deliveryStatus')),
            ('SCAC', delivery.get('scac')),
            ('Node', delivery.get('destinationNodeDets', {}).get('nodeName')),
            ('Delivery Type', delivery.get('deliveryType')),
            ('Inventory Type', delivery.get('inventoryTypeName')),
            ('Total Cases', delivery.get('totalCaseQty')),
            ('Appointment', delivery.get('appointmentDate')),
            ('Arrived', delivery.get('deliveryArrivedTimeStamp', 'N/A')[:10]),
            ('Window Time', delivery.get('manageWindowDets', {}).get('windowStartTime', 'N/A')),
            ('Country', delivery.get('countryCode')),
        ]
        
        for label, value in info_fields:
            html += f'<div><span class="font-semibold">{label}:</span> <span class="text-gray-700">{value or "N/A"}</span></div>'
        
        html += '</div></div>'
        
        # Purchase Orders section
        po_str = delivery.get('purchaseOrders', '')
        if po_str:
            pos = [po.strip() for po in po_str.split('|') if po.strip()]
            html += '<div class="bg-blue-50 border border-blue-200 rounded p-4">'
            html += f'<h3 class="font-bold text-lg mb-3">Purchase Orders ({len(pos)} total)</h3>'
            html += '<div class="grid grid-cols-4 gap-2 text-sm">'
            for po in pos:
                html += f'<div class="bg-white border border-blue-300 rounded px-3 py-2 font-mono text-xs">{po}</div>'
            html += '</div></div>'
        
        html += '</div>'
        return html
    
    except Exception as e:
        return f'<p class="text-red-600 text-sm">Error: {str(e)[:150]}</p>'






@app.get("/test_informix_query", response_class=HTMLResponse)
async def test_informix_query(query: str = None):
    """Execute a test query against Informix and return results."""
    if not query:
        query = "SELECT * FROM rdc_db:informix.po_line LIMIT 10"
    
    try:
        from informix_connect import InformixConnection
        
        conn = InformixConnection()
        conn.connect()
        cursor = conn.conn.cursor()
        
        # Execute the query
        cursor.execute(query)
        
        # Fetch column names
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        
        conn.disconnect()
        
        # Build HTML table with results
        if not rows:
            return '<div class="bg-blue-50 border border-blue-300 rounded p-4 mt-2"><p class="text-blue-800 text-sm">Query executed successfully. No rows returned.</p></div>'
        
        html = '<div class="mt-4 border rounded overflow-x-auto">'
        html += '<table class="w-full text-sm border-collapse">'
        html += '<thead class="bg-gray-200"><tr>'
        
        # Add header row
        for col in columns:
            html += f'<th class="border px-3 py-2 text-left font-semibold">{col}</th>'
        html += '</tr></thead><tbody>'
        
        # Add data rows
        for idx, row in enumerate(rows):
            bg_class = 'bg-gray-50' if idx % 2 == 0 else 'bg-white'
            html += f'<tr class="{bg_class}">'
            for cell in row:
                # Truncate long values
                cell_str = str(cell) if cell is not None else "NULL"
                if len(cell_str) > 100:
                    cell_str = cell_str[:100] + "..."
                html += f'<td class="border px-3 py-2 font-mono text-xs">{cell_str}</td>'
            html += '</tr>'
        
        html += '</tbody></table></div>'
        html += f'<p class="text-sm text-gray-600 mt-3">✓ Query executed successfully. Returned {len(rows)} row(s).</p>'
        
        return html
        
    except Exception as e:
        error_msg = str(e)
        return f'<div class="bg-red-50 border border-red-300 rounded p-4 mt-2"><p class="text-red-800 text-sm"><strong>Query Error:</strong> {error_msg}</p></div>'


# TESTING ENDPOINTS - Multi-item batch reporting (NOT PRODUCTION)
@app.get("/batch/random", response_class=HTMLResponse)
async def batch_random():
    """Testing: Show 3 random items with consolidated info."""
    from batch_report import get_random_items, get_item_read_rate_data
    
    # Get 3 random MDS_FAM_IDs
    item_ids = get_random_items(count=3)
    
    if not item_ids:
        return '<div class="p-6 text-red-600">Error: No items found in read_rates.db</div>'
    
    # Fetch MDM data and read rate data for each
    items_data = []
    
    for item_id in item_ids:
        try:
            # Fetch from MDM API
            api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{item_id}/?xrefItemInfo=false"
            api_key = os.getenv("MDM_API_KEY", "")
            facility_num = os.getenv("MDM_FACILITY_NUM", "6068")
            facility_country = os.getenv("MDM_FACILITY_COUNTRY_CODE", "US")
            wmt_userid = os.getenv("MDM_WMT_USERID", "mdm-ui")
            
            headers = {
                "Api-Key": api_key,
                "Facilitynum": facility_num,
                "Facilitycountrycode": facility_country,
                "Wmt-Userid": wmt_userid
            }
            
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.get(api_url, headers=headers)
                response.raise_for_status()
                mdm_data = response.json()
                item_data = extract_item_data(mdm_data)
                
                # Get read rate data
                rate_data_db = get_item_read_rate_data(item_id)
                
                items_data.append({
                    "item_id": item_id,
                    "mdm": mdm_data,
                    "item_data": item_data,
                    "read_rates": rate_data_db
                })
        except Exception as e:
            print(f"[BATCH] Error fetching {item_id}: {str(e)}")
            items_data.append({
                "item_id": item_id,
                "error": str(e)
            })
    
    # Build HTML with 3 consolidated cards
    cards_html = ""
    item_ids_str = ",".join([item["item_id"] for item in items_data if "item_id" in item])
    
    for idx, item in enumerate(items_data, 1):
        if "error" in item:
            cards_html += f'<div class="bg-red-50 p-4 rounded border-2 border-red-300 mb-4"><p class="text-red-700">Item {item["item_id"]}: {item["error"]}</p></div>'
            continue
        
        item_id = item["item_id"]
        item_info = item["item_data"]
        rate_db = item["read_rates"]
        
        image_html = f'<img src="{item_info["image_url"]}" class="w-full h-64 object-cover rounded border mb-2">' if item_info["image_url"] else '<div class="w-full h-64 bg-gray-200 rounded border mb-2 flex items-center justify-center"><p class="text-gray-500">No Image</p></div>'
        
        # Get ACL performance chart
        chart_html = get_read_rate_chart(item_id, 
                                        item_info.get("vnpk_length", ""),
                                        item_info.get("vnpk_width", ""),
                                        item_info.get("vnpk_height", ""))
        
        # Build casepack card
        casepack_type = item_info.get("casepack_type", "")
        casepack_card_html = ""
        if casepack_type:
            casepack_color = "#0ea5e9" if "CASEPACK" in casepack_type.upper() else "#ec4899"
            casepack_card_html = f'''<div class="bg-gradient-to-br from-blue-50 to-blue-100 p-6 rounded-xl border-2 border-blue-300 shadow-lg text-center">
                <div class="text-4xl font-black" style="color: {casepack_color};">{casepack_type}</div>
            </div>'''
        
        cards_html += f'''<div class="bg-white p-4 rounded border shadow mb-6">
            <h3 class="text-2xl font-bold text-blue-600 mb-4">Item {idx}: {item_info["item_name"]}</h3>
            
            <!-- Two-column layout: Left=Product, Right=Graph -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
                <div>
                    {image_html}
                    <div class="space-y-2 text-sm">
                        <p><strong>Item #:</strong> {item_id}</p>
                        <p><strong>GTIN:</strong> {item_info["gtin"]}</p>
                        <p><strong>Pack Type:</strong> {casepack_type if casepack_type else "N/A"}</p>
                        <p><strong>Dims (L×W×H):</strong> {item_info.get("vnpk_length", "--")} × {item_info.get("vnpk_width", "--")} × {item_info.get("vnpk_height", "--")}"</p>
                        <p><strong>Pack Ratio:</strong> {item_info.get("vendor_pack_qty", "--")}/{item_info.get("warehouse_pack_qty", "--")}</p>
                        <p><strong>Department:</strong> {item_info["supplier_dept"]}</p>
                        <p><strong>Records:</strong> {rate_db["record_count"]}</p>
                    </div>
                </div>
                <div>
                    {chart_html}
                </div>
            </div>
            {casepack_card_html}
            <div class="mt-4 text-center">
                <a href="/print-card-pdf?item_id={item_id}" class="inline-block px-6 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700">📥 Download PDF</a>
            </div>
        </div>'''
    
    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Batch Report - Testing</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-gray-100">
    <div class="w-full p-6" style="max-width: none;">
        <h1 class="text-4xl font-bold text-blue-600 mb-2">Batch Report - Testing</h1>
        <p class="text-sm text-gray-600 mb-6">Randomly selected 3 items from read_rates.db</p>
        
        <div class="mb-6 flex gap-3">
            <a href="/batch/random" class="px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700">🔄 Refresh (New 3 Items)</a>
            <a href="/batch/pdf?items={item_ids_str}" class="px-4 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700">📄 Download All 3 as PDF</a>
            <a href="/" class="px-4 py-2 bg-gray-600 text-white rounded font-semibold hover:bg-gray-700">← Back to Search</a>
        </div>
        
        <div class="yellow-box bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6 rounded">
            <p class="text-yellow-800 text-sm"><strong>TESTING FEATURE:</strong> 3 random items shown below. Click "📄 Download All 3 as PDF" for consolidated file, or individual "📥 Download PDF" buttons for single items. Use "Refresh" to get new items.</p>
        </div>
        
        <!-- ACL Directive Actions Ruleset -->
        <details class="bg-blue-50 border-l-4 border-blue-600 p-4 mb-6 rounded cursor-pointer">
            <summary class="font-bold text-blue-700 select-none">ACL Directive Actions Ruleset (Click to expand)</summary>
            <div class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <div class="bg-green-50 border border-green-300 p-3 rounded">
                    <div class="font-bold text-green-700">ACL APPROVED</div>
                    <div class="text-green-600">Performance >= 85%</div>
                    <div class="text-xs text-gray-600 mt-1">No action needed</div>
                </div>
                <div class="bg-yellow-50 border border-yellow-300 p-3 rounded">
                    <div class="font-bold text-yellow-700">ADEQUATE PERFORMANCE</div>
                    <div class="text-yellow-600">Performance < 85% & Improving</div>
                    <div class="text-xs text-gray-600 mt-1">Monitor closely</div>
                </div>
                <div class="bg-yellow-50 border border-yellow-300 p-3 rounded">
                    <div class="font-bold text-yellow-700">REQUIRES MANUAL INSPECTION</div>
                    <div class="text-yellow-600">Performance < 85% & Declining</div>
                    <div class="text-xs text-gray-600 mt-1">Review needed</div>
                </div>
                <div class="bg-red-50 border border-red-300 p-3 rounded">
                    <div class="font-bold text-red-700">WORKSTATION RECOMMENDED</div>
                    <div class="text-red-600">Performance < 50%</div>
                    <div class="text-xs text-gray-600 mt-1">Immediate action required</div>
                </div>
                <div class="bg-red-50 border border-red-300 p-3 rounded">
                    <div class="font-bold text-red-700">WORKSTATION: NON-CONVEYABLE</div>
                    <div class="text-red-600">Longest side < 7" OR 2nd longest < 5" OR smallest < 2"</div>
                    <div class="text-xs text-gray-600 mt-1">Size-based constraint</div>
                </div>
                <div class="bg-red-50 border border-red-300 p-3 rounded">
                    <div class="font-bold text-red-700">INSPECT CATALOG; TAKE TO PROBLEMS</div>
                    <div class="text-red-600">Performance < 50% & Catalog GTIN exists</div>
                    <div class="text-xs text-gray-600 mt-1">Catalog mismatch requires review</div>
                </div>
            </div>
            <div class="mt-3 text-xs text-gray-600 italic">Note: These rules are directive guidelines subject to change</div>
        </details>
        
        <!-- Department Band Templates -->
        <details class="bg-purple-50 border-l-4 border-purple-600 p-4 mb-6 rounded cursor-pointer">
            <summary class="font-bold text-purple-700 select-none">Department Band Templates (Click to expand)</summary>
            <div class="mt-4 space-y-3">
                <div class="text-sm text-gray-700 mb-4">Sample department bands showing Dept # | Category | Item Description layout:</div>
                
                <!-- D.09 Sporting Goods Example -->
                <div class="space-y-0">
                    <div style="background-color: #00A4A6; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; font-size: 0.95rem;">Dept. 09</div>
                    <div style="background-color: #00A4A6; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.9rem;">Sporting Goods</div>
                    <div style="background-color: #C4A57B; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.85rem;">Example Item Description</div>
                </div>
                
                <!-- D.23 Mens Wear Example -->
                <div class="space-y-0" style="margin-top: 12px;">
                    <div style="background-color: #003DA5; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; font-size: 0.95rem;">Dept. 23</div>
                    <div style="background-color: #003DA5; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.9rem;">Mens Wear</div>
                    <div style="background-color: #C4A57B; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.85rem;">Example Item Description</div>
                </div>
                
                <!-- D.02 HBA Example -->
                <div class="space-y-0" style="margin-top: 12px;">
                    <div style="background-color: #FF8C00; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; font-size: 0.95rem;">Dept. 02</div>
                    <div style="background-color: #FF8C00; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.9rem;">HBA</div>
                    <div style="background-color: #C4A57B; color: black; padding: 10px; font-weight: bold; text-align: left; border: 2px solid black; border-top: none; font-size: 0.85rem;">Example Item Description</div>
                </div>
            </div>
        </details>
        
        {cards_html}
    </div>
</body>
</html>'''


def generate_batch_pdf(items_data: list) -> bytes:
    """Generate multi-page PDF with all items - REFACTORED LAYOUT.
    
    NEW LAYOUT ORDER (right column):
    1. Item Name (large blue header)
    2. Item Details (Item # | GTIN | Catalog GTIN | Dept #)
    3. DIRECTIVE ACTION CARD (TOP - emphasized, colored, large font)
    4. Casepack Card
    5. Pack Ratio
    6. Vendor Pack Dimensions
    7. ACL Performance Section (light background, NOT dashed border):
       - AVG PERFORMANCE + TREND boxes
       - Trend chart with AXIS LABELS (0%, 50%, 100%)
    """
    if not items_data:
        raise ValueError("No items provided")
    
    master_pdf = FPDF(orientation='L', unit='in', format='Letter')
    
    for idx, item_data in enumerate(items_data):
        print(f"[BATCH-PDF] Building page {idx + 1}")
        
        master_pdf.add_page()
        master_pdf.set_margins(0.4, 0.4, 0.4)
        
        # Extract all data
        item_name = sanitize_for_pdf(item_data.get("item_name", "Unknown"))
        image_url = item_data.get("image_url", "")
        gtin = sanitize_for_pdf(item_data.get("gtin", ""))
        catalog_gtin = sanitize_for_pdf(item_data.get("catalog_gtin", ""))
        supplier_dept = sanitize_for_pdf(item_data.get("supplier_dept", ""))
        vnpk_length = sanitize_for_pdf(item_data.get("vnpk_length", ""))
        vnpk_width = sanitize_for_pdf(item_data.get("vnpk_width", ""))
        vnpk_height = sanitize_for_pdf(item_data.get("vnpk_height", ""))
        casepack_type = sanitize_for_pdf(item_data.get("casepack_type", ""))
        vendor_qty = sanitize_for_pdf(item_data.get("vendor_pack_qty", ""))
        warehouse_qty = sanitize_for_pdf(item_data.get("warehouse_pack_qty", ""))
        item_id_orig = item_data.get("item_id", "")
        item_id = sanitize_for_pdf(item_id_orig)
        
        # LEFT COLUMN: Product Image
        img_x, img_y, img_width, img_height = 0.4, 0.4, 3.2, 3.8
        
        # Image border
        master_pdf.set_draw_color(220, 220, 220)
        master_pdf.set_line_width(0.01)
        master_pdf.rect(img_x + 0.05, img_y + 0.05, img_width, img_height)
        master_pdf.set_draw_color(0, 83, 226)
        master_pdf.set_line_width(0.03)
        master_pdf.rect(img_x, img_y, img_width, img_height)
        
        # Embed image
        if image_url:
            try:
                img_response = httpx.get(image_url, timeout=5)
                temp_img = f"/tmp/product_{uuid.uuid4().hex[:8]}.jpg"
                with open(temp_img, 'wb') as f:
                    f.write(img_response.content)
                master_pdf.image(temp_img, x=img_x+0.05, y=img_y+0.05, w=img_width-0.1, h=img_height-0.1)
            except:
                pass
        
        # RIGHT COLUMN: Details (moved right for better spacing from image)
        content_x = 4.2
        current_y = 0.4
        
        # 1. Item Name (header)
        master_pdf.set_xy(content_x, current_y)
        master_pdf.set_font("Helvetica", "B", 18)
        master_pdf.set_text_color(0, 83, 226)
        master_pdf.multi_cell(6.5, 0.3, item_name, align='C')
        current_y = master_pdf.get_y() + 0.1
        
        # 2. Item Details
        master_pdf.set_xy(content_x, current_y)
        master_pdf.set_font("Helvetica", "", 9)
        master_pdf.set_text_color(100, 100, 100)
        details = f"Item: {item_id}"
        if gtin:
            details += f" | GTIN: {gtin}"
        if catalog_gtin:
            details += f" | Catalog GTIN: {catalog_gtin}"
        if supplier_dept:
            details += f" | Dept #: {supplier_dept}"
        master_pdf.multi_cell(6.5, 0.15, details, align='C')
        current_y = master_pdf.get_y() + 0.1
        
        # 2b. Pack Ratio (moved to top)
        if vendor_qty and warehouse_qty:
            master_pdf.set_xy(content_x, current_y)
            master_pdf.set_font("Helvetica", "", 8)
            master_pdf.set_text_color(100, 100, 100)
            master_pdf.multi_cell(6.0, 0.15, f"VNPK/WHPK: {vendor_qty}/{warehouse_qty}", align='C')
            current_y = master_pdf.get_y() + 0.02
        
        # 2c. Dimensions (moved to top)
        if vnpk_length or vnpk_width or vnpk_height:
            master_pdf.set_xy(content_x, current_y)
            master_pdf.set_font("Helvetica", "", 8)
            master_pdf.set_text_color(100, 100, 100)
            dims = f"Vendor Dims (L × W × H): {vnpk_length or '--'} × {vnpk_width or '--'} × {vnpk_height or '--'}"
            master_pdf.multi_cell(6.0, 0.15, dims, align='C')
            current_y = master_pdf.get_y() + 0.1
        
        # 2d. Department Band Trio (3 bands: Dept  | Description)
        dept_band = get_department_band(supplier_dept)
        if dept_band:
            band_height = 0.11  # HALF SIZE
            rgb = dept_band["rgb"]
            
            # Band 1: Department Number (COLORED)
            master_pdf.set_xy(content_x, current_y)
            master_pdf.set_fill_color(*rgb)
            master_pdf.set_draw_color(0, 0, 0)  # BLACK BORDER
            master_pdf.set_line_width(0.02)
            master_pdf.rect(content_x, current_y, 3.0, band_height, 'FD')
            master_pdf.set_xy(content_x + 0.05, current_y + 0.01)
            master_pdf.set_font("Helvetica", "B", 7)
            master_pdf.set_text_color(0, 0, 0)  # BLACK TEXT
            master_pdf.cell(2.9, band_height - 0.01, f"Dept. {supplier_dept}", align='L')
            current_y += band_height
            
            # Band 2: Category Name (CARDBOARD)
            master_pdf.set_xy(content_x, current_y)
            master_pdf.set_fill_color(196, 165, 123)  # Light brown/cardboard
            master_pdf.set_draw_color(0, 0, 0)  # BLACK BORDER
            master_pdf.set_line_width(0.02)
            master_pdf.rect(content_x, current_y, 3.0, band_height, 'FD')
            master_pdf.set_xy(content_x + 0.05, current_y + 0.01)
            master_pdf.set_font("Helvetica", "B", 7)
            master_pdf.set_text_color(0, 0, 0)  # BLACK TEXT
            master_pdf.cell(2.9, band_height - 0.01, dept_band['name'], align='L')
            current_y += band_height
    
            # Band 3: Item Description (CARDBOARD)
            item_desc = sanitize_for_pdf(item_data.get("item_description", "Item Description"))
            master_pdf.set_xy(content_x, current_y)
            master_pdf.set_fill_color(196, 165, 123)  # Light brown/cardboard
            master_pdf.set_draw_color(0, 0, 0)  # BLACK BORDER
            master_pdf.set_line_width(0.02)
            master_pdf.rect(content_x, current_y, 3.0, band_height, 'FD')
            master_pdf.set_xy(content_x + 0.05, current_y + 0.01)
            master_pdf.set_font("Helvetica", "B", 6)
            master_pdf.set_text_color(0, 0, 0)  # BLACK TEXT ON CARDBOARD
            master_pdf.cell(2.9, band_height - 0.01, item_desc, align='L')
            current_y += band_height + 0.05
        
        # 3. DIRECTIVE ACTION CARD (TOP - EMPHASIZED)
        rates = load_read_rates()
        item_rates = rates.get(str(item_id_orig), [])
        
        recommendation = "N/A"
        rec_color_hex = "#6b7280"
        if item_rates:
            try:
                avg_perf = get_avg_performance(item_rates)
                trend_status = get_trend_status(item_rates)
                recommendation, rec_color_hex, _ = get_recommendation(avg_perf, trend_status, catalog_gtin, gtin)
            except:
                pass
        
        color_map = {
            "#16a34a": {"fill_bg": (220, 252, 231), "border": (34, 197, 94), "text": (34, 197, 94)},
            "#eab308": {"fill_bg": (254, 243, 199), "border": (245, 158, 11), "text": (245, 158, 11)},
            "#dc2626": {"fill_bg": (254, 226, 226), "border": (220, 38, 38), "text": (220, 38, 38)},
            "#6b7280": {"fill_bg": (243, 244, 246), "border": (107, 114, 128), "text": (107, 114, 128)}
        }
        
        colors = color_map.get(rec_color_hex, color_map["#6b7280"])
        
        # DIRECTIVE ACTION CARD - LARGE AND PROMINENT
        master_pdf.set_xy(content_x, current_y)
        master_pdf.set_fill_color(*colors["fill_bg"])
        master_pdf.set_draw_color(*colors["border"])
        master_pdf.set_line_width(0.03)
        master_pdf.rect(content_x, current_y, 6.5, 0.55, 'FD')
        master_pdf.set_font("Helvetica", "B", 13)  # LARGER FONT
        master_pdf.set_text_color(*colors["text"])
        master_pdf.set_xy(content_x + 0.2, current_y + 0.12)
        master_pdf.cell(6.1, 0.3, recommendation, align='C')
        current_y += 0.65
        
        # 4. Casepack Card
        if casepack_type:
            master_pdf.set_xy(content_x, current_y)
            if "CASEPACK" in casepack_type.upper():
                master_pdf.set_fill_color(224, 242, 254)
                master_pdf.set_text_color(0, 83, 226)
                master_pdf.set_draw_color(0, 83, 226)
            else:
                master_pdf.set_fill_color(252, 231, 243)
                master_pdf.set_text_color(236, 72, 153)
                master_pdf.set_draw_color(236, 72, 153)
            
            master_pdf.set_line_width(0.02)
            master_pdf.rect(content_x, current_y, 6.5, 0.4, 'FD')
            master_pdf.set_font("Helvetica", "B", 12)
            master_pdf.set_xy(content_x + 0.1, current_y + 0.08)
            master_pdf.cell(6.3, 0.25, casepack_type, align='C')
            current_y += 0.45
        
        # 6. ACL PERFORMANCE SECTION with LIGHT BACKGROUND (NOT dashed border)
        # Add more spacing before ACL section
        current_y += 0.15
        acl_bg_y = current_y
        
        # Light background fill for ACL section
        master_pdf.set_xy(content_x - 0.05, acl_bg_y)
        master_pdf.set_fill_color(240, 248, 255)  # Alice blue (light background)
        master_pdf.set_draw_color(200, 220, 240)  # Light blue border
        master_pdf.set_line_width(0.01)
        master_pdf.rect(content_x - 0.05, acl_bg_y, 6.6, 1.65, 'FD')
        
        # ACL Label
        master_pdf.set_xy(content_x, current_y)
        master_pdf.set_font("Helvetica", "B", 12)
        master_pdf.set_text_color(0, 83, 226)
        master_pdf.cell(6.5, 0.25, "ACL Performance %", align='C')
        current_y += 0.3
        
        if item_rates:
            avg_perf = get_avg_performance(item_rates)
            trend_status = get_trend_status(item_rates).upper()  # ALL CAPS
            color = get_color_for_performance(avg_perf)
            
            # AVG PERFORMANCE box
            master_pdf.set_xy(content_x, current_y)
            master_pdf.set_fill_color(255, 250, 220)
            master_pdf.set_draw_color(218, 165, 32)
            master_pdf.set_line_width(0.02)
            master_pdf.rect(content_x, current_y, 3.2, 0.65, style='FD')
            
            master_pdf.set_xy(content_x, current_y + 0.03)
            master_pdf.set_font("Helvetica", "B", 6)
            master_pdf.set_text_color(180, 140, 0)
            master_pdf.cell(3.2, 0.12, "AVG PERFORMANCE", align='C')
            
            master_pdf.set_xy(content_x, current_y + 0.2)
            master_pdf.set_font("Helvetica", "B", 15)
            if color == "#dc2626":
                master_pdf.set_text_color(220, 38, 38)
            elif color == "#eab308":
                master_pdf.set_text_color(234, 179, 8)
            else:
                master_pdf.set_text_color(22, 163, 74)
            master_pdf.cell(3.2, 0.25, f"{avg_perf:.1f}%", align='C')
            
            # TREND box
            master_pdf.set_xy(content_x + 3.3, current_y)
            master_pdf.set_fill_color(240, 230, 255)
            master_pdf.set_draw_color(147, 112, 219)
            master_pdf.set_line_width(0.02)
            master_pdf.rect(content_x + 3.3, current_y, 3.2, 0.65, style='FD')
            
            master_pdf.set_xy(content_x + 3.3, current_y + 0.03)
            master_pdf.set_font("Helvetica", "B", 6)
            master_pdf.set_text_color(140, 100, 180)
            master_pdf.cell(3.2, 0.12, "TREND", align='C')
            
            master_pdf.set_xy(content_x + 3.3, current_y + 0.2)
            master_pdf.set_font("Helvetica", "B", 11)
            master_pdf.set_text_color(60, 20, 140)
            master_pdf.cell(3.2, 0.25, trend_status, align='C')
            
            current_y += 0.7
            
            # Chart with AXIS LABELS
            if len(item_rates) > 1:
                chart_x, chart_y = content_x + 0.2, current_y
                chart_width, chart_height = 6.1, 0.45
                
                # Draw axes
                master_pdf.set_draw_color(100, 100, 100)
                master_pdf.set_line_width(0.015)
                master_pdf.line(chart_x, chart_y + chart_height, chart_x, chart_y)
                master_pdf.line(chart_x, chart_y + chart_height, chart_x + chart_width, chart_y + chart_height)
                
                # Grid lines with labels
                master_pdf.set_draw_color(200, 200, 200)
                master_pdf.set_line_width(0.008)
                master_pdf.set_font("Helvetica", "", 6)
                master_pdf.set_text_color(100, 100, 100)
                
                for pct in [0, 50, 100]:
                    y_pos = chart_y + chart_height - (pct / 100.0) * chart_height
                    master_pdf.line(chart_x - 0.05, y_pos, chart_x + chart_width, y_pos)
                    # Add axis label INSIDE chart (top-left corner)
                    if pct == 100:
                        master_pdf.set_xy(chart_x + 0.05, chart_y - 0.05)
                        master_pdf.cell(0.2, 0.08, "100%", align='L')
                
                # Plot data
                master_pdf.set_draw_color(0, 83, 226)
                master_pdf.set_line_width(0.02)
                
                points = []
                for rate in item_rates:
                    x = chart_x + (len(points) / max(len(item_rates) - 1, 1)) * chart_width
                    y = chart_y + chart_height - (rate['null_pct'] / 100.0) * chart_height
                    points.append((x, y))
                
                for i in range(len(points) - 1):
                    x1, y1 = points[i]
                    x2, y2 = points[i + 1]
                    master_pdf.line(x1, y1, x2, y2)
                
                master_pdf.set_fill_color(0, 83, 226)
                for x, y in points:
                    master_pdf.circle(x, y, 0.025, style='F')
        
        print(f"[BATCH-PDF] Page {idx + 1} complete")
    
    # Output
    pdf_output = master_pdf.output()
    pdf_bytes = bytes(pdf_output) if isinstance(pdf_output, bytearray) else pdf_output
    print(f"[BATCH-PDF] Final: {len(pdf_bytes)} bytes, {master_pdf.page} pages")
    return pdf_bytes


def generate_batch_pdf_OLD(items_data: list) -> bytes:
    """OLD VERSION - DEPRECATED"""
    if not items_data:
        raise ValueError("No items provided")
    
    # Create single master PDF that will contain all items
    pdf = FPDF(orientation='L', unit='in', format='Letter')
    
    for page_idx, item_data in enumerate(items_data):
        # Add new page for each item
        pdf.add_page()
        pdf.set_margins(0.4, 0.4, 0.4)
        
        item_name = sanitize_for_pdf(item_data.get("item_name", "Unknown Item"))
        image_url = item_data.get("image_url", "")
        gtin = sanitize_for_pdf(item_data.get("gtin", ""))
        item_id_orig = item_data.get("item_id", "")
        item_id = sanitize_for_pdf(item_id_orig)
        vnpk_length = sanitize_for_pdf(item_data.get("vnpk_length", ""))
        vnpk_width = sanitize_for_pdf(item_data.get("vnpk_width", ""))
        vnpk_height = sanitize_for_pdf(item_data.get("vnpk_height", ""))
        casepack_type = sanitize_for_pdf(item_data.get("casepack_type", ""))
        vendor_qty = sanitize_for_pdf(item_data.get("vendor_pack_qty", ""))
        warehouse_qty = sanitize_for_pdf(item_data.get("warehouse_pack_qty", ""))
        
        # LEFT COLUMN: Product Image
        img_x = 0.4
        img_y = 0.4
        img_width = 3.2
        img_height = 3.8
        
        # Draw image border
        pdf.set_draw_color(220, 220, 220)
        pdf.set_line_width(0.01)
        pdf.rect(img_x + 0.05, img_y + 0.05, img_width, img_height)
        pdf.set_draw_color(0, 83, 226)
        pdf.set_line_width(0.03)
        pdf.rect(img_x, img_y, img_width, img_height)
        
        # Download and embed image
        if image_url:
            try:
                img_response = httpx.get(image_url, timeout=5)
                temp_img = f"/tmp/product_{uuid.uuid4().hex[:8]}.jpg"
                with open(temp_img, 'wb') as f:
                    f.write(img_response.content)
                pdf.image(temp_img, x=img_x+0.05, y=img_y+0.05, w=img_width-0.1, h=img_height-0.1)
            except Exception as e:
                print(f"[BATCH-PDF] Image failed for item {page_idx + 1}: {str(e)}")
        
        # RIGHT COLUMN: Details
        content_x = 3.8
        current_y = 0.4
        
        # Title
        pdf.set_xy(content_x, current_y)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(0, 83, 226)
        pdf.multi_cell(6.5, 0.3, item_name, align='C')
        current_y = pdf.get_y() + 0.1
        
        # Item details
        pdf.set_xy(content_x, current_y)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
        details_text = f"Item: {item_id}"
        if gtin:
            details_text += f" | GTIN: {gtin}"
        pdf.multi_cell(6.5, 0.15, details_text, align='C')
        current_y = pdf.get_y() + 0.05
        
        # Casepack card
        if casepack_type:
            pdf.set_xy(content_x, current_y)
            if "CASEPACK" in casepack_type.upper():
                pdf.set_fill_color(224, 242, 254)
                pdf.set_text_color(0, 83, 226)
                pdf.set_draw_color(0, 83, 226)
            else:
                pdf.set_fill_color(252, 231, 243)
                pdf.set_text_color(236, 72, 153)
                pdf.set_draw_color(236, 72, 153)
            
            pdf.set_line_width(0.02)
            pdf.rect(content_x, current_y, 6.5, 0.4, 'FD')
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_xy(content_x + 0.1, current_y + 0.08)
            pdf.cell(6.3, 0.25, casepack_type, align='C')
            current_y += 0.45
        
        # ACL Performance card (simplified for batch view)
        # Just show that we have the data, not the full chart
        pdf.set_xy(content_x, current_y)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(6.5, 0.25, "ACL Performance %", align='C')
        current_y += 0.3
        
        # Load ACL data for this item
        try:
            rates = load_read_rates()
            rate_data = rates.get(str(item_id_orig), [])
            if rate_data and len(rate_data) > 0:
                avg_perf = get_avg_performance(rate_data)
                trend_status = get_trend_status(rate_data)
                recommendation, rec_color_hex, _ = get_recommendation(avg_perf, trend_status)
                
                # Show ACL recommendation card
                pdf.set_xy(content_x, current_y)
                
                # Map color
                color_map = {
                    "#16a34a": (34, 197, 94),
                    "#eab308": (245, 158, 11),
                    "#dc2626": (220, 38, 38),
                    "#6b7280": (107, 114, 128)
                }
                rgb = color_map.get(rec_color_hex, (100, 100, 100))
                
                pdf.set_fill_color(*rgb)
                pdf.set_text_color(*rgb)
                pdf.set_draw_color(*rgb)
                pdf.set_line_width(0.02)
                pdf.rect(content_x, current_y, 6.5, 0.35, 'FD')
                
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_xy(content_x + 0.1, current_y + 0.05)
                pdf.cell(6.3, 0.25, recommendation, align='C')
        except Exception as e:
            print(f"[BATCH-PDF] ACL data failed for item {page_idx + 1}: {str(e)}")
        
        print(f"[BATCH-PDF] Added page {page_idx + 1} for item {item_id}")
    
    # If we're building a multi-page PDF, DON'T output yet - just return the object
    # The final output() will be called on the master_pdf after all items are added
    if return_pdf_object or master_pdf:
        return pdf  # Return the FPDF object without calling output()
    else:
        # Single-item PDF - output and return bytes
        pdf_bytes = pdf.output()
        return bytes(pdf_bytes) if isinstance(pdf_bytes, bytearray) else pdf_bytes


@app.get("/batch/pdf")
async def batch_pdf(items: str = ""):
    """[ARCHIVED] Download consolidated PDF with multiple items (one page per item)."""
    # Parse item IDs from query param
    if not items:
        return JSONResponse({"error": "No items specified. Use ?items=id1,id2,id3"}, status_code=400)
    
    item_ids = [id.strip() for id in items.split(",") if id.strip()]
    if not item_ids:
        return JSONResponse({"error": "Invalid item IDs"}, status_code=400)
    
    try:
        api_key = os.getenv("MDM_API_KEY", "")
        facility_num = os.getenv("MDM_FACILITY_NUM", "6068")
        facility_country = os.getenv("MDM_FACILITY_COUNTRY_CODE", "US")
        wmt_userid = os.getenv("MDM_WMT_USERID", "mdm-ui")
        
        # Fetch all items' data
        items_data = []
        
        for item_id in item_ids:
            try:
                # Fetch MDM data
                api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{item_id}/?xrefItemInfo=false"
                headers = {
                    "Api-Key": api_key,
                    "Facilitynum": facility_num,
                    "Facilitycountrycode": facility_country,
                    "Wmt-Userid": wmt_userid
                }
                
                async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                    response = await client.get(api_url, headers=headers)
                    response.raise_for_status()
                    mdm_data = response.json()
                    item_data = extract_item_data(mdm_data)
                    
                    # IMPORTANT: Also load the full MDM data so generate_pdf() can access it
                    # generate_pdf() uses this to get charts and ACL cards
                    item_data["_mdm_data"] = mdm_data
                    
                    items_data.append(item_data)
                    print(f"[BATCH-PDF] Fetched item: {item_id}")
            
            except Exception as e:
                print(f"[BATCH-PDF] Error fetching item {item_id}: {str(e)}")
        
        if not items_data:
            return JSONResponse({"error": "Failed to fetch any items"}, status_code=500)
        
        # Generate single PDF with all items
        pdf_output = generate_batch_pdf(items_data)
        
        # Convert bytearray to bytes
        pdf_bytes = bytes(pdf_output) if isinstance(pdf_output, bytearray) else pdf_output
        
        print(f"[BATCH-PDF] Successfully generated PDF with {len(items_data)} items")
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="batch_report_all.pdf"'}
        )
    
    except Exception as e:
        print(f"[BATCH-PDF] Fatal error: {str(e)}")
        return JSONResponse({"error": f"PDF generation failed: {str(e)}"}, status_code=500)
    
# ============================================================
# ACL FREIGHT AWARENESS REDESIGN - Instant Load from Background Worker
# ============================================================

@app.get("/")
async def root():
    """Redirect home to ACL1"""
    return RedirectResponse(url="/acl1")


@app.get("/{acl}", response_class=HTMLResponse)
async def acl_page(acl: str):
    """ACL Freight Awareness - Grid layout with instant loads from background cache"""
    
    if acl not in ["acl1", "acl2", "acl3"]:
        raise HTTPException(status_code=404, detail="ACL must be acl1, acl2, or acl3")
    
    def tab_class(tab_acl):
        if tab_acl == acl:
            return "px-6 py-3 bg-blue-600 text-white font-bold rounded-t border-b-4 border-blue-800"
        return "px-6 py-3 bg-gray-200 text-gray-700 font-semibold rounded-t hover:bg-gray-300 cursor-pointer"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACL Freight Awareness - {acl.upper()}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        /* Edge-to-edge grid layout */
        .delivery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }}
        
        @media (min-width: 1024px) {{
            .delivery-grid {{
                grid-template-columns: repeat(4, 1fr);
            }}
        }}
        
        @media (min-width: 768px) and (max-width: 1023px) {{
            .delivery-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <main class="container mx-auto p-4">
        <!-- Header -->
        <div class="bg-white rounded-lg shadow-md p-6 mb-4">
            <h1 class="text-3xl font-bold text-blue-700 mb-2"> ACL Freight Awareness</h1>
            <p class="text-gray-600">Real-time monitoring • Background analysis every 2 minutes • Instant page loads</p>
        </div>

        <!-- ACL Tabs -->
        <div class="flex gap-2 mb-4">
            <a href="/acl1" class="{tab_class('acl1')}">ACL 1</a>
            <a href="/acl2" class="{tab_class('acl2')}">ACL 2</a>
            <a href="/acl3" class="{tab_class('acl3')}">ACL 3</a>
        </div>

        <!-- Delivery Grid - Auto-refresh every 60s -->
        <div 
            id="delivery-grid" 
            class="delivery-grid"
            hx-get="/api/acl-rendered/{acl}"
            hx-trigger="load, every 60s"
            hx-swap="innerHTML"
        >
            <!-- Loading spinner -->
            <div class="col-span-full text-center py-12">
                <div class="animate-spin inline-block w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full"></div>
                <p class="mt-4 text-gray-600 font-semibold">Loading {acl.upper()} deliveries from cache...</p>
            </div>
        </div>

        <!-- Navigation -->
        <div class="mt-6 flex gap-4">
            <a href="/item-analysis" class="px-4 py-2 bg-gray-600 text-white rounded font-semibold hover:bg-gray-700">
                 Item Analysis
            </a>
            <a href="/delivery-analysis" class="px-4 py-2 bg-gray-600 text-white rounded font-semibold hover:bg-gray-700">
                 Delivery Analysis
            </a>
        </div>
    </main>
</body>
</html>
"""


@app.get("/api/acl-rendered/{acl}", response_class=HTMLResponse)
async def get_acl_rendered(acl: str):
    """Return pre-analyzed HTML from background worker cache - INSTANT load!"""
    try:
        # Get cached data from background worker
        cached_data = acl_monitor.get_acl_data(acl)
        
        print(f"[ACL-ENDPOINT-DEBUG] {acl}: Received cached_data: {cached_data is not None}")
        
        if not cached_data:
            print(f"[ACL-ENDPOINT-DEBUG] {acl}: No cached_data! Returning initialization message")
            return f"""
            <div class="col-span-full bg-yellow-50 border-2 border-yellow-400 rounded-lg p-6 text-center">
                <p class="text-yellow-800 font-bold text-lg">No cached data available for {acl.upper()}</p>
                <p class="text-yellow-700 mt-2">Background worker may still be initializing. Please wait 2 minutes.</p>
                <p class="text-xs text-gray-600 mt-2">Status: {cached_data.get('status') if cached_data else 'null'}</p>
            </div>
            """
        
        deliveries = cached_data.get('deliveries', [])
        last_updated = cached_data.get('last_update', 'Unknown')
        status = cached_data.get('status', 'unknown')
        
        print(f"[ACL-ENDPOINT-DEBUG] {acl}: Found {len(deliveries)} deliveries, status={status}, last_update={last_updated}")
        
        if not deliveries:
            print(f"[ACL-ENDPOINT-DEBUG] {acl}: No deliveries in list! Status={status}")
            return f"""
            <div class="col-span-full bg-green-50 border-2 border-green-400 rounded-lg p-6 text-center">
                <p class="text-green-800 font-bold text-lg">No active deliveries in {acl.upper()}</p>
                <p class="text-green-700 mt-2">All clear! Updated: {last_updated}</p>
                <p class="text-xs text-gray-600 mt-2">Status: {status}</p>
            </div>
            """
        
        # Build delivery cards
        cards_html = []
        for delivery in deliveries:
            delivery_num = delivery.get('delivery_number', 'Unknown')
            station = delivery.get('station', 'Unknown')
            
            # Access nested analysis data
            analysis = delivery.get('analysis', {})
            problematic_count = analysis.get('problematic_count', 0)
            problematic_items = analysis.get('problematic_items', [])[:10]  # Top 10
            
            # Color coding based on issue count
            if problematic_count == 0:
                border_color = "border-green-500"
                header_color = "bg-gradient-to-r from-green-600 to-green-700"
                badge_color = "bg-green-100 text-green-800"
                status_emoji = ""
            elif problematic_count < 5:
                border_color = "border-yellow-500"
                header_color = "bg-gradient-to-r from-yellow-600 to-yellow-700"
                badge_color = "bg-yellow-100 text-yellow-800"
                status_emoji = ""
            else:
                border_color = "border-red-500"
                header_color = "bg-gradient-to-r from-red-600 to-red-700"
                badge_color = "bg-red-100 text-red-800"
                status_emoji = ""
            
            # Build item list HTML
            items_html = []
            if problematic_items:
                for item in problematic_items:
                    perf = item.get('performance', 0)
                    if perf < 50:
                        perf_badge = f"<span class='bg-red-200 text-red-900 px-2 py-1 rounded text-xs font-bold'>{perf:.1f}%</span>"
                    elif perf < 70:
                        perf_badge = f"<span class='bg-orange-200 text-orange-900 px-2 py-1 rounded text-xs font-bold'>{perf:.1f}%</span>"
                    else:
                        perf_badge = f"<span class='bg-yellow-200 text-yellow-900 px-2 py-1 rounded text-xs font-bold'>{perf:.1f}%</span>"
                    
                    items_html.append(f"""
                    <div class="flex justify-between items-center py-2 border-b border-gray-200 last:border-0">
                        <div class="flex-1">
                            <a href="/item-analysis?item_id={item.get('mds_fam_id', '')}" 
                               target="_blank"
                               class="text-blue-600 hover:text-blue-800 font-mono text-sm font-semibold underline">
                                {item.get('mds_fam_id', 'N/A')}
                            </a>
                            <p class="text-xs text-gray-500">Qty: {item.get('qty', 0)} • Dept: {item.get('dept', 'N/A')}</p>
                        </div>
                        <div>
                            {perf_badge}
                        </div>
                    </div>
                    """)
            else:
                items_html.append("""
                <div class="text-center py-4 text-green-700 font-semibold">
                     All items performing well!
                </div>
                """)
            
            card = f"""
            <div class="border-2 {border_color} rounded-lg overflow-hidden shadow-lg hover:shadow-xl transition-shadow">
                <!-- Header -->
                <div class="{header_color} p-4 text-white">
                    <div class="flex items-center justify-between">
                        <div>
                            <h3 class="text-xl font-bold">{status_emoji} Delivery #{delivery_num}</h3>
                            <p class="text-sm opacity-90">{station}</p>
                        </div>
                        <div class="{badge_color} px-3 py-1 rounded-full font-bold text-sm">
                            {problematic_count} issues
                        </div>
                    </div>
                </div>
                
                <!-- Problematic Items -->
                <div class="p-4 bg-white">
                    <h4 class="font-bold text-gray-700 mb-3 text-sm uppercase tracking-wide">
                        Top Problematic Items (Performance &lt; 90%)
                    </h4>
                    <div class="space-y-1">
                        {''.join(items_html)}
                    </div>
                    
                    {f'<p class="text-xs text-gray-500 mt-3 text-center">+ {problematic_count - 10} more items</p>' if problematic_count > 10 else ''}
                </div>
                
                <!-- Footer -->
                <div class="bg-gray-50 px-4 py-2 border-t border-gray-200">
                    <a href="/delivery-analysis?delivery={delivery_num}" 
                       target="_blank"
                       class="text-blue-600 hover:text-blue-800 text-sm font-semibold">
                         Full Analysis →
                    </a>
                </div>
            </div>
            """
            cards_html.append(card)
        
        # Add last updated footer
        footer = f"""
        <div class="col-span-full bg-blue-50 border border-blue-300 rounded p-3 text-center">
            <p class="text-blue-800 text-sm font-semibold">
                 Last updated: {last_updated} • Auto-refreshes every 60 seconds
            </p>
        </div>
        """
        
        return '\n'.join(cards_html) + footer
    
    except Exception as e:
        import traceback
        return f"""
        <div class="col-span-full bg-red-50 border-2 border-red-400 rounded-lg p-6">
            <p class="text-red-800 font-bold text-lg"> Error loading {acl.upper()} data</p>
            <p class="text-red-700 mt-2">{str(e)}</p>
            <pre class="text-xs text-gray-600 mt-3 overflow-auto bg-white p-3 rounded">{traceback.format_exc()}</pre>
        </div>
        """

# ============================================================================
# DELIVERY ANALYSIS ENDPOINTS - Query Informix + apply batching to mds_fam_ids
# ============================================================================

@app.get("/delivery-analysis", response_class=HTMLResponse)
async def delivery_analysis_page():
    """Delivery Analysis search page - user inputs delivery number."""
    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Delivery Analysis</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org"></script>
    <style>
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        @keyframes pulse-glow {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .spinner {{
            animation: spin 0.8s linear infinite;
        }}
        .pulse {{
            animation: pulse-glow 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }}
        #loading.htmx-request {{
            display: flex !important;
        }}
        #loading:not(.htmx-request) {{
            display: none !important;
        }}
    </style>
</head>
<body class="bg-gray-50">
    <div class="w-full p-6" style="max-width: none;">
        <h1 class="text-4xl font-bold text-blue-600 mb-2">Delivery Analysis</h1>
        <p class="text-gray-700 mb-6">Enter a delivery number to analyze purchase order data, batching, and item performance.</p>
        
        <div class="bg-white p-6 rounded-lg shadow-lg border-2 border-blue-200" style="max-width: 600px;">
            <form hx-get="/api/delivery-analysis/search" hx-target="#results" hx-indicator="#loading" class="space-y-4">
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">Delivery Number</label>
                    <input 
                        type="text" 
                        name="delivery_number" 
                        placeholder="e.g., 10691042" 
                        class="w-full px-4 py-3 border border-gray-300 rounded font-mono text-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        required
                    >
                    <p class="text-xs text-gray-500 mt-1">Corresponds to rcv.appointment_nbr in the Informix query</p>
                </div>
                
                <button type="submit" class="w-full bg-blue-600 text-white font-semibold py-3 rounded hover:bg-blue-700 transition flex items-center justify-center">
                    <span>Search</span>
                </button>
            </form>
        </div>
        
        <!-- Loading Indicator with Progress -->
        <div id="loading" class="flex-col items-center justify-center mt-12 space-y-8">
            <div class="space-y-4 w-full max-w-2xl">
                <!-- Spinner Header -->
                <div class="flex items-center justify-center space-x-3">
                    <svg class="spinner h-10 w-10 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <div>
                        <div class="text-xl font-bold text-gray-800">Analyzing Delivery...</div>
                        <div class="text-sm text-gray-600">This may take 10-45 seconds depending on data volume</div>
                    </div>
                </div>
                
                <!-- Progress Bar -->
                <div class="bg-gray-200 rounded-full h-3 overflow-hidden">
                    <div id="progressBar" class="bg-blue-600 h-full" style="width: 0%; transition: width 0.3s ease;"></div>
                </div>
                <div class="text-center text-sm text-gray-600">
                    <span id="progressPercent">Starting...</span>
                </div>
                
                <!-- Current Status -->
                <div id="currentStatus" class="bg-blue-50 border-l-4 border-blue-600 p-4 rounded">
                    <div class="text-sm text-blue-800 font-mono">
                        [QUERY] Connecting to Informix...
                    </div>
                </div>
                
                <!-- Steps Progress -->
                <div class="space-y-2">
                    <div id="step1" class="pulse bg-blue-100 border border-blue-300 rounded p-3 text-sm text-blue-700 font-mono">
                        ✓ [QUERY] Connected to Informix
                    </div>
                    <div id="step2" class="bg-gray-100 border border-gray-300 rounded p-3 text-sm text-gray-700 font-mono opacity-50">
                        [BATCH] Loading read rate data...
                    </div>
                    <div id="step3" class="bg-gray-100 border border-gray-300 rounded p-3 text-sm text-gray-700 font-mono opacity-50">
                        [ANALYZE] Analyzing ACL status...
                    </div>
                    <div id="step4" class="bg-gray-100 border border-gray-300 rounded p-3 text-sm text-gray-700 font-mono opacity-50">
                        [BUILD] Building HTML response...
                    </div>
                </div>
                
                <!-- Tips -->
                <div class="bg-yellow-50 border border-yellow-200 rounded p-3 text-xs text-yellow-700">
                    <strong>Tip:</strong> Open browser console (F12) to see detailed progress logs in real-time
                </div>
            </div>
        </div>
        
        <script>
        // Simulate progress based on time elapsed
        let startTime = null;
        let progressInterval = null;
        
        document.addEventListener('htmx:xhr:beforeSend', function(evt) {{
            startTime = Date.now();
            progressInterval = setInterval(function() {{
                let elapsed = (Date.now() - startTime) / 1000;
                let percent = Math.min(80, Math.floor((elapsed / 35) * 100));
                
                document.getElementById('progressBar').style.width = percent + '%';
                
                if (percent < 20) {{
                    document.getElementById('progressPercent').textContent = 'Querying Informix... (' + percent + '%)';
                }} else if (percent < 50) {{
                    document.getElementById('progressPercent').textContent = 'Loading batching data... (' + percent + '%)';
                }} else {{
                    document.getElementById('progressPercent').textContent = 'Analyzing and building report... (' + percent + '%)';
                }}
            }}, 200);
        }});
        
        document.addEventListener('htmx:afterRequest', function(evt) {{
            if (progressInterval) clearInterval(progressInterval);
            if (evt.detail.xhr.status === 200) {{
                document.getElementById('progressBar').style.width = '100%';
                document.getElementById('progressPercent').textContent = 'Complete! (100%)';
            }}
        }});
        </script>
        
        <div id="results" class="mt-8"></div>
        
        <div class="mt-6">
            <a href="/" class="inline-block px-6 py-2 bg-gray-600 text-white rounded font-semibold hover:bg-gray-700">Back to Home</a>
        </div>
    </div>
</body>
</html>'''


@app.get("/api/delivery-analysis/search", response_class=HTMLResponse)
async def delivery_analysis_search(delivery_number: str):
    """Search for delivery data and apply batching to all mds_fam_ids."""
    from delivery_analysis import get_delivery_po_data, apply_batching_to_delivery
    import time
    
    overall_start = time.time()
    
    try:
        # Check if full HTML page is cached (skip all analysis if so)
        cache = get_cache_manager()
        cache_key = f"html_{delivery_number}"
        print(f"[SEARCH-CACHE] Checking for key: {cache_key}")
        cached_html = cache.get(cache_key, category="deliveries")
        if cached_html:
            print(f"[SEARCH-CACHE-HIT] Returning cached HTML for {delivery_number} ({len(cached_html)} bytes)")
            return cached_html
        else:
            print(f"[SEARCH-CACHE-MISS] No HTML cache for {delivery_number} - running analysis")
        
        # Step 1: Query Informix
        delivery_data = get_delivery_po_data(delivery_number)
        progress = delivery_data.get("progress")
        
        if not delivery_data["success"]:
            progress.log("ERROR", "Query failed, returning error")
            progress_logs = progress.get_logs()
            return f'''<div class="bg-red-50 border-l-4 border-red-600 p-4 rounded text-red-700">
                <strong>Error:</strong> {delivery_data["error"]}
            </div>
            <details class="bg-gray-50 border border-gray-300 p-4 rounded mt-4">
                <summary class="cursor-pointer font-semibold text-gray-700">Progress Logs</summary>
                <pre class="text-xs mt-3 bg-black text-green-400 p-3 rounded overflow-x-auto">{progress_logs}</pre>
            </details>
            <script>
                console.group("Delivery Analysis - Error");
                console.log({json.dumps(progress_logs)});
                console.groupEnd();
            </script>'''
        
        # Step 2: Apply batching to all mds_fam_ids
        delivery_data = apply_batching_to_delivery(delivery_data)
        progress = delivery_data.get("progress")
        
        # Step 3: Build HTML response
        po_rows = delivery_data.get("data", [])
        record_count = delivery_data.get("record_count", 0)
        mds_fam_ids = delivery_data.get("mds_fam_ids", [])
        batching_data = delivery_data.get("batching_data", {})
        
        if record_count == 0:
            progress.log("RESULT", "No PO lines found for this delivery")
            progress_logs = progress.get_logs()
            return f'''<div class="bg-yellow-50 border-l-4 border-yellow-600 p-4 rounded text-yellow-700">
                <strong>No Results:</strong> Delivery {delivery_number} returned no PO lines.
            </div>
            <details class="bg-gray-50 border border-gray-300 p-4 rounded mt-4">
                <summary class="cursor-pointer font-semibold text-gray-700">Progress Logs</summary>
                <pre class="text-xs mt-3 bg-black text-green-400 p-3 rounded overflow-x-auto">{progress_logs}</pre>
            </details>'''
        
        progress.log("HTML", f"Building HTML response for {record_count} rows")
        
        # Initialize problematic_items_data (will be populated later)
        problematic_items_data = []
        
        # Load read rates ONLY for items in THIS delivery (SQL filtering - FAST!)
        read_rates_cache = load_read_rates_for_items(mds_fam_ids)
        
        # Calculate delivery case summary using adjusted quantities
        # adjusted quantities account for split POs
        total_po_qty = sum([int(row.get('whpk_adjusted_qty', row.get('whpk_order_qty', 0))) 
                           if isinstance(row.get('whpk_adjusted_qty', row.get('whpk_order_qty')), (int, str)) 
                           else 0 for row in po_rows])
        
        # Get trailer info
        trailer = po_rows[0].get('trailer', 'Unknown') if po_rows else 'Unknown'
        
        # Calculate performance metrics
        total_perf = 0
        items_with_data = 0
        items_without_data = 0
        
        for mds_id in mds_fam_ids:
            rate_data = read_rates_cache.get(str(mds_id), [])
            if rate_data:
                avg_perf = get_avg_performance(rate_data)
                total_perf += avg_perf
                items_with_data += 1
            else:
                items_without_data += 1
        
        avg_read_rate = (total_perf / items_with_data) if items_with_data > 0 else 0
        no_history = items_without_data
        
        # Proportionally adjust estimates based on no-history ratio
        no_history_ratio = no_history / len(mds_fam_ids) if mds_fam_ids else 0
        data_ratio = 1 - no_history_ratio
        
        estimated_good = int(total_po_qty * (avg_read_rate / 100) * data_ratio)
        estimated_bad = int(total_po_qty * ((100 - avg_read_rate) / 100) * data_ratio)
        no_history_qty = int(total_po_qty * no_history_ratio)
        
        # Build summary section with timing
        overall_elapsed = time.time() - overall_start
        split_po_notice = f"<div class='bg-purple-50 border-l-4 border-purple-600 p-4 rounded-lg mb-6'><strong class='text-purple-700'>Note: Split POs & Pure Loads</strong><p class='text-sm text-purple-600 mt-1'>Quantities based on freight_bill_qty ({total_po_qty:,} cases) for trailer {trailer}. Projected cases proportionally adjusted.</p></div>"
        summary_html = split_po_notice + f'''<div class="bg-blue-50 border-l-4 border-blue-600 p-6 rounded-lg mb-6">
            <h2 class="text-2xl font-bold text-blue-700 mb-4">Delivery Summary</h2>
            <div class="grid grid-cols-2 md:grid-cols-6 gap-3 text-center">
                <div class="bg-white p-3 rounded border border-blue-200"><div class="text-2xl font-bold text-blue-600">{record_count}</div><div class="text-xs text-gray-600 mt-1">PO Lines</div></div>
                <div class="bg-white p-3 rounded border border-blue-200"><div class="text-2xl font-bold text-blue-600">{len(mds_fam_ids)}</div><div class="text-xs text-gray-600 mt-1">Items</div></div>
                <div class="bg-white p-3 rounded border border-orange-300"><div class="text-2xl font-bold text-orange-600">{no_history_qty:,}</div><div class="text-xs text-gray-600 mt-1">No History Cases</div></div>
                <div class="bg-white p-3 rounded border border-green-300"><div class="text-2xl font-bold text-green-600">{estimated_good:,}</div><div class="text-xs text-gray-600 mt-1">Est. Good</div></div>
                <div class="bg-white p-3 rounded border border-red-300"><div class="text-2xl font-bold text-red-600">{estimated_bad:,}</div><div class="text-xs text-gray-600 mt-1">Est. Bad</div></div>
                <div class="bg-white p-3 rounded border border-purple-300"><div class="text-2xl font-bold text-purple-600">{avg_read_rate:.0f}%</div><div class="text-xs text-gray-600 mt-1">Avg Rate</div></div>
            </div>
        </div>'''
        
        # Build lookup dict from problematic items data for MDM info
        mdm_data_lookup = {}
        for item in problematic_items_data:
            mds_id = item.get("mds_fam_id", "")
            mdm_data_lookup[str(mds_id)] = item
        
        # Build detailed table with MDM columns (optimized with list)
        table_rows_list = []
        for idx, row in enumerate(po_rows, 1):
            mds_fam_id = str(row.get("mds_fam_id", ""))
            batching_info = row.get("batching_info", {})
            batch_record_count = batching_info.get("record_count", 0)
            
            # Get MDM data if available
            mdm_item = mdm_data_lookup.get(mds_fam_id, {})
            item_name = mdm_item.get("item_name", "—")
            gtin = mdm_item.get("gtin", "—")
            if isinstance(gtin, str) and len(gtin) > 15:
                gtin = gtin[:12] + "..."
            
            # Build dimensions from MDM
            dims = [str(mdm_item.get(k, "")) for k in ["vnpk_length", "vnpk_width", "vnpk_height"]]
            dimensions = "x".join(d for d in dims if d) if any(dims) else "—"
            casepack = mdm_item.get("casepack_type", "—")
            
            bg_class = "bg-gray-50" if idx % 2 else "bg-white"
            
            table_rows_list.append(f'<tr class="{bg_class} border-b hover:bg-blue-50 transition"><td class="px-4 py-3 text-sm font-mono text-gray-600">{idx}</td><td class="px-4 py-3 text-sm font-bold text-blue-600">{mds_fam_id}</td><td class="px-4 py-3 text-sm text-gray-700">{item_name}</td><td class="px-4 py-3 text-sm text-gray-700 font-mono text-xs">{gtin}</td><td class="px-4 py-3 text-sm text-gray-700">{dimensions}</td><td class="px-4 py-3 text-sm text-gray-700">{casepack}</td><td class="px-4 py-3 text-sm">{row.get("po_nbr", "—")}</td><td class="px-4 py-3 text-sm">{row.get("po_line_nbr", "—")}</td><td class="px-4 py-3 text-sm text-center"><span class="inline-block px-3 py-1 bg-green-100 text-green-800 rounded text-xs font-semibold">{batch_record_count}</span></td><td class="px-4 py-3 text-sm">{row.get("vendor_stock_id", "—")}</td><td class="px-4 py-3 text-sm text-right text-gray-700">{row.get("whpk_adjusted_qty", row.get("whpk_order_qty", "—"))}</td><td class="px-4 py-3 text-sm text-right text-gray-700">{row.get("whpk_max_rcv_qty", "—")}</td></tr>')
        
        table_rows = "".join(table_rows_list)
        
        table_html = f'''<div class="bg-white rounded-lg shadow-lg overflow-hidden mb-6">
            <div class="bg-gray-100 px-6 py-4 border-b border-gray-200">
                <h3 class="text-xl font-bold text-gray-800">Purchase Order Lines ({record_count})</h3>
                <p class="text-xs text-gray-600 mt-1">All rows for delivery {delivery_number} with batching data applied</p>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="bg-gray-200 text-gray-800 font-semibold">
                            <th class="px-4 py-3 text-left">#</th>
                            <th class="px-4 py-3 text-left">MDS_FAM_ID</th>
                            <th class="px-4 py-3 text-left">Item Name</th>
                            <th class="px-4 py-3 text-left">GTIN</th>
                            <th class="px-4 py-3 text-left">Dimensions</th>
                            <th class="px-4 py-3 text-left">Pack Type</th>
                            <th class="px-4 py-3 text-left">PO #</th>
                            <th class="px-4 py-3 text-left">Line #</th>
                            <th class="px-4 py-3 text-center">Read Rate Recs</th>
                            <th class="px-4 py-3 text-left">Vendor Stock ID</th>
                            <th class="px-4 py-3 text-right">Order Qty</th>
                            <th class="px-4 py-3 text-right">Max Rcv Qty</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </div>'''

        
        # Get progress logs
        progress_logs = progress.get_logs()
        
        # ACL Directive Actions Ruleset
        ruleset_html = '''<details class="bg-blue-50 border-l-4 border-blue-600 p-4 mb-6 rounded cursor-pointer">
            <summary class="font-bold text-blue-700 select-none">ACL Directive Actions Ruleset (Click to expand)</summary>
            <div class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <div class="bg-green-50 border border-green-300 p-3 rounded">
                    <div class="font-bold text-green-700">ACL APPROVED</div>
                    <div class="text-green-600">Performance >= 85%</div>
                    <div class="text-xs text-gray-600 mt-1">No action needed</div>
                </div>
                <div class="bg-yellow-50 border border-yellow-300 p-3 rounded">
                    <div class="font-bold text-yellow-700">ADEQUATE PERFORMANCE</div>
                    <div class="text-yellow-600">Performance < 85% & Improving</div>
                    <div class="text-xs text-gray-600 mt-1">Monitor closely</div>
                </div>
                <div class="bg-yellow-50 border border-yellow-300 p-3 rounded">
                    <div class="font-bold text-yellow-700">REQUIRES MANUAL INSPECTION</div>
                    <div class="text-yellow-600">Fluctuating or Declining</div>
                    <div class="text-xs text-gray-600 mt-1">Review data quality</div>
                </div>
                <div class="bg-red-50 border border-red-300 p-3 rounded">
                    <div class="font-bold text-red-700">FAILING</div>
                    <div class="text-red-600">Performance < 50% & Declining</div>
                    <div class="text-xs text-gray-600 mt-1">Immediate action required</div>
                </div>
            </div>
        </details>'''
        
        # Build read rate cards for ONLY problematic items
        # CHECK CACHE FIRST - avoid re-analyzing every time!
        analysis_cache_key = f"analysis_{delivery_number}"
        cached_analysis = cache.get(analysis_cache_key, category="deliveries")
        
        if cached_analysis:
            print(f"[ANALYSIS-CACHE-HIT] Using cached analysis for delivery {delivery_number}")
            progress.log("ANALYZE", "Using cached problematic items analysis")
            problematic_mds_ids = cached_analysis.get('problematic_mds_ids', [])
            problematic_details = cached_analysis.get('problematic_details', {})
            problematic_items_data = cached_analysis.get('problematic_items_data', [])
            approved_count = cached_analysis.get('approved_count', 0)
        else:
            print(f"[ANALYSIS-CACHE-MISS] Running full problematic items analysis")
            # Step 1: First pass - identify problematic items (ONLY if they have history)
            problematic_mds_ids = []
        problematic_details = {}  # Store ACL details
        approved_count = 0
        no_history_count = 0
        no_history_qty = 0
        total_items = len(mds_fam_ids)
        items_with_history = set()
        
        # BUILD LOOKUP DICT ONCE (O(n) instead of O(n²) nested loop)
        po_rows_by_mds_id = {}
        for row in po_rows:
            mds_id = str(row.get('mds_fam_id', ''))
            if mds_id not in po_rows_by_mds_id:
                po_rows_by_mds_id[mds_id] = []
            po_rows_by_mds_id[mds_id].append(row)
        
        progress.log("ANALYZE", f"Analyzing {total_items} items for ACL status")
        
        for idx, mds_id in enumerate(sorted(mds_fam_ids), 1):
            if idx % 5 == 0 or idx == total_items:
                progress.log("ANALYZE", f"Processed {idx}/{total_items} items")
            
            rate_data = read_rates_cache.get(str(mds_id), [])
            
            # SKIP items with NO history - don't mark as problematic
            if not rate_data:
                no_history_count += 1
                # Sum quantities for items with no history using lookup dict (FAST!)
                for row in po_rows_by_mds_id.get(str(mds_id), []):
                    qty = row.get('whpk_order_qty', 0)
                    if qty:
                        try:
                            no_history_qty += int(qty) if isinstance(qty, str) else qty
                        except:
                            pass
                continue
            
            # Item HAS history - process it
            items_with_history.add(str(mds_id))
            avg_perf = get_avg_performance(rate_data)
            trend = get_trend_status(rate_data)
            recommendation, color_hex, gradient_class = get_recommendation(avg_perf, trend)
            
            # Determine ACL status (only for items WITH history)
            if avg_perf >= 85:
                acl_status_name = "ACL APPROVED"
                is_problematic = False
            elif avg_perf < 50:
                acl_status_name = "FAILING"
                is_problematic = True
            elif "Improving" in trend:
                acl_status_name = "ADEQUATE PERFORMANCE"
                is_problematic = True
            else:
                acl_status_name = "REQUIRES MANUAL INSPECTION"
                is_problematic = True
            
            if is_problematic:
                problematic_mds_ids.append(mds_id)
                problematic_details[str(mds_id)] = {
                    "avg_perf": avg_perf,
                    "trend": trend,
                    "acl_status": acl_status_name,
                    "recommendation": recommendation,
                    "color_hex": color_hex,
                    "gradient_class": gradient_class,
                    "rate_data": rate_data
                }
            else:
                approved_count += 1
        
        progress.log("ANALYZE", f"Analysis complete: {len(problematic_mds_ids)} problematic, {approved_count} approved")
        
        # Step 2: Fetch MDM data for problematic items (BATCH PATTERN)
        problematic_items_data = []
        if problematic_mds_ids:
            progress.log("MDM", f"Fetching MDM data for {len(problematic_mds_ids)} problematic items")
            
            api_key = os.getenv("MDM_API_KEY", "")
            facility_num = os.getenv("MDM_FACILITY_NUM", "6068")
            facility_country = os.getenv("MDM_FACILITY_COUNTRY_CODE", "US")
            wmt_userid = os.getenv("MDM_WMT_USERID", "mdm-ui")
            
            mdm_headers = {
                "Api-Key": api_key,
                "Facilitynum": facility_num,
                "Facilitycountrycode": facility_country,
                "Wmt-Userid": wmt_userid
            }
            
            # Use cache for MDM results (2-day TTL)
            cache = get_cache_manager()
            
            # Use synchronous HTTP client (no asyncio issues)
            with httpx.Client(verify=False, timeout=30.0) as client:
                for mds_id in problematic_mds_ids:
                    # Check cache first
                    cached_mdm = cache.get(f"mdm_{mds_id}", category="items")
                    if cached_mdm:
                        cached_mdm["acl_details"] = problematic_details.get(str(mds_id), {})
                        problematic_items_data.append(cached_mdm)
                        progress.log("MDM", f"Cache hit for MDS {mds_id}")
                        continue
                    try:
                        api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{mds_id}/?xrefItemInfo=false"
                        response = client.get(api_url, headers=mdm_headers)
                        response.raise_for_status()
                        mdm_data = response.json()
                        
                        item_data = extract_item_data(mdm_data)
                        item_data["mds_fam_id"] = str(mds_id)
                        item_data["acl_details"] = problematic_details.get(str(mds_id), {})
                        problematic_items_data.append(item_data)
                        
                        # Cache MDM data (without acl_details which is delivery-specific)
                        mdm_cache_data = {k: v for k, v in item_data.items() if k != "acl_details"}
                        cache.set(f"mdm_{mds_id}", mdm_cache_data, category="items")
                        
                        progress.log("MDM", f"Fetched MDM data for MDS {mds_id}")
                    except Exception as e:
                        progress.log("MDM", f"Error fetching MDS {mds_id}: {str(e)}")
                        problematic_items_data.append({
                            "mds_fam_id": str(mds_id),
                            "item_name": f"MDS {mds_id}",
                            "image_url": "",
                            "error": str(e),
                            "acl_details": problematic_details.get(str(mds_id), {})
                        })
            
            # Cache the analysis results
            analysis_cache_data = {
                'problematic_mds_ids': problematic_mds_ids,
                'problematic_details': problematic_details,
                'problematic_items_data': problematic_items_data,
                'approved_count': approved_count
            }
            cache.set(analysis_cache_key, analysis_cache_data, category="deliveries")
            print(f"[ANALYSIS-CACHE-WRITE] Cached analysis for {delivery_number} ({len(problematic_items_data)} problematic)")
        
        # Cache the analysis result (problematic_items_data + metadata) for PDF endpoint
        # This lets PDF generation skip re-analyzing if called shortly after web search
        analysis_cache = {
            "mds_fam_ids": mds_fam_ids,
            "po_rows": po_rows,
            "problematic_items_data": problematic_items_data,
            "problematic_details": problematic_details,
            "approved_count": approved_count,
            "no_history_count": no_history_count
        }
        try:
            cache.set(f"pdf_analysis_{delivery_number}", analysis_cache, category="deliveries")
            print(f"[ANALYSIS-CACHE-WRITE] Cached analysis for {delivery_number} ({len(problematic_items_data)} problematic items)")
        except Exception as e:
            print(f"[ANALYSIS-CACHE-WRITE-ERROR] Failed to cache analysis: {e}")
        
        # Step 3: Build cards HTML with images and details
        cards_html = ""
        for item_data in problematic_items_data:
            mds_id = item_data.get("mds_fam_id", "")
            acl_details = item_data.get("acl_details", {})
            color_hex = acl_details.get("color_hex", "#ef4444")
            acl_status_name = acl_details.get("acl_status", "UNKNOWN")
            recommendation = acl_details.get("recommendation", "")
            avg_perf = acl_details.get("avg_perf", 0)
            trend = acl_details.get("trend", "No Data")
            rate_data = acl_details.get("rate_data", [])
            
            image_url = item_data.get("image_url", "")
            item_name = item_data.get("item_name", "Unknown")
            gtin = item_data.get("gtin", "")
            vendor_dept = item_data.get("supplier_dept", "")
            vnpk_length = item_data.get("vnpk_length", "")
            vnpk_width = item_data.get("vnpk_width", "")
            vnpk_height = item_data.get("vnpk_height", "")
            casepack = item_data.get("casepack_type", "")
            
            # SKIP: chart_html = get_read_rate_chart(str(mds_id))  # Disabled - too slow for card display
            
            image_display = f'<img src="{image_url}" class="w-full h-40 object-cover rounded mb-2 border">'
            if not image_url:
                image_display = '<div class="w-full h-40 bg-gray-200 rounded mb-2 flex items-center justify-center"><p class="text-xs text-gray-500">No Image</p></div>'
            
            cards_html += f'''<div class="bg-white p-4 rounded-lg shadow border-l-4 h-full flex flex-col" style="border-color: {color_hex};">
                {image_display}
                <h4 class="font-bold text-sm text-blue-600 mb-2 line-clamp-2">{item_name}</h4>
                <div class="text-xs text-gray-600 space-y-0.5 mb-3 flex-grow">
                    <p><strong>MDS:</strong> {mds_id[:8]}</p>
                    <p><strong>Perf:</strong> <span style="color: {color_hex}; font-weight: bold;">{avg_perf:.0f}%</span></p>
                    <p><strong>Status:</strong> {acl_status_name[:15]}</p>
                    <p class="text-xs text-gray-500">{trend}</p>
                </div>
                <a href="/api/delivery-analysis/pdf-item?mds_id={mds_id}" class="block w-full px-2 py-1 bg-green-600 text-white rounded text-xs font-semibold hover:bg-green-700 text-center">PDF</a>
            </div>'''
        
        problematic_count = len(problematic_items_data)
        
        progress.log("ANALYZE", f"Analysis complete: {problematic_count} problematic, {approved_count} approved")
        
        if cards_html:
            cards_section = f'''{ruleset_html}
            <div class="mb-6">
                <h3 class="text-xl font-bold text-gray-800 mb-3">Performance Review - Problematic Items ({problematic_count})</h3>
                <p class="text-sm text-gray-600 mb-4">
                    {approved_count} items are ACL APPROVED (not shown)
                </p>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {cards_html}
                </div>
            </div>'''
        else:
            cards_section = f'''{ruleset_html}
            <div class="bg-green-50 border border-green-300 p-6 rounded-lg mb-6">
                <h3 class="text-xl font-bold text-green-700">All Items ACL Approved</h3>
                <p class="text-green-700">All {len(mds_fam_ids)} items have performance >= 85%. No action required.</p>
            </div>'''
        
        # Store problematic_items_data for PDF generation (reuse in batch PDF endpoint)
        progress.log("HTML", f"Prepared {len(problematic_items_data)} items for display and PDF")
        
        # Full JSON download button
        # Strip out the progress tracker from JSON (not serializable)
        json_export = dict(delivery_data)
        json_export.pop("progress", None)
        json_data_str = json.dumps(json_export, indent=2, default=str)
        
        # Escape for JavaScript embedding
        json_escaped = json_data_str.replace('"', r'"').replace('\n', ' ')
        
        top_buttons_html = f'''<div class="bg-white rounded-lg shadow-lg p-4 mb-6 border-b-4 border-blue-600">
            <div class="flex flex-wrap gap-3 items-center">
                <a href="/delivery-analysis" class="px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700 text-sm">New Search</a>
                <a href="/api/delivery-analysis/pdf?delivery_number={delivery_number}&include_approved=false" id="pdfButtonProblematic" class="px-4 py-2 bg-purple-600 text-white rounded font-semibold hover:bg-purple-700 text-sm">Batch PDF (Problematic Only)</a>
                <a href="#" id="pdfButtonAll" style="display:none;" class="px-4 py-2 bg-purple-700 text-white rounded font-semibold hover:bg-purple-800 text-sm">Batch PDF (All Items)</a>
                <button onclick="downloadJSON()" class="px-4 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700 text-sm">Download JSON</button>
                <label class="flex items-center gap-2 cursor-pointer ml-auto">
                    <input type="checkbox" id="includeApprovedCheckbox" onchange="updatePdfLink()" class="w-4 h-4">
                    <span class="text-sm text-gray-700">Include ACL APPROVED in PDF</span>
                </label>
            </div>
        </div>
        
        <script>
        const jsonData = "{json_escaped}";
        
        function updatePdfLink() {{
            const checkbox = document.getElementById('includeApprovedCheckbox');
            const probLink = document.getElementById('pdfButtonProblematic');
            const allLink = document.getElementById('pdfButtonAll');
            
            if (checkbox.checked) {{
                probLink.style.display = 'none';
                allLink.style.display = 'inline-block';
                allLink.href = '/api/delivery-analysis/pdf?delivery_number={delivery_number}&include_approved=true';
            }} else {{
                probLink.style.display = 'inline-block';
                allLink.style.display = 'none';
            }}
        }}
        
        function downloadJSON() {{
            const blob = new Blob([jsonData], {{type: 'application/json'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'delivery_{delivery_number}_analysis.json';
            a.click();
            URL.revokeObjectURL(url);
        }}
        </script>'''
        
        progress.log("COMPLETE", f"Response ready ({overall_elapsed:.2f}s total)")
        
        footer_html = f'''<details class="bg-gray-900 border-2 border-green-400 rounded-lg p-6 mb-6 cursor-pointer">
            <summary class="font-mono text-green-400 font-bold select-none hover:text-green-300">
                > Show Analysis Logs ({len(progress.stages)} stages)
            </summary>
            <pre class="text-xs mt-4 bg-black text-green-400 p-4 rounded overflow-x-auto font-mono">{progress_logs}</pre>
            <p class="text-xs text-gray-400 mt-3">Also check browser console (F12) for additional details</p>
        </details>'''
        
        html_response = f'''{top_buttons_html}
{summary_html}
{cards_section}
{footer_html}'''
        
        # Cache the full HTML response for 2 days
        cache.set(f"html_{delivery_number}", html_response, category="deliveries")
        progress.log("CACHE", "Full HTML response cached")
        
        return html_response
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        overall_elapsed = time.time() - overall_start
        print(f"[DELIVERY-ANALYSIS] Error: {str(e)} ({overall_elapsed:.2f}s)")
        print(error_details)
        return f'''<div class="bg-red-50 border-l-4 border-red-600 p-6 rounded">
            <h3 class="text-xl font-bold text-red-700 mb-2">Error</h3>
            <p class="text-red-700 mb-4">{str(e)}</p>
            <details class="bg-red-100 border border-red-300 rounded p-3">
                <summary class="cursor-pointer font-semibold text-red-700">Stack Trace</summary>
                <pre class="text-xs mt-2 overflow-x-auto font-mono">{error_details}</pre>
            </details>
            <p class="text-xs text-gray-600 mt-4">Completed in {overall_elapsed:.2f}s</p>
        </div>
        <script>
        console.error('Delivery Analysis Error:', {json.dumps(str(e))});
        console.error('Stack:', {json.dumps(error_details)});
        </script>'''









@app.get("/api/delivery-analysis/pdf")
def delivery_analysis_pdf(delivery_number: str, include_approved: str = "false"):
    """[ARCHIVED] Generate PDF with summary, priority ranking, and caching."""
    from delivery_analysis import get_delivery_po_data, apply_batching_to_delivery
    import time
    pdf_start = time.time()
    
    try:
        cache = get_cache_manager()
        cache_key = f"pdf_summary_{delivery_number}"
        print(f"[PDF] Checking cache: {cache_key}")
        
        cached_pdf = cache.get(cache_key, category="deliveries")
        if cached_pdf:
            print(f"[PDF-CACHE-HIT] Using cached PDF")
            pdf_bytes = cached_pdf.get('pdf_bytes')
            return Response(content=pdf_bytes, media_type="application/pdf", 
                          headers={"Content-Disposition": f'attachment; filename="delivery_{delivery_number}_report.pdf"'})
        
        print(f"[PDF-CACHE-MISS] Running full analysis")
        delivery_data = get_delivery_po_data(delivery_number)
        if not delivery_data["success"]:
            return JSONResponse({"error": "Query failed"}, status_code=400)
        
        delivery_data = apply_batching_to_delivery(delivery_data)
        mds_fam_ids = delivery_data.get('mds_fam_ids', [])
        po_rows = delivery_data.get('data', [])
        
        # Use optimized version - only query items in THIS delivery
        read_rates_cache = load_read_rates_for_items(mds_fam_ids)
        
        problematic_mds_ids = []
        problematic_details = {}
        total_delivery_qty = 0
        po_rows_by_mds_id = {}
        
        for row in po_rows:
            mds_id = str(row.get('mds_fam_id', ''))
            if mds_id not in po_rows_by_mds_id:
                po_rows_by_mds_id[mds_id] = []
            po_rows_by_mds_id[mds_id].append(row)
            qty = int(row.get('whpk_adjusted_qty', row.get('whpk_order_qty', 0))) if isinstance(row.get('whpk_adjusted_qty', row.get('whpk_order_qty')), (int, str)) else 0
            total_delivery_qty += qty
        
        for mds_id in mds_fam_ids:
            rate_data = read_rates_cache.get(str(mds_id), [])
            if not rate_data:
                continue
            avg_perf = get_avg_performance(rate_data)
            is_problematic = not (avg_perf >= 85)
            if is_problematic:
                item_qty = sum([int(row.get('whpk_adjusted_qty', row.get('whpk_order_qty', 0))) if isinstance(row.get('whpk_adjusted_qty', row.get('whpk_order_qty')), (int, str)) else 0 for row in po_rows_by_mds_id.get(str(mds_id), [])])
                bad_cases = int(item_qty * (100 - avg_perf) / 100)
                priority_score = (100 - avg_perf) * bad_cases
                problematic_mds_ids.append(mds_id)
                problematic_details[str(mds_id)] = {"avg_perf": avg_perf, "item_qty": item_qty, "bad_cases": bad_cases, "priority_score": priority_score}
        
        problematic_mds_ids.sort(key=lambda m: problematic_details[str(m)]['priority_score'], reverse=True)
        
        problematic_items_data = []
        if problematic_mds_ids:
            api_key = os.getenv("MDM_API_KEY", "")
            mdm_headers = {"Api-Key": api_key, "Facilitynum": os.getenv("MDM_FACILITY_NUM", "6068"), 
                          "Facilitycountrycode": os.getenv("MDM_FACILITY_COUNTRY_CODE", "US"), 
                          "Wmt-Userid": os.getenv("MDM_WMT_USERID", "mdm-ui")}
            
            with httpx.Client(verify=False, timeout=30.0) as client:
                for mds_id in problematic_mds_ids:
                    try:
                        api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{mds_id}/?xrefItemInfo=false"
                        response = client.get(api_url, headers=mdm_headers)
                        mdm_data = response.json()
                        item_data = extract_item_data(mdm_data)
                        item_data["mds_fam_id"] = str(mds_id)
                        item_data["acl_details"] = problematic_details.get(str(mds_id), {})
                        problematic_items_data.append(item_data)
                    except Exception as e:
                        problematic_items_data.append({"mds_fam_id": str(mds_id), "item_name": f"MDS {mds_id}", "acl_details": problematic_details.get(str(mds_id), {})})
        
        # Generate PDF using old-style FPDF syntax (no new_x/new_y)
        pdf = FPDF(orientation='L', unit='in', format='Letter')
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 22)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 0.4, f"Delivery {delivery_number} - Analysis Report", ln=True)
        pdf.ln(0.1)
        
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(0, 0, 0)
        total_bad_cases = sum([d.get('bad_cases', 0) for d in problematic_details.values()])
        avg_perf = sum([d.get('avg_perf', 0) for d in problematic_details.values()]) / len(problematic_details) if problematic_details else 0
        
        pdf.cell(0, 0.2, f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
        pdf.cell(0, 0.2, f"Total Items: {len(mds_fam_ids)} | Problematic: {len(problematic_details)} | Qty: {total_delivery_qty:,}", ln=True)
        pdf.cell(0, 0.2, f"Projected Bad Cases: {total_bad_cases:,} | Avg Perf: {avg_perf:.0f}%", ln=True)
        pdf.ln(0.2)
        
        if problematic_items_data:
            pdf.cell(0, 0.2, "Priority-Ranked Items (WORST FIRST):", ln=True)
            pdf.ln(0.1)
            
            # Table header
            col_widths = [0.8, 3.5, 0.8, 1.0, 1.0, 1.0]
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_fill_color(200, 220, 255)
            headers = ["Rank", "Item Name", "MDS", "Perf %", "Qty", "Bad Cases"]
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 0.25, h, border=1, align='C' if i in [0,2,3] else 'L', fill=True)
            pdf.ln()
            
            # Table rows
            pdf.set_font('Helvetica', '', 9)
            for idx, item in enumerate(problematic_items_data, 1):
                acl = item.get('acl_details', {})
                name = (item.get('item_name', 'N/A')[:25] + '...') if len(item.get('item_name', '')) > 25 else item.get('item_name', 'N/A')
                pdf.cell(col_widths[0], 0.22, str(idx), border=1, align='C')
                pdf.cell(col_widths[1], 0.22, name, border=1, align='L')
                pdf.cell(col_widths[2], 0.22, item.get('mds_fam_id', '')[:8], border=1, align='C')
                pdf.cell(col_widths[3], 0.22, f"{acl.get('avg_perf', 0):.0f}%", border=1, align='C')
                pdf.cell(col_widths[4], 0.22, f"{acl.get('item_qty', 0)}", border=1, align='R')
                pdf.cell(col_widths[5], 0.22, f"{acl.get('bad_cases', 0)}", border=1, align='R')
                pdf.ln()
        else:
            pdf.set_text_color(0, 128, 0)
            pdf.set_font('Helvetica', 'B', 14)
            pdf.cell(0, 0.4, "All Items ACL APPROVED!", ln=True)
        
        pdf_bytes = bytes(pdf.output())
        
        # Cache the PDF bytes
        cache.set(cache_key, {'pdf_bytes': pdf_bytes}, category="deliveries")
        print(f"[PDF] Cached PDF for delivery {delivery_number}")
        
        elapsed = time.time() - pdf_start
        print(f"[PDF] Generated in {elapsed:.2f}s")
        
        return Response(content=pdf_bytes, media_type="application/pdf", 
                       headers={"Content-Disposition": f'attachment; filename="delivery_{delivery_number}_report.pdf"'})
    
    except Exception as e:
        print(f"[PDF-ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)



@app.get("/api/delivery-analysis/pdf-item")
def delivery_pdf_single_item(mds_id: str):
    """[ARCHIVED] Generate PDF for a single problematic item with full details."""
    try:
        # Fetch MDM data for single item
        api_key = os.getenv("MDM_API_KEY", "")
        facility_num = os.getenv("MDM_FACILITY_NUM", "6068")
        facility_country = os.getenv("MDM_FACILITY_COUNTRY_CODE", "US")
        wmt_userid = os.getenv("MDM_WMT_USERID", "mdm-ui")
        
        mdm_headers = {
            "Api-Key": api_key,
            "Facilitynum": facility_num,
            "Facilitycountrycode": facility_country,
            "Wmt-Userid": wmt_userid
        }
        
        with httpx.Client(verify=False, timeout=30.0) as client:
            api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{mds_id}/?xrefItemInfo=false"
            response = client.get(api_url, headers=mdm_headers)
            response.raise_for_status()
            mdm_data = response.json()
        
        item_data = extract_item_data(mdm_data)
        item_data["mds_fam_id"] = str(mds_id)
        
        # Generate single-item PDF using batch function
        pdf_bytes = generate_batch_pdf([item_data])
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="mds_{mds_id}_detail.pdf"'}
        )
    
    except Exception as e:
        print(f"[DELIVERY-PDF-ITEM] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8050)
