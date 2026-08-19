"""Route: /api/delivery-analysis/search - the main analysis endpoint."""
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from delivery_analysis import apply_batching_to_delivery, get_delivery_po_data
from dar_app.card_render import extract_item_data
from dar_app.metrics import get_avg_performance, get_recommendation
from dar_app.read_rates_data import load_read_rates_for_items

router = APIRouter()

@router.get("/api/delivery-analysis/search", response_class=HTMLResponse)
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
