# Unloader Monitor - DAR Receiving Dock Cards

BigQuery-based delivery/unloader monitoring for warehouse receiving dock operations.

> **Looking for the old ACL Freight Awareness app (ports 8050/8051)?** It's been
> archived - see [`archive/old_acl_app/`](archive/old_acl_app/README.md). This
> README now covers the **Unloader Monitor**, which is the actively maintained app.

---

## Quick Start

### Server (BigQuery Cache Writer)
```bash
RUN_UNLOADER.bat
```
- **Port:** 8060
- **Role:** Queries BigQuery, caches delivery data, fetches MDM for problematic items
- **Data Source:** `wmt-ambient-centeng.6068_Engineering.DAR_DELIVERIES_CACHE`
- **Background:** Cache updates every 10 minutes
- **Access:** http://localhost:8060

### Client (Door Monitor Display)
```bash
RUN_UNLOADER_CLIENT.bat
```
- **Port:** 8061
- **Role:** Displays deliveries by door range (425-500 default)
- **Special:** ICC Drop items show department bands instead of images
- **Auto-refresh:** Every 30 seconds
- **Auto-open:** Browser opens automatically
- **Access:** http://localhost:8061

### Manager (Summary View)
```bash
RUN_UNLOADER_MANAGER.bat
```
- **Port:** 8062
- **Role:** Horizontal progress bars showing Good/Bad/Unknown cases by door
- **Summary:** Quick overview for managers
- **Auto-refresh:** Every 30 seconds
- **Auto-open:** Browser opens automatically
- **Access:** http://localhost:8062

### Stop All Processes
```bash
KILL.bat
```
- Terminates processes on ports 8060, 8061, 8062

---

## Deployment (Production/Testing Machine)

### Prerequisites
1. **Python 3.10+** installed and added to PATH
2. **Walmart VPN** or Eagle WiFi connection
3. **L: Drive access** to `L:\Engineering\DAR Docktag Cards\`
4. **Clone repository** to testing machine

### First-Time Setup
1. **Copy `.env.example` to `.env`**
   ```bash
   copy .env.example .env
   ```

2. **Edit `.env` with actual credentials:**
   - `MDM_API_KEY` - Get from MDM team
   - `MDM_FACILITY_NUM`, `MDM_FACILITY_COUNTRY_CODE`, `MDM_WMT_USERID`
   - `GCS_PROJECT_ID` - Your BigQuery project (used for ADC quota project)

3. **Authenticate with GCP for BigQuery access:**
   ```bash
   python scripts\setup_gcp_auth.py
   ```
   Logs you in locally via Application Default Credentials - no service account,
   no manual env vars. See [`docs/GCP_AUTH_SETUP.md`](docs/GCP_AUTH_SETUP.md) for
   full details and troubleshooting. `RUN_UNLOADER.bat` and
   `RUN_UNLOADER_CLIENT.bat` also auto-check this on every startup and will
   prompt you to log in if credentials are missing.

4. **Run the server first time** (will auto-create venv and install dependencies):
   ```bash
   RUN_UNLOADER.bat
   ```

5. **Run the client** (in a separate terminal):
   ```bash
   RUN_UNLOADER_CLIENT.bat
   ```

6. **Run the manager view** (optional, in a separate terminal):
   ```bash
   RUN_UNLOADER_MANAGER.bat
   ```

### Network Access
To access from other machines on the network:
- Server: `http://<MACHINE-IP>:8060`
- Client: `http://<MACHINE-IP>:8061`
- Manager: `http://<MACHINE-IP>:8062`

---

## Architecture

```
BigQuery (DAR_DELIVERIES_CACHE)
         |
    SERVER (Port 8060)
    - Queries active deliveries
    - Fetches MDM data for problematic items (< 85% read rate)
    - Writes cache files (no door filtering - caches everything)
    - Background refresh every 10 minutes
         |
  CACHE (L:\Engineering\DAR Docktag Cards\cache_data_unloader)
    - deliveries/delivery_{nbr}.json
    - items/mdm_{mds_id}.json
         |
    +----+----+
    |         |
 CLIENT    MANAGER
(8061)      (8062)
Door       Progress bars
rolodex    by door
```

---

## Key Files

### Startup Scripts
- `RUN_UNLOADER.bat` - Start Unloader server (port 8060)
- `RUN_UNLOADER_CLIENT.bat` - Start Unloader client viewer (port 8061)
- `RUN_UNLOADER_MANAGER.bat` - Start Unloader manager summary view (port 8062)
- `KILL.bat` - Stop all processes on ports 8060/8061/8062

### Application Code (scripts/)
- `unloader_server.py` - BigQuery-based server (port 8060)
- `unloader_client.py` - Door range viewer (port 8061)
- `unloader_manager.py` - Manager summary view (port 8062)
- `department_bands.py` - Department band lookup for ICC Drop items
- `setup_gcp_auth.py` - Local GCP ADC login/setup (see `docs/GCP_AUTH_SETUP.md`)

### Configuration
- `.env` - Environment variables (API keys, project IDs)
- `pyproject.toml` - Python dependencies
- `requirements.txt` - Dependency list

### Reference
- `reference/department_bands.json` - Department color/band data
- `reference/mdm_item_api_response_example.json` - MDM API example

### Documentation
- `docs/GCP_AUTH_SETUP.md` - How to set up local GCP authentication (BigQuery)
- `docs/UNLOADER_FEATURE_SPEC.md` - Complete unloader feature specification
- `docs/archive/` - Historical progress notes and completed-feature write-ups
  (kept for reference, not actively maintained)

### Archived
- `archive/old_acl_app/` - The original ACL Freight Awareness + Delivery
  Analysis app (ports 8050/8051). Frozen, not actively maintained. See its
  own README for how to run it if you ever need it again.

---

## Features

### Unloader Monitor Server
- **BigQuery Data Source** - Queries `DAR_DELIVERIES_CACHE` table
- **Incremental Caching** - Only pulls NEW deliveries from BQ
- **Door Range Filtering** - Client-side, default: 425-500 (configurable)
- **MDM Integration** - Fetches catalog GTIN + images for problematic items
- **ICC Drop Logic** - Detects trailers needing department bands
- **Background Updates** - Cache refreshes every 10 minutes
- **Separate Cache** - Isolated in `cache_data_unloader/` folder

### Unloader Monitor Client
- **Door Range Display** - Shows deliveries for doors 425-500 (default)
- **Rolodex View** - Auto-scrolls through items (2 per page, 5 sec)
- **Department Bands** - ICC Drop items show dept bands instead of images
- **Case Estimates** - Unknown, Bad, Good case counts
- **Dev View Toggle** - Simple view default, technical details on demand
- **Auto-Refresh** - Page reloads every 30 seconds
- **Color-Coded Performance** - Green (>85%), Yellow (50-85%), Red (<50%)

### Unloader Manager
- **Horizontal Progress Bars** - Good/Bad/Unknown case distribution by door
- **Quick Overview** - At-a-glance summary for managers
- **Auto-Refresh** - Every 30 seconds

---

## Environment Variables

Create a `.env` file with:

```env
MDM_API_KEY=your_key
MDM_FACILITY_NUM=6068
MDM_FACILITY_COUNTRY_CODE=US
MDM_WMT_USERID=mdm-ui
GCS_PROJECT_ID=your-bigquery-project-id
```

---

## Troubleshooting

### Server Won't Start
- Check port 8060 not in use
- Verify `.env` file exists with API keys
- Check VPN connection (for MDM API + BigQuery)
- Run `python scripts\setup_gcp_auth.py --check` to confirm GCP auth

### Client Shows Placeholder Items ("No item data available")
- Wait for the server's background cache updater to run (every 10 minutes),
  or hit `http://localhost:8060` and click "Update Cache" to trigger manually

### No Deliveries Showing
- Ensure server is running (port 8060)
- Check `L:\Engineering\DAR Docktag Cards\cache_data_unloader\logs\` for errors
- Verify L: drive is accessible

---

## Development

### Install Dependencies
```bash
uv pip install -r pyproject.toml --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
```

### Clear Cache
```bash
del "L:\Engineering\DAR Docktag Cards\cache_data_unloader\deliveries\*.json"
del "L:\Engineering\DAR Docktag Cards\cache_data_unloader\items\*.json"
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

Last Updated: 2026-08-19
Version: 3.0 (Unloader Monitor is now the primary app; ACL Freight Awareness archived)
