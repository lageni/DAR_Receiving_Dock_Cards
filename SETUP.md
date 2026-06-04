# Setup & Installation Guide 🐕

## Prerequisites

- Windows 10+ or macOS/Linux
- Python 3.9+ (included)
- Walmart VPN or Eagle WiFi connection required
- Informix ODBC Driver (see below)

## 1. Install Informix ODBC Driver

This app requires the IBM Informix ODBC driver to connect to the database.

### Windows
1. Download from: https://hcl-onedb.github.io/odbc/
2. Install the OneDB/Informix ODBC Driver
3. The driver should register itself automatically

### macOS
```bash
brew install ibm-db2-cli-plus
```

### Linux (Ubuntu/Debian)
```bash
sudo apt-get install libdb2cli
```

## 2. Activate Virtual Environment

```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

## 3. Run the App

### Option A: Quick Start (Windows)
```bash
start.bat
```

### Option B: Manual
```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The app will start at **http://localhost:8000**

## 4. Environment Variables

The `.env` file contains your database credentials. **Never commit this file** (it's in `.gitignore`).

If you need to change credentials:
```env
INFORMIX_HOST=dsinfmxro.s06068.us
INFORMIX_SERVER=dsinfmx
INFORMIX_PORT=23301
INFORMIX_USER=star
INFORMIX_PASSWORD=Wakyx3yg0psRlnnh
INFORMIX_DATABASE=dc_sys_common
```

## 5. Troubleshooting

### "Failed to connect to Informix"
- Check you're on Walmart VPN or Eagle WiFi
- Verify ODBC driver is installed
- Check `.env` credentials are correct
- Ensure port 23301 is not blocked by firewall

### "DRIVER={IBM INFORMIX ODBC DRIVER} not found"
- The ODBC driver name varies by system
- Check your driver name in ODBC Administrator:
  - Windows: Control Panel → Administrative Tools → ODBC Data Sources
  - Find your Informix driver name and update `main.py` line 29

### Import Errors
- Delete `.venv/` and run:
  ```bash
  uv venv
  uv sync --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
  ```

## 6. Next Steps

- [ ] Identify actual deliveries table schema from `dc_sys_common`
- [ ] Replace table names and columns in SQL queries
- [ ] Add real-time refresh with WebSockets
- [ ] Add export to CSV/Excel
- [ ] Add filtering by date range, status, customer
- [ ] Add detailed delivery history view
- [ ] Add API authentication

---

Questions? Check the README.md or ask Rocko! 🐶
