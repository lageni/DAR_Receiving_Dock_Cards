# ACL Freight Awareness - Client/Server Architecture

## ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                     SHARED CACHE                             │
│         L:\Engineering\DAR Docktag Cards\cache_data         │
│                                                              │
│  Structure:                                                  │
│    /acl/                                                     │
│      acl_acl1_deliveries.json                               │
│      acl_acl2_deliveries.json                               │
│      acl_acl3_deliveries.json                               │
└─────────────────────────────────────────────────────────────┘
           ▲                                   │
           │ WRITES                    READS   │
           │                                   ▼
┌──────────────────────┐           ┌──────────────────────┐
│   SERVER (8000)      │           │   CLIENT (8001)      │
│   main.py            │           │   client_viewer.py   │
│                      │           │                      │
│  - Analyzes          │           │  - Reads cache only  │
│  - Writes cache      │           │  - Displays data     │
│  - Background worker │           │  - Auto-refresh 30s  │
│  - Heavy processing  │           │  - No processing     │
│                      │           │  - Multiple users OK │
└──────────────────────┘           └──────────────────────┘
```

## HOW TO USE

### 1. START SERVER (Analyzes & Caches)

```bash
RUN.bat
```

- Port: 8000
- Role: Analyzes deliveries, writes to cache
- Background: Updates cache every 2 minutes
- Use for: Delivery analysis, PDF generation

### 2. START CLIENT (Displays Cached Data)

```bash
RUN_CLIENT.bat
```

- Port: 8001
- Role: Reads cache, displays to users
- Refresh: Auto-refresh every 30 seconds
- Use for: Real-time monitoring, multiple viewers

### 3. OPEN IN BROWSER

**Client (Recommended for viewing):**
```
http://localhost:8001
```

**Server (For analysis):**
```
http://localhost:8000
```

---

## BENEFITS

### Server Focus
- Runs heavy analysis in background
- Writes results to disk cache
- No user load impact
- Single source of truth

### Client Benefits
- Lightweight (only reads cache)
- Fast startup (<1 second)
- Multiple users can run clients
- No database/API load
- Auto-refresh without server impact

### Shared Cache
- File-based on L: drive
- Readable by both apps
- Persists across restarts
- 2-day TTL (auto-cleanup)

---

## CACHE STRUCTURE

**File:** `L:\Engineering\DAR Docktag Cards\cache_data\acl\acl_acl1_deliveries.json`

```json
{
  "deliveries": [
    {
      "delivery_number": "10917836",
      "station": "A1",
      "problematic_count": 5,
      "problematic_items": [
        {
          "mds_fam_id": "12345678",
          "item_name": "Widget",
          "performance": 62.5
        }
      ]
    }
  ],
  "last_update": "2026-07-15T16:30:00",
  "status": "ready"
}
```

---

## TYPICAL WORKFLOW

### Scenario 1: Single User
1. Start SERVER (RUN.bat)
2. Wait 2 minutes for initial cache
3. Start CLIENT (RUN_CLIENT.bat)
4. Open http://localhost:8001

### Scenario 2: Multiple Viewers
1. Start SERVER on one machine (RUN.bat)
2. Multiple users start CLIENT on their machines (RUN_CLIENT.bat)
3. All clients read from same L: drive cache
4. Zero load on server from viewers

### Scenario 3: Analysis + Viewing
1. Use CLIENT (8001) for monitoring
2. Click "Full Analysis" button to jump to SERVER (8000)
3. Server analyzes, updates cache
4. Client auto-refreshes with new data

---

## TROUBLESHOOTING

### Client shows "No cache"
- **Cause:** Server hasn't written cache yet
- **Fix:** Wait 2 minutes after starting server

### Client shows old data
- **Cause:** Server stopped or cache expired
- **Fix:** Restart server (RUN.bat)

### Both apps on same machine
- **Use different terminals:**
  - Terminal 1: `RUN.bat` (server)
  - Terminal 2: `RUN_CLIENT.bat` (client)

### Cache not updating
- **Check server logs:** Look for `[ACL-WORKER] Wrote X deliveries to disk cache`
- **Check cache folder:** `L:\Engineering\DAR Docktag Cards\cache_data\acl\`

---

## FILES

### Server Files
- `main.py` - Main server app
- `acl_background_worker.py` - Cache writer
- `RUN.bat` - Start server

### Client Files
- `client_viewer.py` - Client app
- `RUN_CLIENT.bat` - Start client

### Shared
- `cache_manager.py` - Cache read/write

---

Last Updated: 2026-07-15
Architecture: Client/Server with Shared File Cache
