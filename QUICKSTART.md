# CodePuppyDAR - Quick Start Guide

## Setup Status

**Status**: Ready to run  
**Last Updated**: 2026-07-10  
**Dependencies**: 58 installed from Walmart Artifactory  
**Missing Fix**: google-cloud-bigquery now included

---

## What Was Fixed

### The Problem
```
ModuleNotFoundError: No module named 'fpdf'
[ERROR] google-cloud-bigquery not installed
```

### The Solution
1. Added missing Google Cloud dependencies to `pyproject.toml`
   - google-cloud-bigquery (v3.42.2)
   - google-cloud-storage (v3.12.1)
   - google-auth and related packages

2. Updated `RUN.bat` to sync from **Walmart Artifactory** instead of PyPI
   - Index: `https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple`
   - All 58 packages installed successfully
   - **Zero packages from public PyPI**

3. Created dependency documentation in `DEPENDENCIES.md`

---

## Running the Server

### Method 1: RUN.bat (Recommended)
```batch
.\RUN.bat
```
This will:
1. Check Python installation
2. Sync all dependencies from Walmart Artifactory
3. Verify .env configuration
4. Initialize database
5. Start the server on http://localhost:8000

### Method 2: Manual (Development)
```bash
# First time: Sync dependencies
uv sync

# Run the server
uv run uvicorn main:app --reload

# Or with auto-reload for development
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Method 3: Direct Python
```bash
# Activate the venv (if needed)
.venv\Scripts\activate

# Run the server
python main.py
```

---

## Installed Dependencies

**Total: 58 packages** (see DEPENDENCIES.md for full list)

**Key Packages:**
- Web: FastAPI, Uvicorn, Starlette
- PDF: fpdf2, PyPDF2
- Database: pyodbc
- **Google Cloud: bigquery, storage, auth (NEW)**
- Config: pydantic, python-dotenv
- Network: httpx, requests

---

## Required Environment Variables

Create `.env` file with:
```env
# MDM Item API (required for main features)
MDM_API_KEY=YOUR_KEY_HERE
MDM_FACILITY_NUM=6068
MDM_FACILITY_COUNTRY_CODE=US
MDM_WMT_USERID=mdm-ui

# Google Cloud (optional, for BigQuery sync)
GCS_PROJECT_ID=wmt-ambient-centeng
GCS_DATASET_ID=6068_Engineering
GCS_TABLE_ID=ACL_READ_RATE

# Google Cloud Auth (required if using GCS)
# Set up via: gcloud auth application-dn
# Or provide service account JSON
```

---

## Troubleshooting

### "Cannot reach Walmart Artifactory"
- Ensure you are on **Walmart VPN** or **Eagle WiFi**
- Check proxy settings if behind corporate firewall
- Error: `ERR_NAME_RESOLUTION_FAILED` means network issue

### "google-cloud-bigquery not found"
- Run `uv sync` again to install the newly added dependencies
- Check DEPENDENCIES.md for full package list

### "pyvenv.cfg not found" or venv issues
- Delete `.venv` folder and run `uv sync` again
- If locked, restart your terminal/IDE

### "uvicorn: command not found"
- Use `uv run uvicorn` instead of `uvicorn`
- Or activate venv: `.venv\Scripts\activate` then `uvicorn`

---

## Development Tips

### Install new dependencies
```bash
# Add to pyproject.toml, then:
uv sync

# Or direct add (temporary):
uv pip install --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple package-name
```

### View installed packages
```bash
uv pip list
```

### Run with hot-reload (development)
```bash
uv run uvicorn main:app --reload
```

### Run tests
```bash
uv run pytest
```

---

## File Locations

- `pyproject.toml` - Dependency declarations + Walmart Artifactory config
- `DEPENDENCIES.md` - Full dependency list with versions
- `RUN.bat` - Automated setup and startup script
- `.env` - Configuration (create from template, don't commit)
- `.env.example` - Template (check this in)

---

## Next Steps

1. Ensure `.env` is configured with MDM API credentials
2. Run `RUN.bat` to start the server
3. Open http://localhost:8000 in browser
4. Admin panel: http://localhost:8000/admin/debug

All dependencies come from **Walmart Artifactory** - no PyPI fallback!
