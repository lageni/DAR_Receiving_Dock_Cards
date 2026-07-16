# ACL Freight Awareness - CodePuppy DAR

Client/Server architecture for real-time ACL monitoring and delivery analysis.

---

## QUICK START

### Server (Analysis Engine)
```bash
RUN.bat
```
**Port:** 8000  
**See:** [SERVER_README.md](SERVER_README.md)

### Client (Viewer)
```bash
RUN_CLIENT.bat
```
**Port:** 8001  
**See:** [CLIENT_README.md](CLIENT_README.md)

---

## ARCHITECTURE

- **Server:** Analyzes deliveries, writes to shared cache (L: drive)
- **Client:** Reads cache, displays data, auto-refreshes
- **Cache:** Shared JSON files on L:\Engineering\DAR Docktag Cards\cache_data

---

## DOCUMENTATION

- **[SERVER_README.md](SERVER_README.md)** - Server setup, endpoints, optimizations
- **[CLIENT_README.md](CLIENT_README.md)** - Client setup, features, troubleshooting
- **[docs/](docs/)** - Archived documentation and technical details
- **[scripts/](scripts/)** - Diagnostic and helper scripts

---

## FILES

### Core
- `main.py` - Server application
- `client_viewer.py` - Client application
- `acl_background_worker.py` - Background ACL monitor
- `cache_manager.py` - Shared cache module
- `delivery_analysis.py` - Analysis logic

### Config
- `.env` - Environment variables
- `pyproject.toml` - Dependencies

### Startup
- `RUN.bat` - Start server
- `RUN_CLIENT.bat` - Start client

---

## SUPPORT

**Issues?** Check the troubleshooting sections in:
- [SERVER_README.md](SERVER_README.md#troubleshooting)
- [CLIENT_README.md](CLIENT_README.md#troubleshooting)

**Diagnostics:** Run `python scripts/diagnose_acl_cache.py`

---

Last Updated: 2026-07-15
