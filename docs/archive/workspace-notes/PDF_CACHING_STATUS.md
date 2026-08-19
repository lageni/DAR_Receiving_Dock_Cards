PDF CACHING STATUS - ALMOST DONE

WHAT'S WORKING:
- Web page search (10 seconds initial analysis + MDM + HTML build) 
- Web page caches full HTML response
- Web page caches analysis result (problematic_items_data with MDM)
- Second web search of same delivery: <1 second (instant)

WHAT STILL NEEDS FIXING:
- PDF button click still re-runs full analysis (30+ seconds)
- PDF endpoint doesn't check for cached analysis yet

THE FIX IS SIMPLE:
PDF endpoint just needs to check for cached analysis at startup:

```python
# After line 3568 in main.py:
import time
cache = get_cache_manager()
cached_analysis = cache.get(f"pdf_analysis_{delivery_number}", category="deliveries")

if cached_analysis:
    # Use cached values - skip all the analysis below
    mds_fam_ids = cached_analysis.get('mds_fam_ids', [])
    po_rows = cached_analysis.get('po_rows', [])
    problematic_items_data = cached_analysis.get('problematic_items_data', [])
    # ... then jump to PDF generation (skip analysis sections 1 & 2)
else:
    # Run the current analysis code
    # ... (existing code for analysis and MDM fetching)
```

EXPECTED RESULT AFTER FIX:
1. Web search 10797464:        30-45 seconds (first time, full analysis)
2. Click PDF button:            2-5 seconds (uses cached analysis + MDM)
3. Click PDF button again:      2-5 seconds (uses cache)
4. Web search 10797464 again:   <1 second (HTML cache hit)
5. Click PDF button:            2-5 seconds (analysis cache hit)

CURRENT STATE:
- Web endpoint: DONE (caching working)
- PDF endpoint: NEEDS UPDATE (simple if/else to check cache)

Commit: 5f1880f
Next: Update PDF endpoint to use cached analysis
