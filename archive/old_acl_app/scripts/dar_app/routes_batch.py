"""Routes: /batch/random, /batch/pdf."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, Response

from dar_app.card_render import extract_item_data
from dar_app.pdf_export_batch import generate_batch_pdf

router = APIRouter()

@router.get("/batch/random", response_class=HTMLResponse)
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
@router.get("/batch/pdf")
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
