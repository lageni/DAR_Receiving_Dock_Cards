# DELIVERY ANALYSIS REBUILD - SYSTEMATIC APPROACH

## Core Problem
Currently:
- Web shows problematic items but fetches NO MDM data
- PDF shows different results (0 problematic vs 2 on web)
- No images on web or PDF
- No individual PDF buttons

## Solution: Copy Batch Pattern Exactly

### Step 1: Fetch MDM Data for Problematic Items
After identifying `problematic_mds_ids`, fetch MDM data:
```python
async def fetch_problematic_items_mdm(problematic_mds_ids):
    # FOR EACH mds_id IN problematic_mds_ids:
    #   - Call MDM API: /items/wm/{mds_id}
    #   - Call extract_item_data(response)
    #   - Add mds_fam_id to item_data
    # RETURN items_data list
```

### Step 2: Display Images on Web Cards
Replace simple card with:
```html
<div class="card">
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <!-- LEFT: Product Image -->
    <div>
      <img src="{item_data['image_url']}" />
    </div>
    <!-- CENTER: Item Details -->
    <div>
      Name, GTIN, Dimensions, Pack type, Vendor info
    </div>
    <!-- RIGHT: ACL Status + Chart -->
    <div>
      Status, Trend, Performance %, Chart, PDF Button
    </div>
  </div>
</div>
```

### Step 3: Add PDF Button to Each Card
```html
<a href="/api/delivery-analysis/pdf-item?mds_id={mds_id}" 
   class="btn">Download PDF</a>
```

### Step 4: Use Existing generate_batch_pdf()
For batch PDF, collect all problematic items_data and call:
```python
pdf_bytes = generate_batch_pdf(items_data)
```
This already handles images, charts, ACL status - just like batch feature!

### Step 5: New Endpoint for Single-Item PDF
```python
@app.get("/api/delivery-analysis/pdf-item")
async def delivery_pdf_single_item(mds_id: str):
    # Fetch MDM data for single mds_id
    # Call generate_batch_pdf([item_data])
    # Return PDF bytes
```

### Step 6: Fix ACL Logic in PDF
Use SAME logic in PDF as web page for determining is_problematic

---

## Implementation Checklist

- [ ] Add MDM fetching for problematic items in delivery_analysis_search
- [ ] Update web card display to show images + full details
- [ ] Add individual PDF button to each card
- [ ] Create /api/delivery-analysis/pdf-item endpoint (single item PDF)
- [ ] Update /api/delivery-analysis/pdf endpoint to use generate_batch_pdf()
- [ ] Verify ACL logic matches between web and PDF
- [ ] Test end-to-end

---

## Key Files to Modify

1. **main.py - delivery_analysis_search()**
   - Add MDM fetching loop after problematic items identified
   - Change web card display to include images
   - Add PDF buttons

2. **main.py - delivery_analysis_pdf()**
   - Replace custom PDF logic with `generate_batch_pdf(items_data)`

3. **main.py - NEW delivery_pdf_single_item()**
   - Create endpoint for individual item PDF

---

## No New Concepts
Just copy:
- `extract_item_data()` function (already using)
- `generate_batch_pdf()` function (reuse existing)
- MDM API call pattern (from batch_random)
- Image display pattern (from batch HTML)

All code already exists. Just apply it to delivery analysis.
