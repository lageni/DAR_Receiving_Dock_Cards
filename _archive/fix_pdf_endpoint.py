"""Working PDF endpoint - insert before pdf-item endpoint"""

pdf_endpoint_code = '''
@app.get("/api/delivery-analysis/pdf")
def delivery_analysis_pdf(delivery_number: str, include_approved: str = "false"):
    """Generate PDF with summary, priority ranking, and caching."""
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
        read_rates_cache = load_read_rates()
        
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

'''

# Write to file
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find insertion point
marker = '@app.get("/api/delivery-analysis/pdf-item")'
if marker in content:
    content = content.replace(marker, pdf_endpoint_code + '\n\n' + marker)
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("[SUCCESS] PDF endpoint inserted with old-style FPDF syntax")
else:
    print("[ERROR] Could not find marker")
