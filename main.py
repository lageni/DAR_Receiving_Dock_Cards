import os
import json
import csv
from pathlib import Path
from urllib.parse import urlencode
from io import BytesIO
from collections import defaultdict
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
import httpx
from fpdf import FPDF
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

app = FastAPI(title="CodePuppy DAR")

# Cache for read rates data
_read_rates_cache = None


def load_read_rates():
    """Load read_rates.csv and cache it. Returns dict[mds_fam_id] -> list of records."""
    global _read_rates_cache
    if _read_rates_cache is not None:
        return _read_rates_cache
    
    csv_path = Path(__file__).parent / "read_rates.csv"
    if not csv_path.exists():
        return {}
    
    rates_by_family = defaultdict(list)
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    mds_fam_id = row.get("MDS_FAM_ID", "").strip()
                    ts_date = row.get("TS_DATE", "").strip()
                    event_cnt = int(row.get("ACL_EVENT_CNT", 0))
                    null_cnt = int(row.get("ACL_NULL_CNT", 0))
                    
                    if mds_fam_id and event_cnt > 0:
                        null_pct = (null_cnt / event_cnt) * 100
                        rates_by_family[mds_fam_id].append({
                            "date": ts_date,
                            "null_pct": null_pct,
                            "event_cnt": event_cnt,
                            "null_cnt": null_cnt
                        })
                except (ValueError, KeyError):
                    pass
        
        # Sort each family's records by date
        for fam_id in rates_by_family:
            rates_by_family[fam_id].sort(key=lambda x: x["date"])
        
        _read_rates_cache = rates_by_family
    except Exception as e:
        print(f"Error loading read_rates.csv: {e}")
        _read_rates_cache = {}
    
    return _read_rates_cache


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
    """Calculate average null percentage (ACL Performance)."""
    if not item_rates:
        return 0
    total = sum(r['null_pct'] for r in item_rates)
    return total / len(item_rates)


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


def get_recommendation(avg_perf: float, trend_status: str) -> tuple:
    """Get ACL recommendation based on performance and trend.
    
    Returns: (recommendation_text, color_class, bg_color_class)
    
    Rules (subject to change):
    - > 85%: ACL APPROVED (green)
    - < 85% and Improving: ADEQUATE PERFORMANCE (yellow)
    - < 85% and Declining: REQUIRES MANUAL INSPECTION (yellow)
    - < 50%: WORKSTATION RECOMMENDED (red)
    """
    if avg_perf >= 85:
        return "ACL APPROVED", "#16a34a", "from-green-50 via-green-50 to-green-100 border-green-300"
    elif avg_perf < 50:
        return "WORKSTATION RECOMMENDED", "#dc2626", "from-red-50 via-red-50 to-red-100 border-red-300"
    elif avg_perf < 85:
        if trend_status == "Improving":
            return "ADEQUATE PERFORMANCE", "#eab308", "from-yellow-50 via-yellow-50 to-yellow-100 border-yellow-300"
        else:  # Declining or Consistent
            return "REQUIRES MANUAL INSPECTION", "#eab308", "from-yellow-50 via-yellow-50 to-yellow-100 border-yellow-300"
    return "UNKNOWN", "#6b7280", "from-gray-50 via-gray-50 to-gray-100 border-gray-300"

def get_read_rate_chart(mds_fam_id: str) -> str:
    """Generate Chart.js HTML for read rate trend from read_rates.db"""
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
            <div class="text-xs text-gray-600 mt-2 italic">Directive Action (Subject to Change)</div>
        </div>
    </div>'''
    
    return f'''<div class="mt-4 bg-white p-4 rounded border">
        <h2 class="text-3xl font-black text-center text-blue-600 mb-4">ACL Performance %</h2>
        {rec_card}
        {perf_card}
        <div style="height: 400px; position: relative;">
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


@app.get("/", response_class=HTMLResponse)
async def root():
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
            </div>
            <div class="mt-3 text-xs text-gray-600 italic">Note: These rules are directive guidelines subject to change</div>
        </details>
        <!-- Search Bar at Top -->
        <div class="bg-white p-3 rounded border shadow-sm mb-4">
            <form id="searchForm" hx-get="/api/inventory/search" hx-target="#results" class="flex gap-2">
                <input type="text" id="itemIdInput" name="item_id" placeholder="Enter Item ID (e.g., 659608850)" required class="flex-1 px-3 py-2 border rounded text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                <input type="hidden" name="id_type" value="ITEM_NUMBER">
                <input type="hidden" name="node" value="6068">
                <button type="submit" class="bg-blue-600 text-white px-6 py-2 rounded font-semibold text-sm hover:bg-blue-700">Search</button>
                <button type="button" onclick="loadExample()" class="bg-gray-300 text-gray-800 px-4 py-2 rounded font-semibold text-sm hover:bg-gray-400">Example</button>
            </form>
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


@app.get("/print-card-pdf")
async def print_card_pdf(item_id: str, product_id: str = "", gtin: str = "", catalog_gtin: str = "", supplier_dept: str = ""):
    """Generate PDF of the print card for download (MDM API)."""
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
    product_id = item_data["product_id"]
    supplier_dept = item_data["supplier_dept"]

    image_html = ""
    if image_url:
        image_html = f'<img src="{image_url}" alt="{item_name}" class="w-full h-auto object-cover rounded border mb-2">'

    # Simple item details - minimal styling
    item_details = f'<div class="text-center space-y-1 text-xs text-gray-700"><p><strong>Item:</strong> {item_id}</p>'
    if product_id:
        item_details += f'<p><strong>Product ID:</strong> {product_id}</p>'
    if gtin:
        item_details += f'<p><strong>GTIN:</strong> {gtin}</p>'
    if catalog_gtin:
        item_details += f'<p><strong>Catalog GTIN:</strong> {catalog_gtin}</p>'
    if supplier_dept:
        item_details += f'<p><strong>Supplier:</strong> {supplier_dept}</p>'
    item_details += '</div>'

    print_params = urlencode({
        "item_id": item_id,
        "product_id": product_id,
        "gtin": gtin,
        "catalog_gtin": catalog_gtin,
        "supplier_dept": supplier_dept
    })
    print_card_html = f'<a href="/print-card-pdf?{print_params}" class="inline-block mt-2 px-4 py-2 bg-green-600 text-white text-sm rounded font-semibold hover:bg-green-700">Download PDF</a>'
    
    # Get read rate metrics for performance display
    rates = load_read_rates()
    rate_data = rates.get(str(item_id), [])
    perf_html = ""
    
    if rate_data and len(rate_data) > 0:
        avg_perf = get_avg_performance(rate_data)
        trend_status = get_trend_status(rate_data)
        color = get_color_for_performance(avg_perf)
        recommendation, rec_color, rec_bg = get_recommendation(avg_perf, trend_status)
        
        perf_html = f'''<div class="bg-white p-4 rounded border">
            <h2 class="text-2xl font-bold text-center text-blue-600 mb-4">ACL Performance %</h2>
            <div class="bg-gradient-to-br {rec_bg} p-6 rounded-lg border-2 shadow mb-4">
                <div class="text-center">
                    <div class="text-4xl font-black" style="color: {rec_color};">{recommendation}</div>
                    <div class="text-xs text-gray-600 mt-1 italic">Directive Action</div>
                </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div class="bg-yellow-50 border-2 border-yellow-300 p-4 rounded text-center">
                    <div class="text-xs text-yellow-700 font-bold uppercase">Avg Performance</div>
                    <div class="text-4xl font-black mt-2" style="color: {color};">{avg_perf:.1f}%</div>
                </div>
                <div class="bg-purple-50 border-2 border-purple-300 p-4 rounded text-center">
                    <div class="text-xs text-purple-700 font-bold uppercase">Trend</div>
                    <div class="text-2xl font-black mt-2 text-purple-900">{trend_status}</div>
                </div>
            </div>
        </div>'''

    # LEFT column: Product image and details
    left_html = f"""<div class="space-y-3">
        <div class="bg-white p-3 rounded border">
            {image_html}
            <h2 class="font-bold text-xl text-blue-600 text-center mt-2 mb-1">{item_name}</h2>
            {item_details}
            <div class="text-center mt-2">{print_card_html}</div>
        </div>
        <details class="bg-white p-3 rounded border cursor-pointer group">
            <summary class="font-semibold text-xs text-gray-600 hover:text-gray-900 select-none">Developer Info</summary>
            <div class="mt-2 pt-2 border-t">
                <pre class="text-xs bg-gray-50 p-2 rounded overflow-auto max-h-32 font-mono border">{json_str}</pre>
            </div>
        </details>
    </div>"""
    
    # Combine left and right columns
    html = left_html
    if perf_html:
        # Return both columns wrapped in grid
        return f'''<div id="results" class="space-y-3">
            {left_html}
        </div>
        <div id="results-chart">
            {perf_html}
        </div>'''
    
    return left_html




def extract_item_data(data: dict) -> dict:
    """Extract product data from MDM API response."""
    item_data = {
        "item_name": "Unknown Item",
        "item_id": "",
        "image_url": "",
        "gtin": "",
        "catalog_gtin": "",
        "product_id": "",
        "supplier_dept": "",
        "inventory_status": "Unknown"
    }
    
    # MDM API response structure
    if isinstance(data, dict):
        # Item description/name
        if "description" in data and isinstance(data["description"], list) and len(data["description"]) > 0:
            desc = data["description"][0]
            if isinstance(desc, dict):
                item_data["item_name"] = desc.get("textValue", "Unknown Item").strip()
        
        # Item number
        if "number" in data:
            item_data["item_id"] = str(data["number"])
        
        # Image URL - use IMAGE_SIZE_450
        if "productDefinition" in data:
            prod_def = data["productDefinition"]
            if isinstance(prod_def, dict) and "imageDimension" in prod_def:
                img_dim = prod_def["imageDimension"]
                if isinstance(img_dim, dict):
                    item_data["image_url"] = img_dim.get("IMAGE_SIZE_450", "")
        
        # GTIN - try consumable first, then orderable
        if "consumableGTIN" in data:
            item_data["gtin"] = data["consumableGTIN"]
        elif "orderableGTIN" in data:
            item_data["gtin"] = data["orderableGTIN"]
        
        # CatalogGTIN - if it exists (NEW!)
        if "catalogGTIN" in data:
            item_data["catalog_gtin"] = data["catalogGTIN"]
        
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
        recommendation, rec_color, _ = get_recommendation(avg_perf, trend_status)

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
                {f'<div class="info-row"><div class="info-label">Product ID:</div><div class="info-value">{product_id}</div></div>' if product_id else ''}
                {f'<div class="info-row"><div class="info-label">Supplier Dept:</div><div class="info-value">{supplier_dept}</div></div>' if supplier_dept else ''}
            </div>
            <div class="info-section">
                <div class="info-label">Inventory Status</div>
                <div class="status-badge {'status-in-stock' if 'In Stock' in inventory_status else 'status-unknown'}">{inventory_status}</div>
            </div>
            <div class="info-section" style="border: 2px solid {rec_color}; padding: 12px; border-radius: 4px; background: rgba(0,0,0,0.02);">
                <div style="color: {rec_color}; font-weight: 700; font-size: 14px; text-align: center;">{recommendation}</div>
                <div style="color: #666; font-size: 9px; text-align: center; margin-top: 4px;">ACL Directive Action</div>
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


def generate_pdf(item_data: dict) -> bytes:
    """Generate a clean landscape PDF card with product information."""
    pdf = FPDF(orientation='L', unit='in', format='Letter')  # 11" x 8.5" landscape
    pdf.add_page()
    pdf.set_margins(0.4, 0.4, 0.4)
    
    item_name = sanitize_for_pdf(item_data.get("item_name", "Unknown Item"))
    image_url = item_data.get("image_url", "")
    gtin = sanitize_for_pdf(item_data.get("gtin", ""))
    catalog_gtin = sanitize_for_pdf(item_data.get("catalog_gtin", ""))
    product_id = sanitize_for_pdf(item_data.get("product_id", ""))
    supplier_dept = sanitize_for_pdf(item_data.get("supplier_dept", ""))
    inventory_status = sanitize_for_pdf(item_data.get("inventory_status", "Unknown"))
    # Keep original item_id for dictionary lookup, use sanitized version for PDF display
    item_id_orig = item_data.get("item_id", "")
    item_id = sanitize_for_pdf(item_id_orig)
    
    # LEFT COLUMN: Product Image (larger)
    img_x = 0.4
    img_y = 0.4
    img_width = 3.2  # Wider
    img_height = 3.8  # Taller
    
    # Draw image border
    pdf.set_draw_color(0, 83, 226)
    pdf.set_line_width(0.02)
    pdf.rect(img_x, img_y, img_width, img_height)
    
    if image_url:
        try:
            img_response = httpx.get(image_url, timeout=5)
            img_bytes = BytesIO(img_response.content)
            temp_img = "/tmp/product.jpg"
            with open(temp_img, 'wb') as f:
                f.write(img_bytes.getvalue())
            # Center image in the box
            pdf.image(temp_img, x=img_x+0.05, y=img_y+0.05, w=img_width-0.1, h=img_height-0.1)
        except:
            pass
    
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
    if product_id:
        details_text += f" | Product ID: {product_id}"
    if gtin:
        details_text += f" | GTIN: {gtin}"
    if catalog_gtin:
        details_text += f" | Catalog GTIN: {catalog_gtin}"
    if supplier_dept:
        details_text += f" | Supplier: {supplier_dept}"
    
    pdf.multi_cell(6.5, 0.2, details_text, align='C')
    current_y = pdf.get_y() + 0.1
    
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



@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
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
            <h2 class="text-xl font-bold mb-4">System Info</h2>
            <p class="text-sm text-gray-600 mb-3">Database: SQLite (read_rates.db)</p>
            <p class="text-sm text-gray-600 mb-3">API: MDM Item API (uwms-item.prod.us.walmart.net)</p>
            <p class="text-sm text-gray-600">Auth: MDM_API_KEY in .env</p>
        </div>
        
        <a href="/" class="inline-block px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700">Back to Search</a>
    </div>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
