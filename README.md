# ACL Freight Awareness - DAR Receiving Dock Cards

Real-time ACL monitoring system with client/server architecture for warehouse receiving dock operations.

---

## Quick Start

### ACL Freight Awareness (Ports 8050/8051)

#### Server (Analysis & Cache Writer)
```bash
RUN.bat
```
- **Port:** 8050
- **Role:** Analyzes deliveries from Informix, writes cache files
- **Background:** ACL worker updates every 2 minutes
- **Access:** http://localhost:8050/delivery-analysis (manual testing)

#### Client (Live Monitor Display)
```bash
RUN_CLIENT.bat
```
- **Port:** 8051
- **Role:** Reads cache, displays ACL freight status
- **Auto-refresh:** Every 30 seconds
- **Access:** http://localhost:8051

---

### Unloader Monitor (Ports 8060/8061)

#### Server (BigQuery Cache Writer)
```bash
RUN_UNLOADER.bat
```
- **Port:** 8060
- **Role:** Queries BigQuery, caches delivery data, fetches MDM for problematic items
- **Data Source:** `wmt-ambient-centeng.6068_Engineering.DAR_DELIVERIES_CACHE`
- **Background:** Cache updates every 10 minutes
- **Access:** http://localhost:8060

#### Client (Door Monitor Display)
```bash
RUN_UNLOADER_CLIENT.bat
```
- **Port:** 8061
- **Role:** Displays deliveries by door range (430-450 default)
- **Special:** ICC Drop items show department bands instead of images
- **Auto-refresh:** Every 30 seconds
- **Access:** http://localhost:8061

---

#### Stop All Processes
```bash
KILL.bat
```
- Terminates processes on ports 8050, 8051, 8060, 8061
- Useful when processes are stuck or need restart

---

### Deployment (Production/Testing Machine)

#### Prerequisites
1. **Python 3.10+** installed and added to PATH
2. **Walmart VPN** or Eagle WiFi connection
3. **L: Drive access** to `L:\Engineering\DAR Docktag Cards\`
4. **Clone repository** to testing machine

#### First-Time Setup
1. **Copy `.env.example` to `.env`**
   ```bash
   copy .env.example .env
   ```

2. **Edit `.env` with actual credentials:**
   - `MDM_API_KEY` - Get from MDM team
   - `INFORMIX_HOST`, `INFORMIX_USER`, `INFORMIX_PASSWORD` - Database credentials
   - `DATABASE_PATH` - Path to read_rates.db (default: `L:\Engineering\DAR Docktag Cards\read_rates.db`)
   - All other settings (see `.env.example` for descriptions)

3. **Run server first time** (will auto-create venv and install dependencies):
   ```bash
   RUN.bat
   ```
   - Creates `.venv/` directory
   - Installs dependencies from Walmart Artifactory
   - Starts server on port 8050

4. **Run client** (in separate terminal):
   ```bash
   RUN_CLIENT.bat
   ```
   - Uses same `.venv/` as server
   - Starts client on port 8051

#### Network Access
To access from other machines on the network:
- Server: `http://<MACHINE-IP>:8050`
- Client: `http://<MACHINE-IP>:8051`

Example: `http://10.145.220.133:8051`

#### Startup Scripts Handle Everything
 - Activate virtual environment automatically
 - Create venv if it doesn't exist
 - Install dependencies on first run
 - No manual activation needed

---

## Architecture

```
ABIA API (Active Deliveries)
         ↓
    SERVER (Port 8050)
    - Analyzes deliveries
    - Checks read rates (SQLite)
    - Fetches MDM data (images, info)
    - Calculates bad cases
    - Writes cache files
         ↓
  CACHE (L:\Engineering\DAR Docktag Cards\cache_data)
    - analysis_{delivery}.json
    - mdm_{item}.json
         ↓
    CLIENT (Port 8051)
    - Reads cache
    - Displays grid of deliveries
    - Auto-scrolls through items
    - Ranked by bad cases
```

---

## Key Files

### Startup Scripts
- `RUN.bat` - Start ACL server (port 8050)
- `RUN_CLIENT.bat` - Start ACL client viewer (port 8051)
- `RUN_UNLOADER.bat` - Start Unloader server (port 8060)
- `RUN_UNLOADER_CLIENT.bat` - Start Unloader client viewer (port 8061)
- `KILL.bat` - Stop all processes on ports 8050/8051/8060/8061

### Application Code (scripts/)
**ACL Freight Awareness:**
- `main.py` - FastAPI server (analysis engine, cache writer)
- `client_viewer.py` - FastAPI client (display only)
- `acl_background_worker.py` - Background ACL monitor
- `delivery_analysis.py` - Delivery analysis logic

**Unloader Monitor:**
- `unloader_server.py` - BigQuery-based server (port 8060)
- `unloader_client.py` - Door range viewer (port 8061)

**Shared Utilities:**
- `cache_manager.py` - Shared cache module
- `informix_connect.py` - Informix database connection
- `batch_report.py` - Read rates analysis
- `sync_bigquery.py` - Standalone BigQuery sync CLI script
- `db.py` - Database initialization

### Configuration
- `.env` - Environment variables (API keys, DB paths)
- `pyproject.toml` - Python dependencies
- `requirements.txt` - Dependency list

### Reference
- `reference/department_bands.json` - Department data
- `reference/mdm_item_api_response_example.json` - MDM API example

### Documentation
- `_docs/UNLOADER_FEATURE_SPEC.md` - Complete unloader feature specification

---

## Features

### ACL Freight Awareness Server
- **Informix PO Query** - Test endpoint at `/delivery-analysis`
- **Read Rates Analysis** - SQL-optimized, pre-filters problematic items (< 85%)
- **MDM Integration** - Fetches item images, names, dimensions
- **Cache Writing** - Analysis results saved for instant client access
- **Background Worker** - Auto-analyzes ACL deliveries every 2 minutes
- **Import Detection** - Department bands only generated for IMPORT PO events

### ACL Freight Awareness Client
- **All Deliveries Visible** - No scrolling, grid layout
- **Auto-Scroll Items** - 2 items per page, 5 second rotation
- **Ranked Display** - Worst deliveries (most bad cases) first
- **Dev View Toggle** - Hide/show technical details (MDS#, dimensions)
- **Color-Coded** - Red (urgent), Yellow (warning), Green (OK), Gray (pending)

### Unloader Monitor Server (NEW)
- **BigQuery Data Source** - Queries `DAR_DELIVERIES_CACHE` table
- **Incremental Caching** - Only pulls NEW deliveries from BQ
- **Door Range Filtering** - Default: 430-450 (configurable)
- **MDM Integration** - Fetches catalog GTIN + images for problematic items
- **ICC Drop Logic** - Detects trailers needing department bands
- **Background Updates** - Cache refreshes every 10 minutes
- **Separate Cache** - Isolated in `cache_data_unloader/` folder

### Unloader Monitor Client (NEW)
- **Door Range Display** - Shows deliveries for doors 430-450 (default)
- **Rolodex View** - Auto-scrolls through items (2 per page, 5 sec)
- **Department Bands** - ICC Drop items show dept bands instead of images
- **Case Estimates** - Unknown, Bad, Good case counts
- **Dev View Toggle** - Simple view default, technical details on demand
- **Auto-Refresh** - Page reloads every 30 seconds
- **Color-Coded Performance** - Green (>85%), Yellow (50-85%), Red (<50%)

---

## Cache Structure

### Analysis Cache
**File:** `cache_data/deliveries/analysis_{delivery_number}.json`

```json
{
  "problematic_mds_ids": ["12345", "67890"],
  "problematic_details": {
    "12345": {
      "avg_perf": 62.5,
      "bad_cases": 75,
      "recommendation": "REQUIRES MANUAL INSPECTION",
      "color_hex": "#f59e0b"
    }
  },
  "problematic_items_data": [
    {
      "mds_fam_id": "12345",
      "item_name": "Great Value Widget",
      "image_url": "https://...",
      "vnpk_length": "12",
      "vnpk_width": "8",
      "vnpk_height": "6"
    }
  ],
  "approved_count": 420
}
```

### MDM Cache
**File:** `cache_data/items/mdm_{mds_id}.json`

Contains item images, names, dimensions from MDM API.

---

## Environment Variables

Create `.env` file with:

```env
MDM_API_KEY=your_key
MDM_FACILITY_NUM=6068
MDM_FACILITY_COUNTRY_CODE=US
MDM_WMT_USERID=mdm-ui
DATABASE_PATH=L:\Engineering\DAR Docktag Cards\read_rates.db
```

---

## Optimizations

### SQL Pre-Filtering
- **Before:** Load 131k items, filter in Python
- **After:** SQL WHERE IN clause loads only needed items
- **Result:** 100-1000x faster queries

### Analysis Caching
- **Before:** Re-analyze every request
- **After:** Cache results for 2 days
- **Result:** Instant subsequent loads

### Bad Cases Pre-Filter
- **Before:** Load all items, check performance
- **After:** SQL CTE filters performance < 85% at database level
- **Result:** Only loads problematic items

---

## Troubleshooting

### Server Won't Start
- Check port 8050 not in use
- Verify `.env` file exists with API keys
- Check VPN connection (for MDM API)

### Client Shows "Pending Analysis"
- Wait 2 minutes for background worker to analyze
- Or click delivery on server (port 8050) to trigger manual analysis

### No Cache Found
- Ensure server is running (port 8050)
- Check background worker logs: `[ACL-WORKER]`
- Verify L: drive accessible

---

## Development

### Sync BigQuery Data (Standalone)
```bash
python sync_bigquery.py
```

**What it does:**
- Automatically detects missing dates in SQLite database
- Syncs only new data from BigQuery ACL_READ_RATE table
- Filters out DPAL/LBSS pick types
- Shows progress and statistics

**Requirements:**
- Google Cloud credentials configured
- VPN connection to Walmart network
- BigQuery access to `wmt-ambient-centeng.6068_Engineering.ACL_READ_RATE`

### Install Dependencies
```bash
uv pip install -r pyproject.toml --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
```

### Clear Cache
```bash
del "L:\Engineering\DAR Docktag Cards\cache_data\deliveries\*.json"
del "L:\Engineering\DAR Docktag Cards\cache_data\items\*.json"
```

### Git
```bash
git add -A
git commit -m "Your message"
git push
```

---

## Repository

**GitHub:** https://github.com/lageni/DAR_Receiving_Dock_Cards.git

---

## Recent Fixes

### 2026-07-24: Performance Calculation Fix
- Fixed `get_avg_performance()` to use weighted average: `total(acl_null_cnt) / total(acl_event_cnt)`
- Old method incorrectly averaged individual percentages
- Clarified: `acl_null_cnt` = successful reads (misleading name)
- Item 674874972 now correctly shows 82.84% and gets flagged (< 85%)

### 2026-07-24: SQLite Connection Optimization
- All DB reads now use context managers (`with` statement) for automatic cleanup
- Read-only mode with 20-second timeout prevents database locks
- Detailed logging shows exactly what's being read from the database
- Fixes: Server/client both reading DB without interference

### 2026-07-24: File Logging Added
- Server and client now log to `L:\Engineering\DAR Docktag Cards\cache_data\logs\`
- Daily log files: `server_YYYYMMDD.log` and `client_YYYYMMDD.log`
- Logs show DB queries, cache operations, errors, and performance metrics
- Both console and file output for easy debugging

---

Last Updated: 2026-07-24
Version: 2.0 (Client/Server Architecture)
