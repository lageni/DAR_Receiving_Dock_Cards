"""Routes: /diagnostics/informix, /diagnostics/scheduler, scheduler search, test query."""
import base64
import json
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/diagnostics/informix", response_class=HTMLResponse)
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


@router.get("/diagnostics/scheduler", response_class=HTMLResponse)
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


@router.post("/api/scheduler/set-token", response_class=HTMLResponse)
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


@router.post("/api/scheduler/search", response_class=HTMLResponse)
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






@router.get("/test_informix_query", response_class=HTMLResponse)
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
