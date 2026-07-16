# ACL Freight Awareness - SERVER

**Port:** 8000  
**Mode:** Analysis & Cache Writer  
**Start:** `RUN.bat`

---

## OVERVIEW

The server is the analysis engine that:
- Fetches active deliveries from ABIA API
- Analyzes delivery performance (ACL status, read rates)
- Writes results to shared cache every 2 minutes
- Provides delivery analysis tools and PDF generation

---

## QUICK START

```bash
cd CodePuppyDAR
RUN.bat
```

**Expected startup:**
```
[STARTUP] ACL monitor running in background
INFO: Uvicorn running on http://0.0.0.0:8000
[ACL-WORKER] Background analysis starting...
```

**Server is ready when you see:**
```
[ACL-WORKER] Starting monitoring cycle at HH:MM:SS
```

---

## ENDPOINTS

### ACL Monitoring
- `GET /` - Redirects to ACL1
- `GET /acl1`, `/acl2`, `/acl3` - ACL grid views
- Internal background worker updates every 2 minutes

### Delivery Analysis
- `GET /delivery-analysis` - Manual delivery search
- `GET /api/delivery-analysis/search?delivery_number=X` - Analyze delivery
- `GET /api/delivery-analysis/pdf?delivery_number=X` - Generate PDF report

### Item Analysis
- `GET /item-analysis` - Item search tool

---

## BACKGROUND WORKER

**File:** `acl_background_worker.py`

**What it does:**
1. Every 2 minutes, fetches deliveries from ABIA API for ACL1/2/3
2. For each delivery:
   - Checks analysis cache first (instant if cached!)
   - If not cached, runs full analysis (SQL-optimized)
   - Analyzes problematic items (performance < 85%)
3. Writes results to shared cache for client viewer

**Cache output:**
```
L:\Engineering\DAR Docktag Cards\cache_data\acl\
  acl_acl1_deliveries.json
  acl_acl2_deliveries.json
  acl_acl3_deliveries.json
```

---

## OPTIMIZATIONS (COMPLETE)

### 1. SQL Pre-Filtering
**Problem:** Loading all 131k items from read_rates.db  
**Fix:** SQL WHERE IN clause loads only needed items  
**Result:** 100-1000x faster queries

### 2. Problematic Items Pre-Filter
**Problem:** Loading items one-by-one, then filtering  
**Fix:** SQL CTE pre-filters performance < 85% at database level  
**Result:** Only loads problematic items, skips ACL-approved

### 3. Analysis Caching
**Problem:** Re-analyzing same delivery multiple times  
**Fix:** Cache key `analysis_{delivery_number}` with 2-day TTL  
**Result:** Second analysis is instant (0 API calls)

### 4. O(n²) Loop Eliminated
**Problem:** Nested loop scanning 441×441 items  
**Fix:** Pre-built lookup dict for O(1) access  
**Result:** 248 seconds → 2-5 seconds (50-100x faster!)

### 5. Non-Blocking Startup
**Problem:** Server blocked during initial ACL analysis  
**Fix:** Worker runs in background, server ready immediately  
**Result:** Startup in <1 second

---

## CACHE STRUCTURE

### Analysis Cache
**Key:** `analysis_{delivery_number}`  
**Location:** `cache_data/deliveries/`  
**TTL:** 2 days  
**Contents:**
```json
{
  "problematic_mds_ids": ["12345", "67890"],
  "problematic_details": {
    "12345": {
      "avg_perf": 62.5,
      "item_qty": 200,
      "bad_cases": 75,
      "priority_score": 2812.5
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

### ACL Cache (for Client)
**Key:** `acl_{acl}_deliveries`  
**Location:** `cache_data/acl/`  
**TTL:** 2 days  
**Contents:**
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

### PDF Cache
**Key:** `pdf_summary_{delivery_number}`  
**Location:** `cache_data/deliveries/`  
**TTL:** 2 days  
**Contents:** PDF bytes with priority-ranked summary

---

## CONFIGURATION

### Environment Variables
**File:** `.env`

```env
MDM_API_KEY=your_key
MDM_FACILITY_NUM=6068
MDM_FACILITY_COUNTRY_CODE=US
MDM_WMT_USERID=mdm-ui
DATABASE_PATH=L:\Engineering\DAR Docktag Cards\read_rates.db
```

### Cache Settings
**File:** `cache_manager.py`

- Cache directory: `L:\Engineering\DAR Docktag Cards\cache_data`
- Default TTL: 2 days
- Auto-cleanup: Expired files removed on access

---

## MONITORING

### Good Logs
```
[ACL-WORKER] Starting monitoring cycle at 16:42:15
[ACL-WORKER] ACL1: Fetched 15 active deliveries
[ACL-WORKER] Delivery 10917836: Using CACHED analysis (instant!)
[OPTIMIZED] Loaded 20 items (queried only 20 from DB)
[SQL-optimized: Loaded 20 problematic items in 2.5s]
[ACL-WORKER] ACL1: Wrote 15 deliveries to disk cache for client
```

### Debug Logs (if enabled)
```
[ANALYSIS-CACHE-HIT] Using cached analysis for delivery 10917836
[PDF-CACHE-HIT] Using cached PDF
[ACL-WORKER-DEBUG] get_acl_data(acl1): Returning 15 deliveries
```

---

## TROUBLESHOOTING

### Server won't start
**Check:**
- Port 8000 not already in use
- Python and dependencies installed
- `.env` file exists with API keys

### ACL worker not updating
**Check logs for:**
```
[ACL-WORKER] Error: ...
```
**Common causes:**
- ABIA API down
- Network/VPN issues
- Cache directory not writable

### Analysis taking too long
**Expected times:**
- Cached delivery: <1 second
- New delivery (441 items): 2-5 seconds
- New delivery (4820 items): 5-10 seconds

**If slower:** Check for old code (pre-optimization)

### Cache not persisting
**Check:**
- Cache directory exists: `L:\Engineering\DAR Docktag Cards\cache_data`
- Directory is writable
- Server logs show: `[ANALYSIS-CACHE-WRITE]`

---

## FILES

### Core Application
- `main.py` - FastAPI server (3900+ lines)
- `acl_background_worker.py` - Background ACL monitor
- `delivery_analysis.py` - Delivery analysis logic
- `cache_manager.py` - Cache read/write
- `batch_report.py` - Batch processing
- `informix_connect.py` - Database connection
- `db.py` - Database utilities

### Configuration
- `.env` - Environment variables
- `pyproject.toml` - Dependencies
- `uv.lock` - Lock file

### Startup
- `RUN.bat` - Server startup script

---

## DEPENDENCIES

```toml
[project]
dependencies = [
    "fastapi>=0.115.6",
    "uvicorn>=0.34.0",
    "httpx>=0.28.1",
    "python-dotenv>=1.0.1",
    "pyodbc>=5.2.0",
    "fpdf>=1.7.2",
]
```

---

## ARCHITECTURE

```
┌─────────────────────────────────────────────┐
│            SERVER (Port 8000)                │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │   Background Worker (ACL Monitor)    │   │
│  │   - Runs every 2 minutes             │   │
│  │   - Fetches ABIA deliveries          │   │
│  │   - Analyzes performance             │   │
│  │   - Writes to cache                  │   │
│  └──────────────────────────────────────┘   │
│                     │                        │
│                     ▼                        │
│  ┌──────────────────────────────────────┐   │
│  │   Shared Cache (L: Drive)            │   │
│  │   - ACL deliveries JSON              │   │
│  │   - Analysis results                 │   │
│  │   - PDF summaries                    │   │
│  │   - MDM item data                    │   │
│  └──────────────────────────────────────┘   │
│                     │                        │
│                     ▼                        │
│  ┌──────────────────────────────────────┐   │
│  │   Client Viewer (reads cache)        │   │
│  │   - Port 8001                        │   │
│  │   - No processing                    │   │
│  │   - Auto-refresh                     │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## PERFORMANCE BENCHMARKS

### Before Optimizations
- Query all items: 20-30 seconds
- Analyze delivery: 248 seconds
- PDF generation: 15+ seconds every time
- ACL worker: Re-analyzed everything every 2 minutes

### After Optimizations
- Query specific items: <1 second
- Analyze delivery (cached): <1 second
- Analyze delivery (new): 2-5 seconds
- PDF generation (cached): <1 second
- PDF generation (new): 5-10 seconds
- ACL worker: Uses cache, only analyzes new deliveries

---

## MAINTENANCE

### Clear Cache
```bash
# Clear specific category
rm -rf "L:\Engineering\DAR Docktag Cards\cache_data\deliveries"

# Clear all cache
rm -rf "L:\Engineering\DAR Docktag Cards\cache_data"
```

### Restart Server
```bash
# Stop server (Ctrl+C)
# Restart
RUN.bat
```

### Update Dependencies
```bash
uv pip install --upgrade fastapi uvicorn httpx
```

---

Last Updated: 2026-07-15  
Version: 2.0 (Client/Server Architecture)  
Status: Production Ready
