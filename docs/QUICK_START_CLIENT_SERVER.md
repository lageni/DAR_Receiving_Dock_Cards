# QUICK START - ACL Freight Awareness

## SETUP (One-Time)

1. Make sure you have both files:
   - `RUN.bat` - Server (analysis)
   - `RUN_CLIENT.bat` - Client (viewer)

2. Server and client use shared cache:
   ```
   L:\Engineering\DAR Docktag Cards\cache_data
   ```

---

## STARTING THE SYSTEM

### STEP 1: Start Server (Analysis)

**Open Terminal 1:**
```bash
cd C:\Users\d0h0pf7\Documents\puppy_workspace\CodePuppyDAR
RUN.bat
```

**Wait for:**
```
[STARTUP] ACL monitor running in background
INFO: Uvicorn running on http://0.0.0.0:8000
[ACL-WORKER] Starting monitoring cycle...
```

**Server is ready!**

---

### STEP 2: Start Client (Viewer)

**Open Terminal 2 (NEW terminal!):**
```bash
cd C:\Users\d0h0pf7\Documents\puppy_workspace\CodePuppyDAR
RUN_CLIENT.bat
```

**Wait for:**
```
[CLIENT] Starting ACL Viewer Client on port 8001...
INFO: Uvicorn running on http://0.0.0.0:8001
```

**Client is ready!**

---

### STEP 3: Open in Browser

**For Viewing (Recommended):**
```
http://localhost:8001
```

**For Analysis:**
```
http://localhost:8000/delivery-analysis
```

---

## WHAT YOU'LL SEE

### First 2 Minutes
- Client shows: "No cache" or "All clear"
- **This is normal!** Server is analyzing

### After 2 Minutes
- Server: `[ACL-WORKER] Wrote X deliveries to disk cache`
- Client: Auto-refreshes and shows deliveries

### Every 2 Minutes
- Server re-analyzes ACLs
- Updates cache
- Client auto-refreshes (30 seconds)

---

## USAGE

### Single User
1. Start SERVER
2. Wait 2 minutes
3. Start CLIENT
4. Use client for viewing

### Multiple Viewers
1. Start SERVER (once)
2. Multiple people start CLIENT (on their machines)
3. All clients read same cache
4. Zero impact on server!

---

## TROUBLESHOOTING

### "No cache" in client
- **Wait 2 minutes** after starting server
- Check server logs for: `[ACL-WORKER] Wrote X deliveries`

### "Cannot connect"
- Make sure server is running (RUN.bat)
- Check port 8000 is not blocked

### Server slow/stuck
- **This is fixed!** New optimizations:
  - SQL pre-filtering
  - Analysis caching
  - Non-blocking startup

### Want to see raw cache?
```bash
cd "L:\Engineering\DAR Docktag Cards\cache_data\acl"
dir
type acl_acl1_deliveries.json
```

---

## STOPPING

### Stop Client
- Press `Ctrl+C` in client terminal
- Or just close the terminal

### Stop Server
- Press `Ctrl+C` in server terminal
- Cache persists (safe to restart!)

---

## PORTS

- **8000** = Server (analysis, heavy processing)
- **8001** = Client (viewer, lightweight)

Both can run on same machine (different terminals)

---

## LOGS TO WATCH

### Server Logs (Good Signs)
```
[ACL-WORKER] Starting monitoring cycle...
[ACL-WORKER] ACL1: Analyzing delivery 10917836...
[ACL-WORKER] Delivery 10917836: Using CACHED analysis (instant!)
[SQL-optimized: Loaded 20 problematic items in 2.5s]
[ACL-WORKER] ACL1: Wrote 15 deliveries to disk cache for client
```

### Client Logs (Good Signs)
```
[CLIENT] Serving 15 deliveries for acl1 from cache
```

---

Last Updated: 2026-07-15
Status: READY TO USE
