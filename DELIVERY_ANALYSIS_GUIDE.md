# Delivery Analysis Feature

## Overview

The **Delivery Analysis** feature enables you to:
1. Enter a **delivery number** (rcv.appointment_nbr)
2. Query the **Informix database** to retrieve all purchase order lines for that delivery
3. **Automatically apply batching** to every unique `mds_fam_id` returned
4. View consolidated results with read rate data for all items

## How It Works

### Step-by-Step Flow

```
User Input
    |
    v
GET /delivery-analysis (Search Form)
    |
    v
User enters delivery number
    |
    v
POST /api/delivery-analysis/search
    |
    +---> get_delivery_po_data() [Informix query]
    |     - Executes the PO query
    |     - Returns all rows with mds_fam_ids
    |
    +---> apply_batching_to_delivery() [SQLite batching]
    |     - For each unique mds_fam_id:
    |       - Loads read rate data from SQLite
    |       - Attaches to the Informix row
    |
    v
Display Results
    - Summary stats (record count, unique items, etc.)
    - Table with all PO lines + read rate record counts
    - Batching summary (status per item)
    - Download JSON button
```

### The Informix Query

The feature executes this query with your delivery number:

```sql
SELECT
    rcv.appointment_nbr as delivery_nbr,
    po.po_type_code,
    po.po_dept_nbr,
    po.po_order_date,
    po.event,
    po.vndr_nbr,
    po.ship_date,
    po.cancel_date,
    po.status,
    po.pur_ord_id,
    po.po_nbr,
    po.must_arrive_by_dt,
    line.po_line_nbr,
    line.mds_fam_id,
    line.vendor_stock_id,
    line.whpk_order_qty,
    line.whpk_max_rcv_qty,
    line.status as line_status
FROM rdc_db:informix.purchase_order po
INNER JOIN dc_common:informix.po_line line 
    ON po.pur_ord_id = line.pur_ord_id
LEFT JOIN rdc_db:informix.dc_receiver rcv 
    ON po.po_nbr = rcv.po_nbr
WHERE po.must_arrive_by_dt > today - 60
    AND rcv.receiver_final_ts > today - 60
    AND mod(po.po_type_code, 2) = 1
    AND rcv.appointment_nbr = {delivery_number}
```

### Batching Integration

For each unique `mds_fam_id` in the results:
- The feature **borrows** the batching logic from `batch_report.py`
- It queries the **read_rates.db** SQLite database
- It retrieves all historical read rate records for that item
- It attaches the count to the PO line row

## Files Created/Modified

### New Files
- **delivery_analysis.py** - Core logic module
  - `get_delivery_po_data(delivery_number)` - Informix query
  - `apply_batching_to_delivery(delivery_data)` - Applies batching to results

### Modified Files
- **main.py**
  - Added `/delivery-analysis` endpoint (GET) - UI form
  - Added `/api/delivery-analysis/search` endpoint (GET) - API logic
  - Added navigation link on home page

## Usage

### From the Web UI

1. Go to **http://localhost:8000**
2. Click **"Delivery Analysis"** button
3. Enter a delivery number (e.g., `10691042`)
4. Click **"Search"**
5. View results:
   - **Summary** section with totals
   - **PO Lines table** with all data + read rate record counts
   - **Batching Summary** showing load status per item
   - **Download JSON** button for raw data export

### From the Command Line (Python)

```python
from delivery_analysis import get_delivery_po_data, apply_batching_to_delivery

# Step 1: Query Informix
delivery_data = get_delivery_po_data("10691042")

# Step 2: Apply batching
delivery_data = apply_batching_to_delivery(delivery_data)

# Step 3: Access results
print(f"Found {delivery_data['record_count']} PO lines")
print(f"Unique items: {len(delivery_data['mds_fam_ids'])}")

for row in delivery_data['data']:
    mds_id = row['mds_fam_id']
    batch_count = row['batching_info'].get('record_count', 0)
    print(f"MDS {mds_id}: {batch_count} read rate records")
```

## Architecture Decisions

### Why This Design?

1. **Non-invasive**: All new code in `delivery_analysis.py` + minimal changes to main.py
2. **Borrows, doesn't duplicate**: Uses existing `batch_report.py` functions without modification
3. **Separation of concerns**:
   - Data retrieval (Informix) in one function
   - Batching application in another
   - UI/rendering in main.py endpoints
4. **YAGNI principle**: No unnecessary abstraction layers
5. **DRY principle**: Reuses existing batching logic

### Data Flow Isolation

- **SQLite (read_rates.db)**: Batch/read rate data
- **Informix**: PO/delivery data
- **Results**: Combined view, not stored anywhere (clean output)

## Troubleshooting

### No Results?
- **Check delivery number**: Make sure it's a valid `rcv.appointment_nbr` in Informix
- **Check date filters**: Query requires data from last 60 days
- **Check Informix connection**: Verify `.env` has correct INFORMIX_* settings

### Batching Shows Errors?
- **Check SQLite path**: Verify `DATABASE_PATH` in `.env` points to read_rates.db
- **Check data**: Some mds_fam_ids may not exist in read_rates.db (expected)

### Informix Connection Failed?
- See `informix_connect.py` for connection troubleshooting
- Ensure Walmart VPN is connected
- Verify pyodbc and IBM INFORMIX ODBC DRIVER are installed

## Next Steps / Future Enhancements

Possible additions (without modifying existing features):
- Export to PDF (like batch feature does)
- Filtering by department, vendor, status
- Performance trending across deliveries
- Integration with MDM API for item details
- Date range selection beyond 60 days

## Code References

- `batch_report.py` - `get_item_read_rate_data()` function
- `informix_connect.py` - `InformixConnection` class
- `main.py` - `@app.get("/delivery-analysis")` endpoints
