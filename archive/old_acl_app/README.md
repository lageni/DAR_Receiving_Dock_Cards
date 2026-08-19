# Archived: ACL Freight Awareness + Delivery Analysis app

This is the original CodePuppyDAR app (ports 8050/8051). It has been
**archived and is no longer the primary focus** - the Unloader Monitor
(ports 8060/8061/8062, see the repo root README) is now the main app.

This code is frozen here for reference / in case it's needed again. It is
**not actively maintained** and not wired into `KILL.bat` anymore.

## Structure

Identical to how it worked at the repo root before archiving:
- `RUN.bat` - Server startup/setup (port 8050)
- `RUN_CLIENT.bat` - Client viewer (port 8051)
- `scripts/main.py` - FastAPI app entrypoint (imports from `scripts/dar_app/`)
- `scripts/dar_app/` - Route handlers, data access, PDF/HTML rendering
- `scripts/client_viewer.py`, `acl_background_worker.py`, `delivery_analysis.py`,
  `batch_report.py`, `cache_manager.py`, `db.py`, `informix_connect.py`,
  `sync_bigquery.py` - supporting modules
- `scripts/debug/` - one-off debugging scripts written while chasing specific bugs

## If you need to run this again

1. Copy or symlink this `archive/old_acl_app/` folder's contents back to
   wherever you want to run it from (it expects its own `.venv`, `.env`,
   and `read_rates.db` alongside `RUN.bat`, same as before archiving).
2. `department_bands.py` was split into a standalone top-level module
   (`scripts/department_bands.py`, used by the active Unloader app) but this
   archived copy keeps its own `scripts/dar_app/department_bands.py` so it
   stays fully self-contained and doesn't reach outside this folder.
