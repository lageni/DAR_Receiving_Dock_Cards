"""HTML rendering: search-result cards (format_results) and the print-card page."""
import json
import sqlite3
from urllib.parse import urlencode

from dar_app.charts import get_read_rate_chart
from dar_app.metrics import get_avg_performance, get_recommendation, get_trend_status
from dar_app.read_rates_data import get_database_path, load_read_rates

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
