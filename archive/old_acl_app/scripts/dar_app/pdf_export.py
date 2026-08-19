"""PDF generation for a single item card."""
import uuid
from io import BytesIO

import httpx
from fpdf import FPDF

from dar_app.department_bands import get_contrasting_text_rgb, get_department_band
from dar_app.metrics import get_avg_performance, get_recommendation, get_trend_status
from dar_app.read_rates_data import load_read_rates

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


def generate_pdf(item_data: dict, master_pdf: FPDF = None, return_pdf_object: bool = False) -> bytes:
    """Generate a clean landscape PDF card with product information.
    
    If master_pdf is provided, add to that object instead of creating new.
    If return_pdf_object is True, return the FPDF object instead of bytes.
    """
    # Use provided PDF or create new one
    pdf = master_pdf if master_pdf else FPDF(orientation='L', unit='in', format='Letter')
    pdf.add_page()
    pdf.set_margins(0.4, 0.4, 0.4)
    
    item_name = sanitize_for_pdf(item_data.get("item_name", "Unknown Item"))
    image_url = item_data.get("image_url", "")
    gtin = sanitize_for_pdf(item_data.get("gtin", ""))
    catalog_gtin = sanitize_for_pdf(item_data.get("catalog_gtin", ""))
    product_id = sanitize_for_pdf(item_data.get("product_id", ""))
    supplier_dept = sanitize_for_pdf(item_data.get("supplier_dept", ""))
    inventory_status = sanitize_for_pdf(item_data.get("inventory_status", "Unknown"))
    vnpk_length = sanitize_for_pdf(item_data.get("vnpk_length", ""))
    vnpk_width = sanitize_for_pdf(item_data.get("vnpk_width", ""))
    vnpk_height = sanitize_for_pdf(item_data.get("vnpk_height", ""))
    casepack_type = sanitize_for_pdf(item_data.get("casepack_type", ""))
    vendor_qty = sanitize_for_pdf(item_data.get("vendor_pack_qty", ""))
    warehouse_qty = sanitize_for_pdf(item_data.get("warehouse_pack_qty", ""))
    # Keep original item_id for dictionary lookup, use sanitized version for PDF display
    item_id_orig = item_data.get("item_id", "")
    item_id = sanitize_for_pdf(item_id_orig)
    
    # DEBUG: Log what we extracted
    print(f"[PDF] Item {item_id_orig}: catalog_gtin='{catalog_gtin}', gtin='{gtin}', casepack='{casepack_type}'")
    
    # LEFT COLUMN: Product Image (larger)
    img_x = 0.4
    img_y = 0.4
    img_width = 3.2  # Wider
    img_height = 3.8  # Taller
    
    # Draw image border with shadow effect
    # Light shadow
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.01)
    pdf.rect(img_x + 0.05, img_y + 0.05, img_width, img_height)
    # Main border (Walmart Blue)
    pdf.set_draw_color(0, 83, 226)
    pdf.set_line_width(0.03)
    pdf.rect(img_x, img_y, img_width, img_height)
    
    if image_url:
        try:
            img_response = httpx.get(image_url, timeout=5)
            img_bytes = BytesIO(img_response.content)
            # Use unique temp file to avoid duplication
            temp_img = f"/tmp/product_{uuid.uuid4().hex[:8]}.jpg"
            with open(temp_img, 'wb') as f:
                f.write(img_bytes.getvalue())
            # Center image in the box
            pdf.image(temp_img, x=img_x+0.05, y=img_y+0.05, w=img_width-0.1, h=img_height-0.1)
        except Exception as e:
            print(f"[PDF] Image download failed: {str(e)}")
    
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
    if gtin:
        details_text += f" | GTIN: {gtin}"
    if catalog_gtin:
        details_text += f" | Catalog GTIN: {catalog_gtin}"
    if supplier_dept:
        details_text += f" | Dept #: {supplier_dept}"
    
    # Add casepack type and pack ratio
    pack_info_text = ""
    if casepack_type:
        pack_info_text = f"Pack Type: {casepack_type}"
        if vendor_qty and warehouse_qty:
            pack_info_text += f" | Pack Ratio: {vendor_qty}/{warehouse_qty}"
    elif vendor_qty and warehouse_qty:
        pack_info_text = f"Pack Ratio: {vendor_qty}/{warehouse_qty}"
    
    # Add vendorpack dimensions if available
    dimensions_text = ""
    if vnpk_length or vnpk_width or vnpk_height:
        dims_list = []
        dims_list.append(vnpk_length if vnpk_length else "--")
        dims_list.append(vnpk_width if vnpk_width else "--")
        dims_list.append(vnpk_height if vnpk_height else "--")
        dimensions_text = "Vendor Pack Dims (L x W x H): " + " x ".join(dims_list)
    
    pdf.multi_cell(6.5, 0.2, details_text, align='C')
    current_y = pdf.get_y() + 0.1
    
    # Add pack info below details - WITH PROMINENT CARD FOR CASEPACK TYPE
    if casepack_type:
        # Draw colored box for pack type (bold card style)
        pdf.set_xy(content_x, current_y)
        # Background color for card
        if "CASEPACK" in casepack_type.upper():
            pdf.set_fill_color(224, 242, 254)  # Light blue
            pdf.set_text_color(0, 83, 226)  # Walmart blue
        else:
            pdf.set_fill_color(252, 231, 243)  # Light pink
            pdf.set_text_color(236, 72, 153)  # Pink
        
        # Draw box
        pdf.set_draw_color(0, 83, 226) if "CASEPACK" in casepack_type.upper() else pdf.set_draw_color(236, 72, 153)
        pdf.set_line_width(0.02)
        box_height = 0.4
        pdf.rect(content_x, current_y, 6.5, box_height, 'FD')  # F = fill, D = border
        
        # Add pack type text
        pdf.set_font("Helvetica", "B", 12)  # Bold, larger font
        pdf.set_xy(content_x + 0.1, current_y + 0.08)
        pdf.cell(6.3, 0.25, casepack_type, align='C')
        current_y += box_height + 0.05
    
    # Add pack ratio info if available
    if vendor_qty and warehouse_qty:
        pdf.set_xy(content_x, current_y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 100, 100)
        ratio_text = f"Pack Ratio: {vendor_qty}/{warehouse_qty}"
        pdf.multi_cell(6.5, 0.15, ratio_text, align='C')
        current_y = pdf.get_y() + 0.05
    
    # Add vendorpack dimensions below pack info
    if dimensions_text:
        pdf.set_xy(content_x, current_y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(6.5, 0.15, dimensions_text, align='C')
        current_y = pdf.get_y() + 0.1
    
    # Add Department Band Trio (3 bands: Dept # | Category | Description)
    dept_band = get_department_band(supplier_dept)
    if dept_band:
        band_height = 0.11  # HALF SIZE
        rgb = dept_band["rgb"]
        
        # Band 1: Department Number (COLORED)
        pdf.set_xy(content_x, current_y)
        pdf.set_fill_color(*rgb)
        pdf.set_draw_color(0, 0, 0)  # BLACK BORDER
        pdf.set_line_width(0.02)
        pdf.rect(content_x, current_y, 3.0, band_height, 'FD')
        pdf.set_xy(content_x + 0.05, current_y + 0.01)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*get_contrasting_text_rgb(rgb))  # AUTO BLACK/WHITE FOR READABILITY
        pdf.cell(2.9, band_height - 0.01, f"Dept. {supplier_dept}", align='L')
        current_y += band_height
        
        # Band 2: Category Name (CARDBOARD)
        pdf.set_xy(content_x, current_y)
        pdf.set_fill_color(196, 165, 123)  # Light brown/cardboard
        pdf.set_draw_color(0, 0, 0)  # BLACK BORDER
        pdf.set_line_width(0.02)
        pdf.rect(content_x, current_y, 3.0, band_height, 'FD')
        pdf.set_xy(content_x + 0.05, current_y + 0.01)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(0, 0, 0)  # BLACK TEXT
        pdf.cell(2.9, band_height - 0.01, dept_band['name'], align='L')
        current_y += band_height
        
        # Band 3: Item Description (CARDBOARD)
        item_desc = sanitize_for_pdf(item_data.get("item_description", "Item Description"))
        pdf.set_xy(content_x, current_y)
        pdf.set_fill_color(196, 165, 123)  # Light brown/cardboard
        pdf.set_draw_color(0, 0, 0)  # BLACK BORDER
        pdf.set_line_width(0.02)
        pdf.rect(content_x, current_y, 3.0, band_height, 'FD')
        pdf.set_xy(content_x + 0.05, current_y + 0.01)
        pdf.set_font("Helvetica", "B", 6)
        pdf.set_text_color(0, 0, 0)  # BLACK TEXT ON CARDBOARD
        pdf.cell(2.9, band_height - 0.01, item_desc, align='L')
        current_y += band_height + 0.05
    
    # Add Directive Action card (in right column, below product details)
    rates = load_read_rates()
    rate_data = rates.get(str(item_id_orig), [])
    recommendation = "N/A"
    rec_color_hex = "#6b7280"
    if rate_data and len(rate_data) > 0:
        avg_perf = get_avg_performance(rate_data)
        trend_status = get_trend_status(rate_data)
        recommendation, rec_color_hex, _ = get_recommendation(avg_perf, trend_status, catalog_gtin, gtin)
    
    # Color mapping - matching what get_recommendation() returns
    color_map = {
        "#16a34a": {  # Green (ACL APPROVED) - matches get_recommendation()
            "fill_bg": (220, 252, 231),     # Very light green background
            "border": (34, 197, 94),         # Bright green border
            "text": (34, 197, 94)            # Bright vibrant green text
        },
        "#eab308": {  # Amber (ADEQUATE/REQUIRES MANUAL)
            "fill_bg": (254, 243, 199),     # Light amber background
            "border": (245, 158, 11),        # Bright amber border
            "text": (245, 158, 11)           # Bright amber text
        },
        "#dc2626": {  # Red (WORKSTATION RECOMMENDED)
            "fill_bg": (254, 226, 226),     # Light red background
            "border": (220, 38, 38),         # Bright red border
            "text": (220, 38, 38)            # Bright red text
        },
        "#6b7280": {  # Gray (default)
            "fill_bg": (243, 244, 246),     # Light gray background
            "border": (107, 114, 128),       # Medium gray border
            "text": (107, 114, 128)          # Gray text
        }
    }
    
    colors = color_map.get(rec_color_hex, color_map["#6b7280"])
    print(f"[PDF] rec_color_hex={rec_color_hex}, using colors: {colors}")
    
    # Draw directive action box with colored background - matching web page
    pdf.set_xy(content_x, current_y)
    pdf.set_fill_color(colors["fill_bg"][0], colors["fill_bg"][1], colors["fill_bg"][2])
    pdf.set_draw_color(colors["border"][0], colors["border"][1], colors["border"][2])
    pdf.set_line_width(0.05)  # Thicker border
    pdf.rect(content_x, current_y, 6.5, 0.7, style='FD')
    
    # No title - just the action
    
    # Recommendation text - LARGE and BOLD, centered in box
    pdf.set_xy(content_x + 0.1, current_y + 0.15)
    pdf.set_font("Helvetica", "B", 16)  # Large bold text
    pdf.set_text_color(colors["text"][0], colors["text"][1], colors["text"][2])
    pdf.cell(6.3, 0.35, recommendation, align='C')
    
    current_y = current_y + 0.8
    
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
