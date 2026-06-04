# CodePuppy DAR - Deliveries Dashboard 🐶

A FastAPI + Informix dashboard for managing and tracking deliveries from the Walmart dc_sys_common database.

## Quick Start

1. **Install dependencies:**
   ```bash
   uv venv
   uv sync --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
   ```

2. **Configure environment:**
   - `.env` file is already set with Informix credentials
   - Ensure you're on Walmart VPN or Eagle WiFi

3. **Run the server:**
   ```bash
   uv run uvicorn main:app --reload
   ```

4. **Open in browser:**
   - http://localhost:8000

## Architecture

- **Backend:** FastAPI + ifxpy (Informix Python driver)
- **Frontend:** HTMX + Tailwind CSS
- **Database:** Informix (dsinfmxro.s06068.us:23301)

## TODO

- [ ] Identify actual deliveries table schema
- [ ] Replace hardcoded SQL queries with real table names
- [ ] Add filtering & search
- [ ] Add date range picker
- [ ] Add export to CSV
- [ ] Add real-time updates
- [ ] Add status history tracking

## Status

🚧 **In Development** - Scaffold created, needs DB schema exploration

---

*Created by Rocko the Code Puppy* 🐕
