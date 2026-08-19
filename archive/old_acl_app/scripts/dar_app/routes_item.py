"""Routes: /item-analysis, /api/inventory/search, /print-card, /print-card-pdf."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from dar_app.card_render import extract_item_data, format_results, generate_print_card
from dar_app.pdf_export import generate_pdf

router = APIRouter()

@router.get("/item-analysis", response_class=HTMLResponse)
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
@router.get("/api/inventory/search", response_class=HTMLResponse)
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
@router.get("/print-card", response_class=HTMLResponse)
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
@router.get("/print-card-pdf")
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
