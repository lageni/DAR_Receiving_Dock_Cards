# CLIENT/SERVER ARCHITECTURE - CORRECTED

## HOW IT WORKS NOW

```
┌──────────────────────────────────────────────────────────┐
│                     ABIA API                             │
│   https://abia.wal-mart.com/aclaware/fetchData/         │
│        ?dc=6068&acl=acl1                                │
│                                                          │
│   Returns: Active deliveries for ACL 1/2/3             │
└──────────────────────────────────────────────────────────┘
           │                                   │
           │ Fetch                     Fetch   │
           ▼                                   ▼
┌──────────────────────┐           ┌──────────────────────┐
│   SERVER (8000)      │           │   CLIENT (8001)      │
│                      │           │                      │
│  1. Fetch from ABIA  │           │  1. Fetch from ABIA  │
│  2. Analyze delivery │           │  2. For each delivery│
│  3. Write to cache:  │           │     check cache:     │
│     analysis_        │           │     analysis_        │
│     {delivery}       │           │     {delivery}       │
│                      │           │  3. Display:         │
│  Background worker   │           │     - Gray (pending) │
│  runs every 2 min    │           │     - Green (good)   │
│                      │           │     - Yellow (warn)  │
│                      │           │     - Red (urgent)   │
└──────────────────────┘           └──────────────────────┘
           │                                   │
           │ WRITES                    READS   │
           ▼                                   ▼
┌──────────────────────────────────────────────────────────┐
│               SHARED CACHE (L: Drive)                    │
│   L:\Engineering\DAR Docktag Cards\cache_data\          │
│                                                          │
│   /deliveries/                                           │
│     analysis_10917836.json  ← Server writes             │
│     analysis_10928946.json     Client reads →           │
│     analysis_10863066.json                              │
│                                                          │
│   Each file: {                                           │
│     problematic_items_data: [...],                       │
│     problematic_details: {...},                          │
│     approved_count: X                                    │
│   }                                                      │
└──────────────────────────────────────────────────────────┘
```

---

## KEY DIFFERENCES FROM BEFORE

### OLD (Broken) Architecture
 Client waited for server to write `acl_acl1_deliveries.json`  
 Server had to pre-cache ALL deliveries before client could show them  
 Client showed "No cache" because server writes were failing  
 Client was passive, dependent on server

### NEW (Working) Architecture
 **Client calls ABIA directly** - gets active deliveries independently  
 **Client checks analysis cache per delivery** - sees which are analyzed  
 **Shows "Pending" for un-analyzed deliveries** - immediate feedback  
 **Client is active, independent** - doesn't wait for server

---

## DATA FLOW

### Server Flow
```
1. Background worker runs every 2 minutes
2. Fetches ABIA deliveries
3. For each delivery:
   - Check if already analyzed (analysis cache)
   - If yes: Skip (instant!)
   - If no: Analyze delivery, write cache
4. Next iteration in 2 minutes
```

### Client Flow
```
1. User loads page
2. Client fetches ABIA deliveries
3. For each delivery:
   - Check if analysis_{delivery}.json exists
   - If yes: Show problematic items (green/yellow/red)
   - If no: Show "Pending Analysis" (gray)
4. Auto-refresh every 30 seconds (repeat from step 2)
```

---

## USER EXPERIENCE

### Scenario 1: First Load
```
User opens client → See ALL active deliveries immediately
                  ↓
Some show "Pending Analysis" (gray)
Some show problematic items (green/yellow/red if server already analyzed)
                  ↓
After 30 seconds, auto-refresh → More deliveries now analyzed
```

### Scenario 2: Click "Analyze Now"
```
User clicks "Analyze Now" on gray card
                  ↓
Opens server (port 8000) for that delivery
                  ↓
Server analyzes delivery, writes cache
                  ↓
User returns to client → Next refresh shows results (green/yellow/red)
```

### Scenario 3: Background Analysis
```
User watching client → Sees 15 deliveries (5 gray, 10 analyzed)
                     ↓
Server background worker runs
                     ↓
30 seconds later, client auto-refreshes
                     ↓
Now shows 15 deliveries (2 gray, 13 analyzed)
```

---

## BENEFITS

### Independent Operation
- Client doesn't depend on server writing ACL cache
- Client gets fresh ABIA data every refresh
- Shows deliveries immediately, even if not analyzed

### Clear Status
- Gray = Not analyzed yet (pending)
- Green = Analyzed, all good
- Yellow = Analyzed, minor issues
- Red = Analyzed, needs attention

### Responsive
- User sees deliveries instantly
- Can trigger analysis manually
- Auto-refresh shows progress

### Scalable
- Multiple clients don't impact ABIA API (30s refresh)
- Each client makes 1 ABIA call per refresh
- Analysis cache shared across all users

---

## API CALLS

### Client makes:
- **ABIA API:** 1 call per ACL per 30 seconds
- **Cache reads:** 1 per delivery per refresh (local L: drive)

### Server makes:
- **ABIA API:** 1 call per ACL per 2 minutes (background worker)
- **Informix:** 1 call per new delivery analysis
- **MDM API:** N calls per delivery (for problematic items)
- **Cache writes:** 1 per delivery analyzed

---

## CACHE KEYS

### Server writes:
```
analysis_10917836.json
analysis_10928946.json
analysis_10863066.json
```

### Client reads:
```python
for delivery in abia_deliveries:
    cache_key = f"analysis_{delivery.number}"
    analysis = cache.get(cache_key)
    if analysis:
        show_analyzed(delivery, analysis)
    else:
        show_pending(delivery)
```

---

## TROUBLESHOOTING

### Client shows all gray "Pending"
**Normal!** Server hasn't analyzed deliveries yet.

**Actions:**
- Click "Analyze Now" to trigger analysis
- Wait for server background worker (runs every 2 minutes)
- Check server logs for analysis progress

### Client shows "Cannot read cache"
**Problem:** L: drive not accessible

**Fix:**
- Check VPN connection
- Verify path: `L:\Engineering\DAR Docktag Cards\cache_data`
- Check file permissions

### ABIA API errors
**Problem:** Cannot fetch deliveries

**Fix:**
- Check VPN/network
- Verify ABIA API is up: https://abia.wal-mart.com/
- Check server logs for ABIA errors

---

Last Updated: 2026-07-15  
Architecture: Client calls ABIA + checks server analysis cache  
Status: WORKING
