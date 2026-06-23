# CodePuppyDAR - Database Architecture

## Overview

CodePuppyDAR uses **SQLite** for efficient, partitioned access to ACL performance data. The database can be synced with **Google Cloud BigQuery** on demand.

---

## Database Structure

### Table: `read_rates`

```sql
CREATE TABLE read_rates (
    id INTEGER PRIMARY KEY,
    acl_insert_date DATE NOT NULL,           -- Partition key (when data was inserted)
    ts_date DATE NOT NULL,                   -- Observation date
    mds_fam_id TEXT NOT NULL,                -- Item number (key for lookups)
    item1_desc TEXT,                         -- Item description
    pick_type_code TEXT,                     -- Pick type (e.g., DQRL)
    slot_id TEXT,                            -- Warehouse slot
    vnpk_gtin_t TEXT,                        -- GTIN
    acl_event_cnt INTEGER,                   -- Total ACL events
    acl_null_cnt INTEGER,                    -- Null read count
    acl_bypass_cnt INTEGER,                  -- Bypass count
    good_read_cnt_null INTEGER,              -- Good reads (nulls)
    good_read_cnt_bypass INTEGER,            -- Good reads (bypass)
    item_num_read_cnt_null INTEGER,          -- Item number reads (nulls)
    item_num_read_cnt_bypass INTEGER,        -- Item number reads (bypass)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(acl_insert_date, ts_date, mds_fam_id, slot_id)
)
```

### Indexes

```
idx_mds_fam_id     - Fast lookup by Item ID
idx_acl_insert_date - Partition filtering
idx_ts_date        - Time-based queries
```

---

## Data Migration

### From CSV to SQLite

**First-time setup (automatic):**

```bash
RUN.bat
```

This will:
1. Create `read_rates.db`
2. Migrate data from `read_rates.csv` (if present)
3. Create indexes for fast lookups

**Manual initialization:**

```bash
python db.py
```

---

## Google Cloud BigQuery Sync

### Configuration

Create environment variables or use the admin debug page:

```env
# In .env file (optional)
GCS_PROJECT_ID=your-gcp-project
GCS_DATASET_ID=your-dataset
GCS_TABLE_ID=your-table
```

### How Sync Works

**Partition Strategy:**

1. Query: `SELECT MAX(acl_insert_date) FROM read_rates` → Get latest local date
2. Filter: `WHERE ACL_INSERT_DATE > {latest_date}` 
3. Fetch: Pull all new rows from BigQuery
4. Append: Insert new rows into SQLite (duplicates are skipped)

**Example:**

```
Last sync: 2026-06-15
Local DB:  2026-01-01 to 2026-06-15 (169 days of data)
GCS table: 2026-01-01 to 2026-06-19 (new 4 days)
         ↓
Sync fetches only: 2026-06-16, 2026-06-17, 2026-06-18, 2026-06-19
Appends: ~27,360 new rows (assuming same partition structure)
```

---

## Using the Admin Debug Page

**Access:**

```
http://localhost:8000/admin/debug
```

**Features:**

### 1. Database Status
- Total rows
- Unique items
- Date range

### 2. Test Item Lookup
- Enter an Item ID (e.g., 659608850)
- See how many ACL records exist for that item

### 3. Google Cloud Configuration
- **Project ID**: Your GCP project
- **Dataset ID**: BigQuery dataset containing ACL data
- **Table ID**: BigQuery table name
- Click "Initialize GCS" to connect

### 4. Manual Sync
- Click "Sync Data" to fetch new rows from BigQuery
- See results: rows inserted, skipped, errors

---

## Python API

### Database Functions

**Get item ACL data:**

```python
from db import get_item_rates

rates = get_item_rates("659608850")
# Returns: [
#   {'date': '2026-06-15', 'null_pct': 45.2, 'event_cnt': 50, 'null_cnt': 23},
#   {'date': '2026-06-14', 'null_pct': 42.0, 'event_cnt': 50, 'null_cnt': 21},
#   ...
# ]
```

**Get database stats:**

```python
from db import get_database_stats

stats = get_database_stats()
# Returns: {
#   'total_rows': 136800,
#   'unique_items': 27360,
#   'min_date': '2026-01-01',
#   'max_date': '2026-06-19'
# }
```

### Google Cloud Sync Functions

**Initialize connection:**

```python
from gcs_sync import initialize_google_cloud

success = initialize_google_cloud(
    project_id="my-project",
    dataset_id="acl_data",
    table_id="read_rates"
)
```

**Trigger sync:**

```python
from gcs_sync import sync_from_google_cloud

result = sync_from_google_cloud(since_date="2026-06-15")
# Returns: {
#   'status': 'success',
#   'inserted': 27360,
#   'skipped': 0,
#   'errors': 0,
#   'last_sync': '2026-06-19T15:45:30.123456'
# }
```

**Get sync status:**

```python
from gcs_sync import get_sync_status

status = get_sync_status()
# Returns: {
#   'gcs_initialized': true,
#   'last_sync': '2026-06-19T15:45:30.123456',
#   'latest_data_date': '2026-06-19',
#   'total_rows': 136800
# }
```

---

## Common Workflows

### Daily Operation

```
1. Run: RUN.bat
2. Users access: http://SERVERNAME:8000
3. Searches use cached SQLite database
4. Fast performance (milliseconds)
```

### Weekly Data Update

```
1. Admin opens: http://localhost:8000/admin/debug
2. Fills in GCS credentials (if not cached)
3. Clicks "Sync Data"
4. New rows appended automatically
5. Users see updated ACL data on next search
```

### First-Time Setup

```
1. Copy folder to server
2. Run: RUN.bat (first time)
   - Detects first-run
   - Checks Python
   - Installs dependencies
   - Creates .env template
   - Initializes database
   - Starts server
3. Edit .env with API credentials
4. Restart server
```

---

## Performance

### Query Times

| Operation | Time |
|-----------|------|
| Search item (10 records) | <10ms |
| Full database scan | <500ms |
| BigQuery fetch (27k rows) | ~5-10s |
| Database append (27k rows) | ~2-5s |

### File Sizes

| File | Size |
|------|------|
| SQLite database | ~50 MB (27k items, 5 dates each) |
| BigQuery partition | ~50 MB per month |
| Index overhead | ~5 MB |

---

## Backup & Recovery

### Backup SQLite Database

```bash
# Windows
copy read_rates.db read_rates_backup_2026-06-19.db

# Or use scheduled task to backup weekly
```

### Restore from Backup

```bash
# Stop server
# Replace read_rates.db with backup
# Restart server
```

### Export to CSV

```bash
sqlite3 read_rates.db ".mode csv" ".output data.csv" "SELECT * FROM read_rates;"
```

---

## Troubleshooting

### "read_rates.db not found"

**Cause:** Database not initialized

**Fix:**
```bash
python db.py
```

### "ModuleNotFoundError: google.cloud"

**Cause:** Google Cloud library not installed

**Fix:**
```bash
pip install google-cloud-bigquery
```

### "BigQuery connection failed"

**Cause:** Credentials invalid or network issue

**Check:**
- Project ID is correct
- Service account has BigQuery access
- Network can reach BigQuery API
- Google Cloud credentials are configured

### Database locked error

**Cause:** Multiple processes writing simultaneously

**Fix:**
- Don't run sync while users are searching
- Or wait for in-progress queries to finish

---

## Architecture Diagram

```
┌─────────────────┐
│  Users/Browsers │
│   (Search)      │
└────────┬────────┘
         │
         v
┌─────────────────┐       ┌──────────────────┐
│   FastAPI App   │──────>│  SQLite Database │
│  (main.py)      │       │  (read_rates.db) │
└─────────────────┘       └────────┬─────────┘
         ^                          │
         │                          │
         └──────────────────────────┘
         (Load & cache)
         
         
Optional Google Cloud Sync:

┌──────────────────────┐
│ Google Cloud BigQuery│
│  (gcs_sync.py)       │
└──────────┬───────────┘
           │
      (Query)
           │
           v
┌──────────────────────┐
│ Fetch new rows since │
│  last_sync_date      │
└──────────┬───────────┘
           │
      (Append)
           │
           v
┌─────────────────────────────┐
│  SQLite (read_rates.db)      │
│  Partitioned by ACL_INSERT_  │
│  DATE for efficient syncing  │
└─────────────────────────────┘
```

---

## Future Enhancements

- [ ] Real-time BigQuery streaming insert
- [ ] Automatic daily sync (scheduler)
- [ ] Data compression (old partitions)
- [ ] Read replicas for high-concurrency
- [ ] Time-series optimization

---

## Document Info

**Version:** 1.0  
**Last Updated:** June 2026  
**Database Format:** SQLite 3  
**Python Version:** 3.10+
