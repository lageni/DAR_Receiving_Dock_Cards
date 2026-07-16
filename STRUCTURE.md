# PROJECT STRUCTURE

```
CodePuppyDAR/
│
├── README.md                      # Quick start & navigation
├── SERVER_README.md               # Complete server documentation
├── CLIENT_README.md               # Complete client documentation
│
├── RUN.bat                        # Start server (port 8000)
├── RUN_CLIENT.bat                 # Start client (port 8001)
│
├── main.py                        # Server application (195 KB)
├── client_viewer.py               # Client application (12 KB)
├── acl_background_worker.py       # Background ACL monitor
│
├── delivery_analysis.py           # Delivery analysis logic
├── batch_report.py                # Batch processing
├── informix_connect.py            # Database connection
├── db.py                          # Database utilities
├── cache_manager.py               # Shared cache module
│
├── .env                           # Environment variables (not in git)
├── .env.example                   # Environment template
├── .gitignore                     # Git ignore rules
├── pyproject.toml                 # Dependencies
├── uv.lock                        # Lock file
│
├── department_bands.json          # Department data
├── mdm_item_api_response_example.json  # MDM API example
│
├── docs/                          # Archived documentation
│   ├── ACL_DEBUGGING_GUIDE.md
│   ├── CLIENT_SERVER_ARCHITECTURE.md
│   ├── OPTIMIZATION_SUMMARY.md
│   └── QUICK_START_CLIENT_SERVER.md
│
├── scripts/                       # Helper scripts
│   ├── diagnose_acl_cache.py
│   └── optimized_read_rates.py
│
├── _archive/                      # Old backup files
├── _docs/                         # Old documentation
├── _installers/                   # Installer files
│
├── .venv/                         # Virtual environment (not in git)
├── __pycache__/                   # Python cache (not in git)
└── codepuppydar.egg-info/         # Package info
```

---

## DOCUMENTATION HIERARCHY

### Primary (Read These First)
1. **README.md** - Start here for quick overview
2. **SERVER_README.md** - Everything about server (port 8000)
3. **CLIENT_README.md** - Everything about client (port 8001)

### Secondary (Reference)
- **docs/** - Archived technical details, debugging guides, optimization notes

### Helper Scripts
- **scripts/diagnose_acl_cache.py** - Debug ACL cache issues
- **scripts/optimized_read_rates.py** - Reference implementation

---

## FILE SIZES

| File | Size | Purpose |
|------|------|---------|
| main.py | 195 KB | Server application |
| uv.lock | 564 KB | Dependencies lock |
| client_viewer.py | 12 KB | Client application |
| acl_background_worker.py | 13 KB | Background worker |
| delivery_analysis.py | 11 KB | Analysis logic |
| SERVER_README.md | 10 KB | Server docs |
| CLIENT_README.md | 10 KB | Client docs |

---

## KEY DIRECTORIES

### `/docs/`
Archived documentation for reference:
- Architecture details
- Optimization history
- Debugging procedures
- Historical quick-start guides

### `/scripts/`
Diagnostic and helper utilities:
- Cache diagnostics
- Performance profiling
- One-off migrations

### `/_archive/`
Old code backups (pre-refactor)

### `/_docs/`
Old markdown documentation (pre-consolidation)

---

## CLEAN COMMIT HISTORY

Recent commits show the evolution:
```
4590d02 - Housekeeping: consolidate docs, organize structure, cleanup files
0b614cc - Add quick start guide for client/server architecture
8429d44 - Add client/server architecture: separate viewer app
a808c45 - Add ACL debugging tools and documentation
5c5c603 - Add extensive debug logging to ACL worker
d249e45 - CRITICAL: Replace one-by-one batch loading with SQL pre-filtering
49f6c46 - Fix: Make ACL worker truly non-blocking
051ea15 - Fix ACL worker: check analysis cache before re-analyzing
bdaea02 - Optimize: SQL-level filtering + cache problematic items analysis
dc81989 - Fix PDF endpoint, remove table, optimize load_read_rates
```

---

## SIMPLIFIED NAVIGATION

**Want to run the server?**  
→ Read [SERVER_README.md](SERVER_README.md)

**Want to run the client?**  
→ Read [CLIENT_README.md](CLIENT_README.md)

**Need help debugging?**  
→ Check [docs/ACL_DEBUGGING_GUIDE.md](docs/ACL_DEBUGGING_GUIDE.md)

**Want technical details?**  
→ Browse [docs/](docs/) folder

**Need diagnostics?**  
→ Run `python scripts/diagnose_acl_cache.py`

---

Last Updated: 2026-07-15  
Structure: Client/Server with Shared Cache  
Documentation: Consolidated into 2 primary files
