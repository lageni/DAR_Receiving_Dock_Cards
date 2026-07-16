# ACL Freight Awareness - CLIENT VIEWER

**Port:** 8001  
**Mode:** Read-Only Display  
**Start:** `RUN_CLIENT.bat`

---

## OVERVIEW

The client is a lightweight viewer that:
- **Calls ABIA API directly** to get active deliveries (same endpoint as server)
- **Checks server's analysis cache** to see which deliveries have been analyzed
- Displays deliveries with color-coded status (analyzed vs pending)
- Auto-refreshes every 30 seconds
- Zero database load
- Multiple users can run simultaneously

---

## QUICK START

### Prerequisites
Server must be running (port 8000) to populate cache

### Start Client
```bash
cd CodePuppyDAR
RUN_CLIENT.bat
```

**Expected startup:**
```
[CLIENT] Starting ACL Viewer Client on port 8001...
[CLIENT] Reading from cache: L:\Engineering\DAR Docktag Cards\cache_data
[CLIENT] Open browser: http://localhost:8001
INFO: Uvicorn running on http://0.0.0.0:8001
```

### Open Browser
```
http://localhost:8001
```

---

## FEATURES

### Auto-Refresh
- Refreshes cache data every 30 seconds
- Visual countdown timer
- No manual refresh needed

### Multi-Tab View
- **ACL 1** - Active deliveries on ACL 1
- **ACL 2** - Active deliveries on ACL 2
- **ACL 3** - Active deliveries on ACL 3

### Color-Coded Cards
- **Gray** - Pending analysis (server hasn't analyzed yet)
- **Green** - 0 problematic items (all good)
- **Yellow** - 1-4 problematic items (minor issues)
- **Red** - 5+ problematic items (attention needed)

### Card Information
Each delivery card shows:
- Delivery number
- Station
- Problematic item count
- Top 5 problematic items with performance %
- Link to full analysis (opens server)

## HOW IT WORKS

### Step 1: Fetch Active Deliveries
Client calls ABIA API directly:
```
https://abia.wal-mart.com/aclaware/fetchData/?dc=6068&acl=acl1
```

### Step 2: Check Analysis Status
For each delivery from ABIA, client checks if server has analyzed it:
```python
cache_key = f"analysis_{delivery_number}"
cached_analysis = cache.get(cache_key)
```

### Step 3: Display Results
- **Analyzed deliveries:** Show problematic items, performance scores (green/yellow/red)
- **Pending deliveries:** Show gray "Pending Analysis" status

### Step 4: Auto-Refresh
- Every 30 seconds, repeat steps 1-3
- Get fresh ABIA data
- Check for new analysis results

### Main Page
- `GET /` - ACL viewer with tabs

### API
- `GET /api/cache/{acl}` - Get cached ACL data (JSON)
- `GET /health` - Health check

---

## CACHE READING

### What Client Checks
For each delivery from ABIA, client checks:
```
L:\Engineering\DAR Docktag Cards\cache_data\deliveries\
analysis_{delivery_number}.json
```

### Cache Structure (Written by Server)
```json
{
  "problematic_mds_ids": ["12345", "67890"],
  "problematic_details": {
    "12345": {
      "avg_perf": 62.5,
      "item_qty": 200,
      "bad_cases": 75
    }
  },
  "problematic_items_data": [
    {
      "mds_fam_id": "12345",
      "item_name": "Widget",
      "acl_details": {...}
    }
  ],
  "approved_count": 420
}
```

### Client Logic
```python
# 1. Get deliveries from ABIA
deliveries = fetch_from_abia()

# 2. For each delivery, check if analyzed
for delivery in deliveries:
    analysis = cache.get(f"analysis_{delivery.number}")
    if analysis:
        # Show problematic items
        display_analyzed(delivery, analysis)
    else:
        # Show "Pending Analysis"
        display_pending(delivery)
```

---

## TYPICAL WORKFLOW

### Single User
1. Start server (RUN.bat)
2. Wait 2 minutes for initial cache
3. Start client (RUN_CLIENT.bat)
4. Open http://localhost:8001
5. Monitor deliveries in real-time

### Multiple Viewers
1. **One person** starts server (RUN.bat)
2. **Multiple people** start client (RUN_CLIENT.bat on their machines)
3. All clients read from same L: drive cache
4. Zero load on server from viewers

### Click for Details
1. Monitor deliveries on client (port 8001)
2. See problematic delivery
3. Click "Full Analysis" button
4. Opens server (port 8000) for detailed analysis
5. Generate PDF reports, view charts, etc.

---

## TROUBLESHOOTING

### Seeing gray "Pending Analysis" cards
**Cause:** Server hasn't analyzed those deliveries yet  
**This is normal!** Server analyzes deliveries in background  
**Wait time:** Usually 2-5 seconds per delivery  
**Action:** 
- Click "Analyze Now" to trigger analysis on server
- Or wait for server background worker to analyze it

### "Cannot read cache" error
**Cause:** Cannot access L: drive or cache directory  
**Fix:**
- Verify path exists: `L:\Engineering\DAR Docktag Cards\cache_data\deliveries\`
- Check file permissions
- Ensure you're on VPN (if L: drive is network)

### Old data showing
**Cause:** Server stopped or crashed  
**Fix:** Restart server (RUN.bat)  
**Check:** Last update timestamp in client UI

### Client won't start
**Cause:** Port 8001 already in use  
**Fix:**
- Check if another client is running
- Use different terminal window
- Kill process using port 8001

### Slow refresh
**Normal:** Client refreshes every 30 seconds  
**If slower:** Check network connection to L: drive

---

## MULTIPLE CLIENTS

### Same Machine
**Use separate terminals:**
```bash
# Terminal 1
RUN.bat          # Server on port 8000

# Terminal 2
RUN_CLIENT.bat   # Client on port 8001
```

### Different Machines
**All machines must:**
- Have access to L: drive
- Have Python + deies installed
- Run `RUN_CLIENT.bat`
- Open browser to `http://localhost:8001`

**Server only runs once** (on one machine)

---

## PERFORMANCE

### Client Load
- **Startup:** <1 second
- **Memory:** ~50 MB
- **CPU:** <1% (idle)
- **Network:** Reads local cache (L: drive)

### Refresh Performance
- **Cache read:** <0.1 seconds
- **JSON parse:** <0.01 seconds
- **Total:** Instant!

### Scalability
- **Users:** Unlimited (reads only)
- **Impact on server:** Zero
- **Impact on database:** Zero

---

## DISPLAY LOGIC

### Card Colors
```python
if problematic_count == 0:
    color = GREEN  # All items performing well
elif problematic_count < 5:
    color = YELLOW  # Minor issues
else:
    color = RED  # Needs attention
```

### Performance Colors
```python
if performance < 50:
    color = RED  # Failing
elif performance < 70:
    color = YELLOW  # Warning
else:
    color = ORANGE  # Adequate
```

### Item Limit
- Shows top 5 problematic items per delivery
- "+X more" indicator if more items exist
- Click "Full Analysis" for complete list

---

## FILES

### Application
- `client_viewer.py` - FastAPI client app (300 lines)
- `cache_manager.py` - Shared cache reader

### Startup
- `RUN_CLIENT.bat` - Client startup script

### Dependencies
Same as server:
- `fastapi`
- `uvicorn`
- `cache_manager` (shared module)

---

## ARCHITECTURE

```
┌───────────────────────────────────────────────┐
│         CLIENT VIEWER (Port 8001)             │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  Browser (http://localhost:8001)        │  │
│  │  - Tabbed interface (ACL1/2/3)          │  │
│  │  - Auto-refresh every 30s               │  │
│  │  - Color-coded delivery cards           │  │
│  └─────────────────────────────────────────┘  │
│                     ▲                         │
│                     │ HTTP                    │
│                     ▼                         │
│  ┌─────────────────────────────────────────┐  │
│  │  FastAPI App (client_viewer.py)         │  │
│  │  - GET /                                │  │
│  │  - GET /api/cache/{acl}                 │  │
│  │  - GET /health                          │  │
│  └─────────────────────────────────────────┘  │
│                     │                         │
│                     │ File Read               │
│                     ▼                         │
│  ┌─────────────────────────────────────────┐  │
│  │  Shared Cache (L: Drive)                │  │
│  │  cache_data/acl/*.json                  │  │
│  │  - Written by server                    │  │
│  │  - Read by client                       │  │
│  └─────────────────────────────────────────┘  │
└───────────────────────────────────────────────┘
```

---

## BENEFITS VS SERVER

### Client Advantages
- **Lightweight:** No database, no API calls
- **Fast:** Reads local cache only
- **Scalable:** Multiple users, zero impact
- **Simple:** One file, minimal dependencies
- **Safe:** Read-only, can't corrupt data

### When to Use Client
- Monitoring deliveries
- Quick status checks
- Multiple simultaneous viewers
- No analysis needed

### When to Use Server
- Manual delivery analysis
- Generate PDF reports
- View detailed charts
- Deep dive into items

---

## SECURITY

### Read-Only
Client **cannot**:
- Write to cache
- Modify deliveries
- Run analysis
- Access database
- Call APIs

Client **can only**:
- Read cache files
- Display data
- Link to server

### Network
- Runs on localhost only
- No external connections
- No authentication needed
- Local file access only

---

## MONITORING

### Health Check
```bash
curl http://localhost:8001/health
```

**Response:**
```json
{
  "status": "healthy",
  "mode": "client",
  "port": 8001,
  "cache_accessible": true,
  "cache_path": "L:\\Engineering\\DAR Docktag Cards\\cache_data"
}
```

### Good Logs
```
[CLIENT] Serving 15 deliveries for acl1 from cache
[CLIENT] Serving 8 deliveries for acl2 from cache
[CLIENT] Serving 22 deliveries for acl3 from cache
```

### Warning Logs
```
[CLIENT] No cache found for acl1
```
**Action:** Wait for server to write cache

---

## MAINTENANCE

### Restart Client
```bash
# Stop (Ctrl+C in terminal)
# Restart
RUN_CLIENT.bat
```

### Clear Browser Cache
- Force refresh: `Ctrl + Shift + R`
- Clear cookies: Not needed (stateless)

### Update Client
```bash
git pull
# Restart client
RUN_CLIENT.bat
```

---

## FAQ

**Q: Can I run multiple clients on one machine?**  
A: No, port 8001 can only be used once. Use different machines.

**Q: Does the client work without server?**  
A: Yes, if cache files exist. But cache won't update without server.

**Q: How often does client refresh?**  
A: Every 30 seconds automatically.

**Q: Can I change the refresh interval?**  
A: Yes, edit `client_viewer.py` line with `setInterval(..., 30000)` (milliseconds)

**Q: Where's the server?**  
A: Server runs on port 8000. Link: http://localhost:8000

**Q: Why is client faster than server?**  
A: Client only reads files. Server does analysis, database queries, API calls.

**Q: Can I customize the UI?**  
A: Yes, edit HTML template in `client_viewer.py` (Tailwind CSS)

---

Last Updated: 2026-07-15  
Version: 1.0 (Client/Server Architecture)  
Status: Production Ready
