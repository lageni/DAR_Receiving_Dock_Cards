# ACL Freight Awareness - DAR Receiving Dock Cards

Real-time ACL monitoring system with client/server architecture for warehouse receiving dock operations.

---

## Quick Start

### Development (Local Machine)

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

### Core Application
- `main.py` - FastAPI server (analysis engine, cache writer)
- `client_viewer.py` - FastAPI client (display only)
- `acl_background_worker.py` - Background ACL monitor
- `delivery_analysis.py` - Delivery analysis logic
- `cache_manager.py` - Shared cache module
- `informix_connect.py` - Informix database connection
- `batch_report.py` - Read rates analysis
- `sync_bigquery.py` -  **Standalone BigQuery sync CLI script**

### Configuration
- `.env` - Environment variables (API keys, DB paths)
- `pyproject.toml` - Python dependencies

### Reference
- `reference/department_bands.json` - Department data
- `reference/mdm_item_api_response_example.json` - MDM API example

---

## Features

### Server
- **Informix PO Query** - Test endpoint at `/delivery-analysis`
- **Read Rates Analysis** - SQL-optimized, pre-filters problematic items (< 85%)
- **MDM Integration** - Fetches item images, names, dimensions
- **Cache Writing** - Analysis results saved for instant client access
- **Background Worker** - Auto-analyzes ACL deliveries every 2 minutes

### Client
- **All Deliveries Visible** - No scrolling, grid layout
- **Auto-Scroll Items** - 2 items per page, 5 second rotation
- **Ranked Display** - Worst deliveries (most bad cases) first
- **Dev View Toggle** - Hide/show technical details (MDS#, dimensions)
- **Color-Coded** - Red (urgent), Yellow (warning), Green (OK), Gray (pending)

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
- Items are now flagged accurately (e.g., item 674874972 now shows 17.16% instead of 9.19%)

---

Last Updated: 2026-07-24
Version: 2.0 (Client/Server Architecture)
