# UNLOADER FEATURE SPECIFICATION

## Overview
New server/client pair for unloader door monitoring with BigQuery data source and ICC Drop department band display logic.

---

## Architecture

### Server (Port 8060)
- **Data Source:** BigQuery `wmt-ambient-centeng.6068_Engineering.DAR_DELIVERIES_CACHE`
- **Cache Strategy:** Incremental updates (only new deliveries)
- **MDM Integration:** Pull catalog GTIN + images for problematic items
- **Cache Location:** `L:\Engineering\DAR Docktag Cards\cache_data_unloader\`

### Client (Port 8061)
- **Display:** Rolodex view filtered by door range (default: 430-450)
- **View Modes:** Simple (default) and Dev toggle
- **Special Logic:** ICC Drop items show department bands instead of images

---

## BigQuery Integration

### Table
```
wmt-ambient-centeng.6068_Engineering.DAR_DELIVERIES_CACHE
```

### Key Fields
- `delivery_nbr` - Delivery identifier
- `trailer_nbr` - Trailer identifier
- `trailer_status_desc` - **CRITICAL** (e.g., "ICC Drop")
- `door_number` - Unloader door (filter 430-450)
- `mds_fam_id` - Item identifier
- `estimated_unknown_cases` - Unknown case count
- `estimated_bad_cases` - Bad case count
- `estimated_good_cases` - Good case count
- `avg_read_rate` - Item performance percentage

### Query Example
```sql
SELECT 
  delivery_nbr,
  trailer_nbr,
  trailer_status_desc,
  door_number,
  mds_fam_id,
  estimated_unknown_cases,
  estimated_bad_cases,
  estimated_good_cases,
  avg_read_rate
FROM `wmt-ambient-centeng.6068_Engineering.DAR_DELIVERIES_CACHE`
WHERE door_number BETWEEN 430 AND 450
  AND delivery_date >= CURRENT_DATE() - 7
ORDER BY delivery_nbr, mds_fam_id
```

---

## ICC Drop Department Band Logic

### Condition
Display department band **INSTEAD OF** product image when:
1. `TRAILER_STATUS_DESC == "ICC Drop"` **AND**
2. Item is problematic (low read rate, needs MDM pull) **AND**
3. MDM data includes department information

### Implementation
```python
def should_show_department_band(item_data):
    """Determine if department band should replace image."""
    trailer_status = item_data.get('trailer_status_desc', '')
    is_problematic = item_data.get('avg_read_rate', 100) < 85
    has_mdm_data = item_data.get('supplier_dept') is not None
    
    return (
        trailer_status == "ICC Drop" 
        and is_problematic 
        and has_mdm_data
    )
```

### Department Band Display
- **3 Bands:** Dept # | Category | Item Description
- **Colors:** From `reference/department_bands.json`
- **Same as ACL Import Items:** Reuse existing `get_department_band()` function

---

## Cache Structure

### Folders
```
L:\Engineering\DAR Docktag Cards\cache_data_unloader\
├── deliveries\          (Delivery-level cache)
│   ├── delivery_12345678.json
│   └── delivery_87654321.json
├── items\               (MDM item data)
│   ├── mdm_550508254.json
│   └── mdm_678810598.json
├── trailers\            (Trailer aggregations)
│   └── trailer_summary_430_450.json
└── logs\                (Application logs)
    ├── unloader_server_20260728.log
    └── unloader_client_20260728.log
```

### Delivery Cache Format
```json
{
  "delivery_nbr": "12345678",
  "trailer_nbr": "ABC123",
  "trailer_status_desc": "ICC Drop",
  "door_number": 435,
  "items": [
    {
      "mds_fam_id": "550508254",
      "avg_read_rate": 72.5,
      "estimated_bad_cases": 45,
      "estimated_good_cases": 120,
      "estimated_unknown_cases": 10,
      "supplier_dept": "02",
      "item_name": "Sample Item",
      "image_url": "https://...",
      "catalog_gtin": "12345678901234"
    }
  ],
  "cached_at": "2026-07-28T14:30:00Z"
}
```

---

## Client Display

### Simple View (Default)
- Door number header
- Delivery card with trailer status badge
- Item rolodex (auto-scroll, 2 items per page)
- Performance indicators (color-coded)
- Product images **OR** department bands (ICC Drop logic)
- Case count summaries

### Dev View (Toggle)
- All Simple View content **PLUS:**
- MDS family IDs
- Exact read rate percentages
- Trailer status description
- Cache timestamps
- Door number details

### Door Range Filter
- **Default:** 430-450 (20 doors)
- **Future:** URL parameter `?doors=430-450`
- **Future:** .env configuration `UNLOADER_DOOR_START=430` / `UNLOADER_DOOR_END=450`

---

## Startup Scripts

### RUN_UNLOADER.bat
```batch
@echo off
title Unloader Server (Port 8060)
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python scripts\unloader_server.py
pause
```

### RUN_UNLOADER_CLIENT.bat
```batch
@echo off
title Unloader Client (Port 8061)
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python scripts\unloader_client.py
pause
```

### KILL.bat (Updated)
Add ports 8060 and 8061 to kill list:
```batch
REM Kill Unloader processes
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8060" ^| find "LISTENING"') do taskkill /F /PID %%a
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8061" ^| find "LISTENING"') do taskkill /F /PID %%a
```

---

## Key Differences from ACL App

| Feature | ACL App (8050/8051) | Unloader App (8060/8061) |
|---------|---------------------|---------------------------|
| **Data Source** | Informix + ABIA API | BigQuery cached table |
| **Update Strategy** | Real-time Informix queries | Incremental BQ pulls |
| **Filter** | ACL lanes (acl1/acl2/acl3) | Door range (430-450) |
| **Special Logic** | Import PO → dept bands | ICC Drop → dept bands |
| **Cache Location** | `cache_data/` | `cache_data_unloader/` |
| **Background Worker** | ABIA API polling | BQ scheduled queries |

---

## Implementation Phases

### Phase 1: Server Core
- [ ] Create `scripts/unloader_server.py`
- [ ] Implement BigQuery connection
- [ ] Build incremental cache logic
- [ ] Set up MDM integration
- [ ] Create cache folder structure
- [ ] Add logging

### Phase 2: ICC Drop Logic
- [ ] Implement `should_show_department_band()` function
- [ ] Integrate with MDM data fetch
- [ ] Test with ICC Drop deliveries
- [ ] Verify department band rendering

### Phase 3: Client Display
- [ ] Create `scripts/unloader_client.py`
- [ ] Build door filter logic (430-450)
- [ ] Implement rolodex display
- [ ] Add dev view toggle
- [ ] Integrate department band display

### Phase 4: Startup & Testing
- [ ] Create `RUN_UNLOADER.bat`
- [ ] Create `RUN_UNLOADER_CLIENT.bat`
- [ ] Update `KILL.bat` for ports 8060/8061
- [ ] End-to-end testing
- [ ] Performance validation

---

## Testing Checklist

- [ ] BQ query returns delivery data with `TRAILER_STATUS_DESC`
- [ ] Incremental cache only pulls NEW deliveries
- [ ] MDM API successfully fetches catalog GTIN and images
- [ ] ICC Drop items display department bands (not images)
- [ ] Non-ICC Drop items display product images
- [ ] Door filter (430-450) works correctly
- [ ] Dev view toggle shows/hides technical details
- [ ] Server starts on port 8060
- [ ] Client starts on port 8061
- [ ] KILL.bat terminates all 4 processes (8050/8051/8060/8061)
- [ ] Cache persists across server restarts
- [ ] Logs write to `cache_data_unloader/logs/`

---

## Future Enhancements

1. **Dynamic Door Range:** URL param or .env config
2. **Trailer Status Filters:** Show only ICC Drop, or all statuses
3. **Historical View:** Query past deliveries from BQ
4. **Alerts:** Notify when bad cases exceed threshold
5. **Export:** Download delivery reports as PDF/Excel
6. **Multi-DC Support:** Query different DCs (6068, 7064, etc.)

---

## Notes

- **Isolation:** Completely separate from ACL app for testing
- **Reuse Code:** Share MDM functions, cache manager, department band logic
- **BigQuery Costs:** Consider caching strategy to minimize queries
- **Network Drive:** Same L: drive access requirements as ACL app
- **Department Bands:** Only for ICC Drop + problematic items (not all imports)
