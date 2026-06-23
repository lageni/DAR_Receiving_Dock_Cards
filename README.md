# CodePuppyDAR - Inventory Search & ACL Performance Analysis

A FastAPI-based inventory search application that integrates MDM (Master Data Management) APIs with ACL (Automated Cycle Logistics) performance analytics.

## Features

- **MDM API Integration**: Search inventory by item number
- **Product Details**: Display product image, GTIN, supplier information
- **ACL Performance Metrics**: View average performance % and trend analysis
- **Directive Actions**: Automated recommendations based on ACL performance ruleset
- **Print Cards**: Generate and download PDF print cards for items
- **SQLite Database**: Local caching of ACL read rate metrics

## Quick Start

### Prerequisites

- Python 3.10+
- FastAPI
- MDM API credentials

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/dylanhoang11/DAR-Receiving-Frictions.git
   cd CodePuppyDAR
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Configure `.env` file:
   ```
   MDM_API_KEY=your-api-key-here
   MDM_FACILITY_NUM=6068
   MDM_FACILITY_COUNTRY_CODE=US
   MDM_WMT_USERID=mdm-ui
   ```

4. Run the application:
   ```bash
   python main.py
   ```

5. Open browser:
   ```
   http://localhost:8000
   ```

## Usage

### Search for an Item

1. Enter item number (e.g., 659608850)
2. Click **Search** or **Example** for demo
3. View:
   - Product image and details
   - ACL Performance metrics
   - Directive action recommendation
   - Performance trend

### Directive Actions Ruleset

The system automatically recommends actions based on ACL performance:

- **ACL APPROVED** (Green): Performance >= 85% - No action needed
- **ADEQUATE PERFORMANCE** (Yellow): Performance < 85% & Improving - Monitor closely
- **REQUIRES MANUAL INSPECTION** (Yellow): Performance < 85% & Declining - Review needed
- **WORKSTATION RECOMMENDED** (Red): Performance < 50% - Immediate action required

### Download Print Card

Click **Download PDF** to generate a printable card with:
- Product image
- Item details (GTIN, supplier, etc.)
- ACL performance metrics
- Directive action recommendation

## Architecture

### Core Files

- **main.py** - FastAPI application, search endpoints, UI routes
- **db.py** - SQLite database management for ACL metrics
- **gcs_sync.py** - Google Cloud BigQuery integration (optional)
- **error_logger.py** - Centralized error logging

### Key Endpoints

- `GET /` - Main search page
- `GET /api/inventory/search` - Item search via MDM API
- `GET /print-card` - HTML print card view
- `GET /print-card-pdf` - PDF download endpoint
- `GET /admin` - Admin dashboard

## Database

### read_rates.db

SQLite database containing ACL performance metrics:
- **mds_fam_id**: Item number (key for lookups)
- **acl_event_cnt**: Total ACL events
- **acl_null_cnt**: Null/failed reads
- **acl_insert_date**: Date of metric

Note: Column named `mds_fam_id` contains the item number, not merchandiseFamilyID.

## API Integration

### MDM API

- **Endpoint**: `https://uwms-item.prod.us.walmart.net/items/wm/{item_id}/`
- **Headers**: Api-Key, Facilitynum, Facilitycountrycode, Wmt-Userid
- **Response**: Product details including image URL, GTIN, supplier info

## Development

See `REQUIREMENTS_LOG.txt` for comprehensive requirements, known issues, and development notes.

## Support

For issues or questions, refer to the inline code documentation or REQUIREMENTS_LOG.txt.

## License

Internal Walmart tool - All rights reserved
