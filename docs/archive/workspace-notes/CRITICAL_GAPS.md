# DELIVERY ANALYSIS - CRITICAL GAPS IDENTIFIED

## The Gap Between Web & PDF

### Web Page Shows:
- 2 problematic items (47.2% FAILING, 84.0% status)
- 64 ACL APPROVED items
- Full charts for each problematic item

### PDF Shows:
- 0 problematic items
- 66 ACL APPROVED
- Just a table, no item details

**Root Cause:** PDF uses different ACL status logic than web page

---

## What's Needed (Priority Order)

### 1. CRITICAL: Fix PDF ACL Logic (BROKEN)
**Current:** PDF says 0 problematic, web says 2
**Need:** Use SAME logic in PDF as web page

**Web Logic:**
```python
if avg_perf >= 85:
    is_problematic = False
elif avg_perf < 50:
    is_problematic = True  # FAILING
elif "Improving" in trend:
    is_problematic = True  # ADEQUATE
else:
    is_problematic = True  # REQUIRES MANUAL INSPECTION
```

**PDF Logic:** Currently doesn't exist - just tables

---

### 2. CRITICAL: Batch PDF = Full Batch Report
**Current:** Just a table
**Need:** Full item detail cards like batch feature:
- Product image
- Item dimensions (length, width, height)
- Pack type, dept, vendor
- Read rate performance chart
- ACL status badge
- One card per problematic item

**Example (from screenshot):**
```
[Item Card]
├─ Product Image
├─ Item details (GTIN, dimensions, pack type, etc.)
├─ ACL Performance % badge
└─ Chart showing read rate trend
```

---

### 3. Individual PDF Download Buttons
**Current:** No button on each card
**Need:** "Download PDF" button on each problematic item card
- Downloads single-item detailed report
- Includes image, dimensions, chart, ACL status

---

### 4. Product Images
**Current:** Not fetched or displayed
**Need:** 
- Fetch from MDM API using item_id
- Display on web cards
- Include in PDF printouts

**Question:** How do we map mds_fam_id to item_id for MDM lookup?

---

### 5. Add "No History Cases" to Summary
**Current:** Shows count of no history items
**Need:** Also show TOTAL QUANTITY for those items
- Example: "3 No History Items, 45 Cases"

---

## Current Issues

| Feature | Web | PDF | Status |
|---------|-----|-----|--------|
| ACL Logic | Correct (2 problematic) | Wrong (0 problematic) | BROKEN |
| Item Details |  Shows chart |  Table only | INCOMPLETE |
| Images |  Not fetched |  Not included | MISSING |
| Individual PDF |  No button | N/A | MISSING |
| No History Cases |  Count |  No quantity | INCOMPLETE |

---

## What I Didn't Realize

The batch PDF should be the FULL BATCH REPORT with complete item "printout cards" for each problematic item, not just a data table. This is a significant feature that requires:

1. Item detail fetching (MDM API)
2. Chart generation in PDF
3. Image embedding in PDF
4. Multiple-page PDF with one detailed card per item

---

## To Move Forward, I Need:

1. **Clarification on images:**
   - How do we get item_id from mds_fam_id?
   - Should I query MDM API?
   - Any sample item_id we can test with?

2. **Confirm design:**
   - Should PDF be: Summary + Problematic Items (detailed) + All PO Lines (table)?
   - Page count: ~2-3 pages total?
   - Include charts in PDF (yes/no)?

3. **Individual PDF scope:**
   - One problematic item per page?
   - Include PO lines for that item?

---

## Status

The feature is **INCOMPLETE** because:
- PDF logic doesn't match web display
- PDF lacks full item details  
- No product images
- No individual export per item
- Missing no-history quantity metric

I sincerely apologize for not building this correctly from the start. I should have made the PDF a full batch report from the beginning.

Ready to rebuild this properly once you clarify the item_id mapping and design preferences.
