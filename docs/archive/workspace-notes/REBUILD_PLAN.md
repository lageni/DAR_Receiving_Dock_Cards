# DELIVERY ANALYSIS - COMPLETE REBUILD PLAN

## What I'm Doing Wrong

I'm treating delivery analysis as separate from batch feature, but it should use THE SAME patterns:

**Batch Feature (Working):**
- Fetches MDM data for each item_id
- Extracts: image, dimensions, pack type, GTIN, etc.
- Displays: Full cards with images
- PDF: Detailed batch report with charts

**Delivery Analysis (Broken):**
- Just shows MDS IDs without fetching MDM
- No images
- PDF is just a table
- Missing all product details

---

## The Fix (Step by Step)

### Step 1: Fetch MDM Data for Each Problematic Item
For each problematic mds_fam_id, call MDM API using it as item_id:
```python
api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{mds_fam_id}/?xrefItemInfo=false"
# Headers: Api-Key, Facilitynum, Facilitycountrycode, Wmt-Userid
response = await client.get(api_url, headers=headers)
item_data = extract_item_data(response.json())
```

### Step 2: Display Images on Web Cards
Add `{item_data['image_url']}` to problematic item cards

### Step 3: Show All Product Details on Cards
- Image (top)
- Item name, GTIN, pack type
- Dimensions (length x width x height)
- Vendor stock info
- Chart below

### Step 4: Add Individual PDF Button
Each problematic item card gets a "Download PDF" button that downloads a single-item detailed report

### Step 5: Rebuild Batch PDF
Instead of just a table, create FULL batch report with:
- Page 1: Summary
- Pages 2+: One detailed card per problematic item (like batch feature shows)
- Each card includes: image, details, chart, ACL status
- Final pages: PO lines table

### Step 6: Fix ACL Status Logic in PDF
PDF currently shows different results than web page - use SAME logic in both

---

## Code Pattern to Copy

From batch_random (line 2172):
```python
# Fetch MDM data
api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{item_id}/?xrefItemInfo=false"
response = await client.get(api_url, headers=headers)
mdm_data = response.json()
item_data = extract_item_data(mdm_data)

# Use item_data:
# - item_data['image_url'] -> Image
# - item_data['vnpk_length/width/height'] -> Dimensions
# - item_data['casepack_type'] -> Pack type
# - item_data['item_name'] -> Item name
# - etc.
```

---

## What I Need to Change

### main.py - Delivery Analysis Cards Section
Replace the simple MDS ID display with:
1. Fetch MDM data for each problematic mds_fam_id
2. Call extract_item_data()
3. Add image to card
4. Add all item details
5. Add "Download PDF" button for single item

### main.py - Batch PDF Endpoint
Replace table-only PDF with:
1. Fetch MDM data for each problematic item
2. Create detailed cards in PDF (like batch feature does)
3. Include images (via base64 embedding)
4. Include charts
5. Use SAME ACL logic as web page

### main.py - New Endpoint for Single-Item PDF
`/api/delivery-analysis/pdf-single?mds_fam_id=XXXXX` that returns a PDF for just one item

---

## Implementation Order

1. Fix ACL status logic (make PDF match web)
2. Add MDM fetching to problematic item cards (web display)
3. Add individual PDF button + endpoint
4. Rebuild batch PDF to be full batch report
5. Test everything end-to-end

---

## Key Insight

The delivery analysis should work EXACTLY like batch feature:
- Same MDM API calls
- Same extract_item_data() function
- Same image display
- Same PDF generation
- Just filtered to show only problematic items

I was overcomplicating it. Just copy the pattern!

Ready to implement once you confirm:
1. Use mds_fam_id as the item_id to query MDM? (or is there another mapping?)
2. Include images in PDF (base64 encoded)?
3. Individual PDF for each item when clicked?
