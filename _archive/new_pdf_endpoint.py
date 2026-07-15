"""New PDF endpoint with proper caching, summary page, and priority ranking."""

def setup_pdf_endpoint(app, get_cache_manager, get_delivery_po_data, apply_batching_to_delivery,
                      load_read_rates, get_avg_performance, get_trend_status, extract_item_data,
                      Response, JSONResponse):
    \"\"\"Register the new PDF endpoint with the app.\"\"\"
    from fpdf import FPDF
    import httpx
    import os
    import time
    
    @app.get("/api/delivery-analysis/pdf")
    def delivery_analysis_pdf(delivery_number: str, include_approved: str = "false"):
        \"\"\"Generate PDF batch report with summary page, priority ranking, and caching.\"\"\"
        pdf_start = time.time()
        
        try:
            cache = get_cache_manager()
            cache_key = f"pdf_summary_{delivery_number}"
            print(f"[PDF-CACHE] Checking cache for {cache_key}")
            
            # === CACHE CHECK ===
            cached_pdf = cache.get(cache_key, category="deliveries")
            if cached_pdf:
                print(f"[PDF-CACHE-HIT] Using cached PDF (saving ~15 seconds)")
                pdf_bytes = cached_pdf.get('pdf_bytes')
                elapsed = time.time() - pdf_start
                print(f"[PDF] Generated from cache in {elapsed:.2f}s")
                return Response(
                    content=pdf_bytes,
                    media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="delivery_{delivery_number}_report.pdf"'}
                )
            
            print(f"[PDF-CACHE-MISS] Running full analysis")
            delivery_data = get_delivery_po_data(delivery_number)
            if not delivery_data["success"]:
                return JSONResponse({"error": "Query failed"}, status_code=400)
            
            delivery_data = apply_batching_to_delivery(delivery_data)
            mds_fam_ids = delivery_data.get('mds_fam_ids', [])
            po_rows = delivery_data.get('data', [])
            
            # Step 1: Identify & score problematic items
            read_rates_cache = load_read_rates()
            problematic_mds_ids = []
            problematic_details = {}
            total_delivery_qty = 0
            
            # Build PO rows lookup for fast access
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
                trend = get_trend_status(rate_data)
                
                if avg_perf >= 85:
                    is_problematic = False
                elif avg_perf < 50:
                    is_problematic = True
                elif "Improving" in trend:
                    is_problematic = True
                else:
                    is_problematic = True
                
                if is_problematic:
                    # Calculate quantity for this item
                    item_qty = 0
                    for row in po_rows_by_mds_id.get(str(mds_id), []):
                        item_qty += int(row.get('whpk_adjusted_qty', row.get('whpk_order_qty', 0))) if isinstance(row.get('whpk_adjusted_qty', row.get('whpk_order_qty')), (int, str)) else 0
                    
                    # Calculate projected bad cases
                    bad_cases = int(item_qty * (100 - avg_perf) / 100)
                    
                    # Priority score: worse performance + higher qty impact = higher priority
                    priority_score = (100 - avg_perf) * bad_cases
                    
                    problematic_mds_ids.append(mds_id)
                    problematic_details[str(mds_id)] = {
                        "avg_perf": avg_perf,
                        "trend": trend,
                        "item_qty": item_qty,
                        "bad_cases": bad_cases,
                        "priority_score": priority_score
                    }
            
            # Sort by priority (worst first)
            problematic_mds_ids.sort(key=lambda mds_id: problematic_details[str(mds_id)]['priority_score'], reverse=True)
            
            # Step 2: Fetch MDM data for problematic items
            problematic_items_data = []
            if problematic_mds_ids:
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
                    for mds_id in problematic_mds_ids:
                        try:
                            api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{mds_id}/?xrefItemInfo=false"
                            response = client.get(api_url, headers=mdm_headers)
                            response.raise_for_status()
                            mdm_data = response.json()
                            item_data = extract_item_data(mdm_data)
                            item_data["mds_fam_id"] = str(mds_id)
                            item_data["acl_details"] = problematic_details.get(str(mds_id), {})
                            problematic_items_data.append(item_data)
                        except Exception as e:
                            print(f"[PDF-MDM] Error {mds_id}: {str(e)}")
                            problematic_items_data.append({
                                "mds_fam_id": str(mds_id),
                                "item_name": f"MDS {mds_id}",
                                "image_url": "",
                                "acl_details": problematic_details.get(str(mds_id), {})
                            })
            
            # Step 3: Generate PDF with summary + priority-ranked items
            pdf = FPDF(orientation='L', unit='in', format='Letter')
            
            # Summary Page
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 22)
            pdf.set_text_color(0, 51, 102)
            pdf.cell(0, 0.4, f"Delivery {delivery_number} - Analysis Report", new_x=0, new_y=0.5)
            
            pdf.set_font('Helvetica', '', 11)
            pdf.set_text_color(0, 0, 0)
            
            # Calculate summary stats
            total_bad_cases = sum([d.get('bad_cases', 0) for d in problematic_details.values()])
            avg_performance = sum([d.get('avg_perf', 0) for d in problematic_details.values()]) / len(problematic_details) if problematic_details else 0
            
            pdf.cell(0, 0.2, f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", new_x=0, new_y=0.2)
            pdf.cell(0, 0.2, f"Total Items: {len(mds_fam_ids)} | Problematic: {len(problematic_details)} | Delivery Qty: {total_delivery_qty:,} cases", new_x=0, new_y=0.2)
            pdf.cell(0, 0.2, f"Projected Bad Cases: {total_bad_cases:,} | Avg Performance: {avg_performance:.0f}%", new_x=0, new_y=0.3)
            
            # Summary table
            if problematic_items_data:
                pdf.cell(0, 0.2, f"Priority-Ranked Problematic Items (WORST FIRST):", new_x=0, new_y=0.3)
                
                # Table header
                col_widths = [0.8, 3.5, 0.8, 1.0, 1.0, 1.0]
                pdf.set_font('Helvetica', 'B', 10)
                pdf.set_fill_color(200, 220, 255)
                pdf.cell(col_widths[0], 0.25, "Rank", border=1, align='C', fill=True, new_x=0)
                pdf.cell(col_widths[1], 0.25, "Item Name", border=1, align='L', fill=True, new_x=0)
                pdf.cell(col_widths[2], 0.25, "MDS", border=1, align='C', fill=True, new_x=0)
                pdf.cell(col_widths[3], 0.25, "Perf %", border=1, align='C', fill=True, new_x=0)
                pdf.cell(col_widths[4], 0.25, "Qty", border=1, align='R', fill=True, new_x=0)
                pdf.cell(col_widths[5], 0.25, "Bad Cases", border=1, align='R', fill=True, new_y=0.25)
                
                # Table rows
                pdf.set_font('Helvetica', '', 9)
                for idx, item in enumerate(problematic_items_data, 1):
                    mds = item.get('mds_fam_id', '')[:8]
                    acl = item.get('acl_details', {})
                    name = (item.get('item_name', 'N/A')[:25] + '...') if len(item.get('item_name', '')) > 25 else item.get('item_name', 'N/A')
                    pdf.cell(col_widths[0], 0.22, str(idx), border=1, align='C', new_x=0)
                    pdf.cell(col_widths[1], 0.22, name, border=1, align='L', new_x=0)
                    pdf.cell(col_widths[2], 0.22, mds, border=1, align='C', new_x=0)
                    pdf.cell(col_widths[3], 0.22, f"{acl.get('avg_perf', 0):.0f}%", border=1, align='C', new_x=0)
                    pdf.cell(col_widths[4], 0.22, f"{acl.get('item_qty', 0)}", border=1, align='R', new_x=0)
                    pdf.cell(col_widths[5], 0.22, f"{acl.get('bad_cases', 0)}", border=1, align='R', new_y=0.22)
            else:
                pdf.set_text_color(0, 128, 0)
                pdf.set_font('Helvetica', 'B', 14)
                pdf.cell(0, 0.4, "All Items ACL APPROVED!", new_x=0, new_y=0.5)
            
            pdf_bytes = bytes(pdf.output())
            
            # Cache the PDF
            cache.set(cache_key, {'pdf_bytes': pdf_bytes}, category="deliveries")
            print(f"[PDF] Cached analysis for delivery {delivery_number}")
            
            elapsed = time.time() - pdf_start
            print(f"[PDF] Generated in {elapsed:.2f}s")
            
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="delivery_{delivery_number}_report.pdf"'}
            )
        
        except Exception as e:
            print(f"[PDF-ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            return JSONResponse({"error": str(e)}, status_code=500)
