# TESTING & VERIFICATION GUIDE

## Quick Start
```bash
cd CodePuppyDAR
# If server is running, restart it:
# Ctrl+C to stop
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Test 1: Performance Improvement (CRITICAL)
```
http://localhost:8000/delivery-analysis

1. Enter delivery number: 10863066 (or any you have)
2. Click Search
3. Watch the spinner
4. EXPECTED: Page loads in <5 seconds (was 248s+ before!)
5. Check browser console (F12):
   - Look for [ANALYZE] Analysis complete logs
   - Time should be 2-4 seconds for analysis phase
```

## Test 2: PDF Caching Works
```
Same delivery number: 10863066

1. Click Batch PDF (Problematic Only)
   - FIRST TIME: ~10-15 seconds (full analysis + MDM fetch)
   - Watch logs: [PDF-CACHE-MISS] Running full analysis
   
2. Click PDF button again (same page)
   - SECOND TIME: <3 seconds (cache hit!)
   - Watch logs: [PDF-CACHE-HIT] Using cached PDF
   
3. Verify PDF contains:
   - Summary page at top
   - Priority-ranked problematic items
   - Table showing: Rank | Item Name | MDS | Perf % | Qty | Bad Cases
   - Items sorted by WORST FIRST (highest risk first)
```

## Test 3: Priority Ranking
```
Check the PDF table order:

Should see:
- Item with lowest performance + highest qty at RANK 1
- Items with better performance further down

Example:
Rank 1: Item A, 20% perf, 500 qty = 400 bad cases (HIGH PRIORITY)
Rank 2: Item B, 60% perf, 300 qty = 120 bad cases (lower)
```

## Test 4: Table Removed
```
http://localhost:8000/delivery-analysis
Enter delivery number and search

1. Scroll down on the results page
2. You should see:
   - Summary cards (Good/Bad estimates)
   - Problematic items cards (with images/details)
   - NO big 600+ row table anymore!
3. Page should load faster visually
```

## Test 5: No Errors
```
Browser Console (F12):
- No red errors
- Should see logs like:
  [DELIVERY-ANALYSIS] [QUERY] ...
  [DELIVERY-ANALYSIS] [BATCH] ...
  [DELIVERY-ANALYSIS] [ANALYZE] Analysis complete: X problematic, Y approved
  
Server Console:
- No Python tracebacks
- Should see:
  [PDF-CACHE-HIT] or [PDF-CACHE-MISS]
  [PDF] Generated in X.XXs
```

## Expected Results Summary

### Before Optimization
- Analysis: 248+ seconds
- PDF generation: 15+ seconds every time
- Page cluttered with giant table
- No priority ranking

### After Optimization  
- Analysis: 2-5 seconds (50-100x faster!)
- PDF first time: 10-15s (full analysis)
- PDF cached: <3 seconds (instant!)
- Clean summary cards only
- Items ranked by risk (worst first)

---

## If Something Goes Wrong

### Issue: TypeError: stat: path should be string...
- This is FIXED now! If you see it, run: git pull and restart

### Issue: Analysis still slow (>30 seconds)
- Check: Is read_rates.db file at L:\Engineering\DAR Docktag Cards\read_rates.db?
- Check: Is Informix connection working? Look for [QUERY] errors in console

### Issue: PDF does not download
- Check browser console for network errors (F12 Network tab)
- Check server console for [PDF-ERROR] messages
- Try refreshing page and clicking PDF again

### Issue: PDF appears but items are not priority sorted
- This shouldn't happen, but check: PDF was generated after commit dc81989
- Run: git log --oneline to see recent commits

---

## Performance Metrics to Monitor

After restart, test with delivery #10863066:
```
BEFORE (old code):
  [DELIVER-ANALYSIS] [ANALYZE] Analysis complete... (elapsed: 247.95s)
  
AFTER (new code):
  [DELIVERY-ANALYSIS] [ANALYZE] Analysis complete... (elapsed: 2-5s)
```

Look for this improvement in server logs!

---

## Questions?

If anything looks wrong:
1. Check git status: cd CodePuppyDAR && git log -1
2. Should show commit: Fix PDF endpoint, remove table, optimize...
3. If not, pull latest: git pull origin main
4. Restart server

---

Last Updated: 2026-07-15
Status: Ready for production testing
