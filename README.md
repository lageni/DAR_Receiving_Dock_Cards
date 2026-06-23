# CodePuppyDAR - MDM Item Inventory Search

A FastAPI application for searching Walmart MDM inventory items with ACL performance tracking.

## Quick Start

```bash
python main.py
```

Open browser: **http://localhost:8000**

## Features

- Search items by **Item ID**
- Display product details (name, image, GTIN, Catalog GTIN)
- View **ACL Performance %** trends with charts
- Download PDF print cards
- Real-time API integration with Walmart MDM

## Architecture

### Key Data Relationships

**IMPORTANT:** The `read_rates.csv` file uses `MDS_FAM_ID` column to store **ITEM NUMBERS**.

When searching for an item:
1. User enters: **Item ID** (e.g., 659608850)
2. App searches: **MDM API** by Item ID → returns product details
3. App looks up ACL data: **read_rates.csv** using `MDS_FAM_ID` column (which equals the Item ID)
4. Display: Product info + ACL Performance chart (if data exists in CSV)

### Files

- **main.py** - FastAPI application
- **read_rates.csv** - ACL performance data (6.4 MB)
  - Columns: `MDS_FAM_ID` (=Item ID), `TS_DATE`, `ACL_EVENT_CNT`, `ACL_NULL_CNT`, etc.
  - Keyed by Item Number in `MDS_FAM_ID` column
- **.env** - Configuration (API keys, facility info)
- **mdm_item_api_response_example.json** - Sample API response

## Configuration (.env)

```env
MDM_API_KEY=<your-api-key>
MDM_FACILITY_NUM=6068
MDM_FACILITY_COUNTRY_CODE=US
MDM_WMT_USERID=mdm-ui
INFORMIX_HOST=<db-host>
INFORMIX_USER=<db-user>
INFORMIX_PASSWORD=<db-pass>
```

## API Endpoints

- `GET /` - Main search page
- `GET /api/inventory/search?item_id=<id>` - Search and display results
- `GET /print-card?item_id=<id>` - HTML print card
- `GET /print-card-pdf?item_id=<id>` - PDF download

## ACL Data Lookup

The app automatically correlates:
- **Item ID** → MDM API call
- **Item ID** → read_rates.csv lookup (via `MDS_FAM_ID` column = Item ID)

If an item doesn't show ACL data on the main page, it means that Item ID doesn't have a record in `read_rates.csv`.

## GTINs

Each item may have:
- **Catalog GTIN** - Special catalog identifier (if present in API response)
- **Consumable GTIN** - Standard product barcode

The app displays **Catalog GTIN** if available, otherwise shows **Consumable GTIN**.
