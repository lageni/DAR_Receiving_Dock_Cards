"""PDF generation for a batch of items (multi-page PDF)."""
from fpdf import FPDF

from dar_app.department_bands import get_contrasting_text_rgb, get_department_band
from dar_app.metrics import get_avg_performance, get_recommendation, get_trend_status
from dar_app.pdf_export import sanitize_for_pdf
from dar_app.read_rates_data import load_read_rates

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
        # ONLY generate department bands if PO event is "import"
        po_event = item_data.get("po_event", "").lower()
        print(f"[BATCH-PDF] Item {idx + 1}: PO Event = '{po_event}'")
        
        if po_event == "import":
            print(f"[BATCH-PDF] Item {idx + 1}: Generating department bands (IMPORT)")
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
                master_pdf.set_text_color(*get_contrasting_text_rgb(rgb))  # AUTO BLACK/WHITE FOR READABILITY
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
        else:
            print(f"[BATCH-PDF] Item {idx + 1}: Skipping department bands (event='{po_event}', not 'import')")
        
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
