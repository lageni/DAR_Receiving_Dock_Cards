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


def get_read_rate_chart(mds_fam_id: str) -> str:
    """Generate Chart.js HTML for read rate trend."""
    rates = load_read_rates()
    data = rates.get(str(mds_fam_id), [])
    
    if not data or len(data) == 0:
        return ""
    
    # Format data for Chart.js - use abbreviated month+year for labels
    labels = [format_date_for_chart(d["date"]) for d in data]
    values = [d["null_pct"] for d in data]
    
    # Create chart ID
    chart_id = f"chart_{mds_fam_id}"
    
    # Safely build the data JSON string
    labels_json = json.dumps(labels)
    values_json = json.dumps(values)
    
    return f'''<div class="mt-6 bg-white p-4 rounded border">
        <h4 class="text-sm font-bold mb-3">Null Read % Trend</h4>
        <div style="height: 300px; position: relative;">
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
                            label: "Null Read %",
                            data: values,
                            borderColor: "#0053e2",
                            backgroundColor: "rgba(0, 83, 226, 0.1)",
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3,
                            pointRadius: 4,
                            pointBackgroundColor: "#0053e2"
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                display: true,
                                position: "top"
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
    <header class="bg-white border-b px-4 py-6">
        <h1 class="text-3xl font-bold text-blue-600">CodePuppy DAR</h1>
        <p class="text-sm text-gray-600">Inventory Search</p>
    </header>
    <main class="max-w-4xl mx-auto px-4 py-8">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="bg-white p-6 rounded border shadow-sm">
                <h2 class="font-bold mb-4">Search</h2>
                <form id="searchForm" hx-get="/api/inventory/search" hx-target="#results">
                    <div class="space-y-3">
                        <div>
                            <label class="block text-xs font-semibold text-gray-700 mb-1">Item ID</label>
                            <input type="text" id="itemIdInput" name="item_id" placeholder="665540630" required class="w-full px-3 py-2 border rounded text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-gray-700 mb-1">ID Type</label>
                            <select name="id_type" class="w-full px-3 py-2 border rounded text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                                <option value="ITEM_NUMBER">Item Number</option>
                                <option value="UPC">UPC</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-gray-700 mb-1">Node</label>
                            <input type="text" name="node" value="6068" class="w-full px-3 py-2 border rounded text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                        </div>
               </div>
                    <button type="submit" class="w-full mt-4 bg-blue-600 text-white py-2 rounded font-semibold hover:bg-blue-700">Search</button>
                </form>
                <button onclick="loadExample()" class="w-full mt-2 bg-gray-200 text-gray-800 py-2 rounded font-semibold hover:bg-gray-300">Load Example (665540630)</button>
            </div>
            <div class="lg:col-span-2 bg-white p-6 rounded border shadow-sm">
                <div id="results" class="text-sm text-gray-500">Results appear here...</div>
            </div>
        </div>
    </main>
    <script>
        function loadExample() {
            document.getElementById('itemIdInput').value = '665540630';
            htmx.ajax('GET', '/api/inventory/search?item_id=665540630&id_type=ITEM_NUMBER&node=6068', '#results');
        }
    </script>
</body>
</html>"""


@app.get("/api/inventory/search", response_class=HTMLResponse)
async def search_inventory(item_id: str, id_type: str = "ITEM_NUMBER", node: str = None):
    try:
        jwt = os.getenv("INVENTORY_JWT_TOKEN")
        user_id = os.getenv("INVENTORY_USER_ID")
        api_url = os.getenv("INVENTORY_API_URL", "https://inventory-viewer.prod.walmart.net")
        node = node or os.getenv("INVENTORY_DEFAULT_NODE", "6068")
        country_code = os.getenv("INVENTORY_COUNTRY_CODE", "US")

        if not jwt or not user_id:
            return '<div class="text-red-600">Error: Missing credentials in .env</div>'

        headers = {"Authorization": jwt, "UserId": user_id}
        params = {
            "node": node,
            "itemId": item_id,
            "idType": id_type,
            "userName": user_id,
            "countryCode": country_code,
            "isOfferIdRollupEnabled": "false",
        }

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.get(f"{api_url}/get-summary", params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        return format_results(data, item_id)

    except httpx.HTTPStatusError as e:
        return f'<div class="text-red-600">API Error {e.response.status_code}</div>'
    except Exception as e:
        return f'<div class="text-red-600">Error: {str(e)}</div>'


@app.get("/print-card", response_class=HTMLResponse)
async def print_card(item_id: str, product_id: str = "", gtin: str = "", supplier_dept: str = ""):
    try:
        jwt = os.getenv("INVENTORY_JWT_TOKEN")
        user_id = os.getenv("INVENTORY_USER_ID")
        api_url = os.getenv("INVENTORY_API_URL", "https://inventory-viewer.prod.walmart.net")
        node = os.getenv("INVENTORY_DEFAULT_NODE", "6068")
        country_code = os.getenv("INVENTORY_COUNTRY_CODE", "US")

        if not jwt or not user_id:
            return '<div class="text-red-600">Error: Missing credentials in .env</div>'

        headers = {"Authorization": jwt, "UserId": user_id}
        params = {
            "node": node,
            "itemId": item_id,
            "idType": "ITEM_NUMBER",
            "userName": user_id,
            "countryCode": country_code,
            "isOfferIdRollupEnabled": "false",
        }

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.get(f"{api_url}/get-summary", params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        return generate_print_card(data, item_id)

    except Exception as e:
        return f'<div class="text-red-600">Error: {str(e)}</div>'


@app.get("/print-card-pdf")
async def print_card_pdf(item_id: str, product_id: str = "", gtin: str = "", supplier_dept: str = ""):
    """Generate a clean PDF of the print card for download."""
    try:
        jwt = os.getenv("INVENTORY_JWT_TOKEN")
        user_id = os.getenv("INVENTORY_USER_ID")
        api_url = os.getenv("INVENTORY_API_URL", "https://inventory-viewer.prod.walmart.net")
        node = os.getenv("INVENTORY_DEFAULT_NODE", "6068")
        country_code = os.getenv("INVENTORY_COUNTRY_CODE", "US")

        if not jwt or not user_id:
            return '<div class="text-red-600">Error: Missing credentials in .env</div>'

        headers = {"Authorization": jwt, "UserId": user_id}
        params = {
            "node": node,
            "itemId": item_id,
            "idType": "ITEM_NUMBER",
            "userName": user_id,
            "countryCode": country_code,
            "isOfferIdRollupEnabled": "false",
        }

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.get(f"{api_url}/get-summary", params=params, headers=headers)
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
    product_id = item_data["product_id"]
    supplier_dept = item_data["supplier_dept"]

    image_html = ""
    if image_url:
        image_html = f'<img src="{image_url}" alt="{item_name}" class="w-full h-48 object-cover rounded border mb-3">'

    url_html = ""
    if image_url:
        url_html = f'<div class="text-xs text-gray-600 mt-2 break-all"><strong>Image URL:</strong><br><code class="text-blue-600 text-xs"><a href="{image_url}" target="_blank" class="underline">{image_url}</a></code></div>'

    print_params = urlencode({
        "item_id": item_id,
        "product_id": product_id,
        "gtin": gtin,
        "supplier_dept": supplier_dept
    })
    print_card_html = f'<a href="/print-card-pdf?{print_params}" class="inline-block mt-3 px-4 py-2 bg-green-600 text-white text-sm rounded font-semibold hover:bg-green-700">Download PDF</a>'
    
    # Get read rate trend chart
    chart_html = get_read_rate_chart(item_id)

    return f"""<div class="space-y-4">
        <div class="bg-blue-50 p-4 rounded border border-blue-200">
            {image_html}
            <h3 class="font-bold">{item_name}</h3>
            <p class="text-xs text-gray-600 mt-1">Item: <code class="bg-white px-2 py-1 rounded text-blue-600 font-mono text-xs">{item_id}</code></p>
            {url_html}
            {print_card_html}
        </div>
        {chart_html}
        <div class="bg-white p-4 rounded border">
            <h4 class="text-sm font-bold mb-2">Full Response</h4>
            <pre class="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-96 font-mono border">{json_str}</pre>
        </div>
    </div>"""


def extract_item_data(data: dict) -> dict:
    """Extract product and inventory data from API response."""
    item_data = {
        "item_name": "Unknown Item",
        "item_id": "",
        "image_url": "",
        "gtin": "",
        "product_id": "",
        "supplier_dept": "",
        "inventory_status": "Unknown"
    }
    
    if isinstance(data, dict) and "productResponse" in data:
        product_resp = data["productResponse"]
        if isinstance(product_resp, dict) and "docs" in product_resp:
            docs = product_resp["docs"]
            if isinstance(docs, list) and len(docs) > 0:
                doc = docs[0]
                if isinstance(doc, dict):
                    item_data["item_name"] = doc.get("product.product_name", "Unknown Item")
                    item_data["image_url"] = doc.get("product.primary_image_url", "")
                    item_data["gtin"] = doc.get("si.consumableGtin", doc.get("product.gtin", ""))
                    item_data["product_id"] = doc.get("product.product_id", "")
                    item_data["supplier_dept"] = str(doc.get("si.supplierDeptNbr", ""))
    
    if isinstance(data, dict) and "inventoryResponse" in data:
        inv_resp = data["inventoryResponse"]
        if isinstance(inv_resp, dict):
            status_code = inv_resp.get("statusCode")
            item_data["inventory_status"] = "In Stock" if status_code == 200 else f"Status: {status_code}"
    
    return item_data


def generate_print_card(data: dict, item_id: str) -> str:
    item_data = extract_item_data(data)
    item_name = item_data["item_name"]
    image_url = item_data["image_url"]
    gtin = item_data["gtin"]
    product_id = item_data["product_id"]
    supplier_dept = item_data["supplier_dept"]
    inventory_status = item_data["inventory_status"]

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
    product_id = sanitize_for_pdf(item_data.get("product_id", ""))
    supplier_dept = sanitize_for_pdf(item_data.get("supplier_dept", ""))
    inventory_status = sanitize_for_pdf(item_data.get("inventory_status", "Unknown"))
    # Keep original item_id for dictionary lookup, use sanitized version for PDF display
    item_id_orig = item_data.get("item_id", "")
    item_id = sanitize_for_pdf(item_id_orig)
    
    # LEFT COLUMN: Product Image
    img_x = 0.4
    img_y = 0.4
    img_width = 2.8
    img_height = 3.2
    
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
    
    # RIGHT COLUMN: Product Details (starting at x=3.5")
    content_x = 3.5
    current_y = 0.4
    
    # Product Name (title)
    pdf.set_xy(content_x, current_y)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(0, 83, 226)  # Walmart Blue
    pdf.multi_cell(6.8, 0.4, item_name, align='L')
    current_y = pdf.get_y() + 0.1
    
    # Separator line
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.01)
    pdf.line(content_x, current_y, 10.2, current_y)
    current_y += 0.2
    
    # Details in a clean format
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(0, 0, 0)
    
    details = []
    if item_id:
        details.append(("Item ID:", item_id))
    if product_id:
        details.append(("Product ID:", product_id))
    if gtin:
        details.append(("GTIN:", gtin))
    if supplier_dept:
        details.append(("Supplier Dept:", supplier_dept))
    
    # Draw details as label: value pairs
    for label, value in details:
        pdf.set_xy(content_x, current_y)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(1.2, 0.25, label, align='L')
        
        pdf.set_xy(content_x + 1.3, current_y)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(5.5, 0.25, str(value), align='L')
        current_y += 0.28
    
    # Status section
    current_y += 0.15
    pdf.set_xy(content_x, current_y)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(1.2, 0.25, "Status:", align='L')
    
    pdf.set_xy(content_x + 1.3, current_y)
    pdf.set_font("Helvetica", "B", 10)
    
    # Color-code status
    if "In Stock" in inventory_status or "200" in inventory_status:
        pdf.set_text_color(0, 128, 0)  # Green
    elif "404" in inventory_status or "Unknown" in inventory_status:
        pdf.set_text_color(255, 0, 0)  # Red
    else:
        pdf.set_text_color(200, 140, 0)  # Orange
    
    pdf.cell(5.5, 0.25, inventory_status, align='L')
    
    # Read Rates section
    current_y += 0.35
    pdf.set_xy(content_x, current_y)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(6.8, 0.25, "Read Rates (Null %)", align='L')
    current_y += 0.28
    
    # Get read rates for this item (use original item_id for lookup)
    rates = load_read_rates()
    item_rates = rates.get(str(item_id_orig), [])
    
    if item_rates:
        # Show latest record
        latest = item_rates[-1]
        pdf.set_xy(content_x, current_y)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(2.0, 0.25, f"Latest ({latest['date']}):", align='L')
        pdf.cell(4.8, 0.25, f"{latest['null_pct']:.1f}% null", align='L')
        current_y += 0.25
        
        # Show trend if more than 1 record
        if len(item_rates) > 1:
            first = item_rates[0]
            trend = "improving" if latest['null_pct'] > first['null_pct'] else "declining"
            pdf.set_xy(content_x, current_y)
            pdf.cell(2.0, 0.25, f"Trend:", align='L')
            pdf.cell(4.8, 0.25, f"{trend} ({first['null_pct']:.1f}% -> {latest['null_pct']:.1f}%)", align='L')
    else:
        pdf.set_xy(content_x, current_y)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(6.8, 0.25, "No read rate data available", align='L')
    
    # Convert to bytes
    result = pdf.output(dest='S')
    return bytes(result) if isinstance(result, bytearray) else result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
