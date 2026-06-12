# CodePuppy DAR - Inventory Search Tool

A lightweight FastAPI web app for searching items in the Walmart inventory-viewer API with full JSON response display.

## Quick Start

1. **Install dependencies:**
   ```bash
   cd CodePuppyDAR
   uv venv
   uv sync --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
   ```

2. **Configure credentials in `.env`:**
   ```
   INVENTORY_JWT_TOKEN=your_jwt_token_here
   INVENTORY_USER_ID=Dylan Hoang - d0h0pf7
   INVENTORY_API_URL=https://inventory-viewer.prod.walmart.net
   INVENTORY_DEFAULT_NODE=6068
   INVENTORY_COUNTRY_CODE=US
   ```
   See `.env.example` for details.

3. **Run the server:**
   ```bash
   uv run uvicorn main:app --reload
   ```

4. **Open in browser:**
   - http://localhost:8000

## How to Use

1. Enter an **Item ID** or **UPC code**
2. Select the **ID Type** (Item Number or UPC)
3. Specify the **Node/Store** (default: 6068)
4. Click **Search Item**
5. View the full JSON response

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `INVENTORY_JWT_TOKEN` | JWT auth token from inventory-viewer | `eyJ...` |
| `INVENTORY_USER_ID` | Your user ID | `Dylan Hoang - d0h0pf7` |
| `INVENTORY_API_URL` | API base URL | `https://inventory-viewer.prod.walmart.net` |
| `INVENTORY_DEFAULT_NODE` | Default store node | `6068` |
| `INVENTORY_COUNTRY_CODE` | Country code | `US` |

## Getting Your JWT Token

1. Open the inventory-viewer dashboard
2. Press **F12** to open DevTools
3. Go to **Network** tab
4. Refresh the page
5. Look for any request and check **Request Headers**
6. Copy the **Authorization** header value
7. Paste it into `.env` as `INVENTORY_JWT_TOKEN`

## Architecture

- **Backend:** FastAPI
- **Frontend:** HTMX + Tailwind CSS
- **API:** Inventory-Viewer (Walmart internal)

## Features

- Fast, lightweight search interface
- Full JSON response display (pretty-printed)
- GET-based queries (stateless, cacheable)
- Static credentials in `.env` (no UI auth required)

---

*Created by Rocko the Code Puppy*
