# ACL Freight Awareness Redesign - Integration Guide

## Status

- Background worker created: `acl_background_worker.py`
- Main.py backup: `_archive/main_backup_before_redesign.py`

## What This Does

1. Background worker runs continuously, analyzing all deliveries every 2 minutes
2. Landing page (/) shows ACL1 by default with instant-load grid layout
3. Old home page moved to /item-analysis
4. /acl1, /acl2, /acl3 endpoints with multi-column cards showing ALL deliveries edge-to-edge
5. Zero wait time - data is pre-analyzed and cached

## Integration Steps

Due to Windows command line limitations, manual integration needed.

### Step 1: Add Import

In `main.py`, after line:
```python
from cache_manager import get_cache_manager
```

Add:
```python
from acl_background_worker import acl_monitor
```

### Step 2: Add Startup Event

After `app = FastAPI(title="CodePuppy DAR")`, add:

```python
@app.on_event("startup")
async def startup_event():
    print("[STARTUP] Starting ACL background monitor...")
    await acl_monitor.start()
    print("[STARTUP] ACL monitor running")
```

### Step 3: Move Old Home

Change:
```python
@app.get("/", response_class=HTMLResponse)
async def root():
```

To:
```python
@app.get("/item-analysis", response_class=HTMLResponse)
async def item_analysis_page():
```

### Step 4: Remove Old ACL Section

Find and DELETE everything from:
```python
# ========== ACL FREIGHT AWARENESS ==========
```

To (but not including):
```python
@app.get("/delivery-analysis", response_class=HTMLResponse)
```

### Step 5: Add New ACL Endpoints

See `_docs/ACL_NEW_ENDPOINTS.py` for complete code to paste before delivery-analysis endpoint.

## Testing

1. Run: `python main.py`
2. Navigate to: http://localhost:8000
3. Should auto-redirect to http://localhost:8000/acl1
4. Deliveries should load instantly from cache
5. Click ACL 2, ACL 3 tabs

## Troubleshooting

If background worker fails:
- Check console for `[ACL-WORKER]` messages
- Worker updates every 120 seconds
- SSL errors mean verify=False is needed (already added)
