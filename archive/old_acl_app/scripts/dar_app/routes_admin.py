"""Routes: /api/admin/set-database-path, /api/admin/sync-bigquery, /admin."""
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from dar_app.read_rates_data import get_database_path

router = APIRouter()

@router.post("/api/admin/set-database-path")
async def set_database_path(request: Request):
    """Update the DATABASE_PATH in .env file."""
    try:
        # Get path from JSON body
        body = await request.json()
        new_path = body.get("path")
        
        if not new_path:
            return JSONResponse({"status": "error", "message": "No path provided"}, status_code=400)
        
        # Update .env file
        env_path = Path(".env")
        env_content = ""
        
        # Read existing .env
        if env_path.exists():
            with open(env_path, "r") as f:
                lines = f.readlines()
                for line in lines:
                    if not line.startswith("DATABASE_PATH="):
                        env_content += line
        
        # Add/update DATABASE_PATH
        env_content += f"DATABASE_PATH={new_path}\n"
        
        # Write back
        with open(env_path, "w") as f:
            f.write(env_content)
        
        # Update .env in current process
        os.environ["DATABASE_PATH"] = new_path
        
        print(f"[ADMIN] Database path updated to: {new_path}")
        return JSONResponse({"status": "success", "message": f"Database path set to {new_path}", "path": new_path})
    
    except Exception as e:
        print(f"[ERROR] Failed to update database path: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.post("/api/admin/sync-bigquery")
async def sync_bigquery():
    print("\n" + "="*70)
    print("[SYNC] BigQuery sync started")
    print("="*70)
    
    try:
        from gcs_sync import GoogleCloudSync
        from db import get_database_stats
        import sqlite3
        from datetime import datetime, timedelta
        
        print("[SYNC] Step 1: Initializing GoogleCloudSync...")
        sync = GoogleCloudSync()
        init_result = sync.initialize()
        if not init_result:
            print("[ERROR] Failed to initialize BigQuery")
            return JSONResponse({"status": "error", "message": "BigQuery init failed"}, status_code=400)
        print("[OK] BigQuery initialized")
        
        print("[SYNC] Step 2: Getting database stats...")
        stats = get_database_stats()
        max_date = stats.get('max_date', '2024-01-01')
        total_rows = stats.get('total_rows', 0)
        print(f"[OK] DB: {total_rows} rows, max_date={max_date}")
        
        print("[SYNC] Step 3: Connecting to database...")
        conn = sqlite3.connect("read_rates.db")
        cursor = conn.cursor()
        print("[OK] Connected")
        
        print("[SYNC] Step 4: Reading existing dates...")
        cursor.execute("SELECT DISTINCT acl_insert_date FROM read_rates ORDER BY acl_insert_date")
        existing_dates = {row[0] for row in cursor.fetchall()}
        print(f"[OK] Found {len(existing_dates)} dates in database")
        
        print("[SYNC] Step 5: Calculating missing dates...")
        if max_date and max_date != 'N/A':
            last_date = datetime.strptime(max_date, '%Y-%m-%d')
        else:
            last_date = datetime(2024, 1, 1)
        
        today = datetime.now()
        missing_dates = []
        current = last_date + timedelta(days=1)
        while current <= today:
            date_str = current.strftime('%Y-%m-%d')
            if date_str not in existing_dates:
                missing_dates.append(date_str)
            current += timedelta(days=1)
        
        print(f"[OK] Found {len(missing_dates)} missing dates")
        if missing_dates:
            print(f"     Range: {missing_dates[0]} to {missing_dates[-1]}")
        
        if not missing_dates:
            print("[OK] Database is current, no missing dates")
            conn.close()
            return JSONResponse({"status": "success", "message": "No missing dates", "rows_appended": 0, "dates_synced": 0})
        
        print(f"[SYNC] Step 6: Building BigQuery query...")
        print(f"[DEBUG] Missing {len(missing_dates)} dates to sync: {missing_dates}")
        # Use double quotes for BigQuery date strings
        dates_list = ", ".join([f'"{d}"' for d in missing_dates])
        query = f"""SELECT acl_insert_date, ts_date, mds_fam_id, slot_id, acl_event_cnt, acl_null_cnt, acl_bypass_cnt, good_read_cnt_null, good_read_cnt_bypass, item_num_read_cnt_null, item_num_read_cnt_bypass, item1_desc, pick_type_code, vnpk_gtin_t
            FROM `wmt-ambient-centeng.6068_Engineering.ACL_READ_RATE`
            WHERE PICK_TYPE_CODE NOT IN ('DPAL', 'LBSS')
            AND acl_insert_date IN ({dates_list})"""
        print("[OK] Query built with filter: PICK_TYPE_CODE NOT IN ('DPAL', 'LBSS')")
        print(f"[DEBUG] Query: {query[:250]}...")
        
        print(f"[SYNC] Step 7: Executing BigQuery query (may take 10-30 seconds)...")
        query_job = sync.client.query(query)
        results = query_job.result()
        print("[OK] Query executed")
        
        # Convert results to list to check length
        results_list = list(results)
        print(f"[IMPORTANT] BigQuery returned {len(results_list)} rows")
        
        if len(results_list) == 0:
            print(f"[WARNING] NO ROWS returned from BigQuery!")
            print(f"[WARNING] This means the 14 missing dates have NO data matching:")
            print(f"[WARNING]   WHERE PICK_TYPE_CODE NOT IN ('DPAL', 'LBSS')")
            print(f"[WARNING] The dates may only contain DPAL or LBSS pick types.")
            conn.close()
            return JSONResponse({"status": "success", "message": "BigQuery returned 0 rows (dates may only have DPAL/LBSS pick types)", "rows_appended": 0, "dates_synced": len(missing_dates)})
        
        print(f"[SYNC] Step 8: Processing and inserting {len(results_list)} rows...")
        inserted = 0
        total = 0
        duplicates = 0
        errors = 0
        
        for row in results_list:
            total += 1
            
            # Print details of first row
            if total == 1:
                print(f"[DEBUG] First row from BigQuery:")
                print(f"        acl_insert_date: {row.acl_insert_date}")
                print(f"        mds_fam_id: {row.mds_fam_id}")
                print(f"        acl_event_cnt: {row.acl_event_cnt}")
                print(f"        acl_null_cnt: {row.acl_null_cnt}")
            
            try:
                insert_sql = '''INSERT OR IGNORE INTO read_rates (acl_insert_date, ts_date, mds_fam_id, slot_id, acl_event_cnt, acl_null_cnt, acl_bypass_cnt, good_read_cnt_null, good_read_cnt_bypass, item_num_read_cnt_null, item_num_read_cnt_bypass, item1_desc, pick_type_code, vnpk_gtin_t) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
                insert_values = (str(row.acl_insert_date), str(row.ts_date) if row.ts_date else None, str(row.mds_fam_id), str(row.slot_id) if row.slot_id else None, int(row.acl_event_cnt) if row.acl_event_cnt else 0, int(row.acl_null_cnt) if row.acl_null_cnt else 0, int(row.acl_bypass_cnt) if row.acl_bypass_cnt else 0, int(row.good_read_cnt_null) if row.good_read_cnt_null else 0, int(row.good_read_cnt_bypass) if row.good_read_cnt_bypass else 0, int(row.item_num_read_cnt_null) if row.item_num_read_cnt_null else 0, int(row.item_num_read_cnt_bypass) if row.item_num_read_cnt_bypass else 0, str(row.item1_desc) if row.item1_desc else None, str(row.pick_type_code) if row.pick_type_code else None, str(row.vnpk_gtin_t) if row.vnpk_gtin_t else None)
                cursor.execute(insert_sql, insert_values)
                
                if cursor.rowcount > 0:
                    inserted += 1
                else:
                    duplicates += 1
                
                if total % 500 == 0:
                    print(f"     Processed {total} rows: {inserted} new, {duplicates} duplicates")
            
            except Exception as e:
                errors += 1
                print(f"[ERROR] Row {total} failed: {str(e)}")
                if errors <= 3:  # Only print first 3 errors
                    print(f"        Values: {insert_values}")
        
        print(f"\n[RESULTS]")
        print(f"  BigQuery returned: {total} rows")
        print(f"  Missing dates queried: {len(missing_dates)} dates ({missing_dates[0]} to {missing_dates[-1]})")
        print(f"  Inserted: {inserted} NEW rows")
        print(f"  Duplicates (already exist): {duplicates}")
        print(f"  Errors: {errors}")
        
        print("[SYNC] Step 9: Committing...")
        conn.commit()
        conn.close()
        print("[OK] Committed")
        
        print("\n" + "="*70)
        print(f"[SUCCESS] Sync complete: {len(missing_dates)} dates, {inserted} rows")
        print("="*70 + "\n")
        
        return JSONResponse({"status": "success", "message": f"Synced {len(missing_dates)} dates, {inserted} rows", "rows_appended": inserted, "dates_synced": len(missing_dates)})
    
    except Exception as e:
        print(f"\n[ERROR] Sync failed: {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*70 + "\n")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/admin", response_class=HTMLResponse)
async def admin_page():
    # Get database path from configuration
    db_path = get_database_path()
    
    try:
        from db import get_database_stats
        stats = get_database_stats()
        total = stats.get('total_rows', 0)
        items = stats.get('unique_items', 0)
        min_d = stats.get('min_date', 'N/A')
        max_d = stats.get('max_date', 'N/A')
    except Exception as e:
        total = items = 'Error loading'
        min_d = max_d = str(e)
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodePuppy DAR - Admin</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <div class="max-w-2xl mx-auto p-6">
        <h1 class="text-3xl font-bold text-blue-600 mb-6">CodePuppy DAR - Admin</h1>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Database Status</h2>
            <table class="w-full text-sm">
                <tr class="border-b"><td class="py-2 font-semibold">Total Rows:</td><td class="py-2 text-right text-blue-600 font-bold">{total}</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">Unique Items:</td><td class="py-2 text-right text-blue-600 font-bold">{items}</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">Min Date:</td><td class="py-2 text-right font-mono">{min_d}</td></tr>
                <tr><td class="py-2 font-semibold">Max Date:</td><td class="py-2 text-right font-mono">{max_d}</td></tr>
            </table>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Database Path Settings</h2>
            <p class="text-sm text-gray-600 mb-3">Current path: <span class="font-mono bg-gray-100 px-2 py-1 text-blue-600">{db_path}</span></p>
            <div class="flex gap-2 mb-4">
                <input type="file" id="dbFileInput" accept=".db,.sqlite,.sqlite3" class="flex-1 px-3 py-2 border rounded text-sm" />
                <button onclick="updateDatabasePathFromFile()" class="px-4 py-2 bg-purple-600 text-white rounded font-semibold hover:bg-purple-700">Set From File</button>
            </div>
            <div id="path-status" class="text-sm hidden"></div>
            <p class="text-xs text-gray-500 mt-2">Click "Set From File" to browse and select your database file (.db, .sqlite, .sqlite3)</p>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">BigQuery Sync</h2>
            <p class="text-sm text-gray-600 mb-4">Synchronize missing dates from Google BigQuery ACL_READ_RATE table</p>
            <button onclick="syncBigQuery()" class="px-6 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700">Sync Missing Dates from BigQuery</button>
            <div id="sync-status" class="mt-4 text-sm hidden"></div>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">System Info</h2>
            <table class="w-full text-sm">
                <tr class="border-b"><td class="py-2 font-semibold">Database Path:</td><td class="py-2 text-right font-mono text-blue-600">{db_path}</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">Database Type:</td><td class="py-2 text-right">SQLite (read_rates.db)</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">API:</td><td class="py-2 text-right">MDM Item API</td></tr>
                <tr class="border-b"><td class="py-2 font-semibold">BigQuery:</td><td class="py-2 text-right font-mono text-sm">ACL_READ_RATE</td></tr>
                <tr><td class="py-2 font-semibold">Auth Method:</td><td class="py-2 text-right">MDM_API_KEY (.env)</td></tr>
            </table>
            <div class="mt-4 p-3 bg-blue-50 border-l-4 border-blue-400 rounded">
                <p class="text-xs text-blue-700"><strong>To change database path:</strong> Set <code>DATABASE_PATH</code> in .env (relative or absolute path)</p>
            </div>
        </div>
        
        <div class="bg-blue-50 border-l-4 border-blue-600 p-4 mb-6 rounded">
            <h3 class="font-bold text-blue-900 mb-2">Developer Tips</h3>
            <ul class="text-sm text-blue-800 space-y-1">
                <li>Press F12 to open Browser Console → Check [EXTRACT] logs</li>
                <li>Network tab → See MDM API responses in real-time</li>
                <li>See <strong>BROWSER_CONSOLE_DEBUGGING.md</strong> in the repo for detailed guide</li>
            </ul>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Scheduler.walmart.com</h2>
            <p class="text-sm text-gray-600 mb-4">Automatic authentication via PingFederate SSO</p>
            <div hx-get="/diagnostics/scheduler" hx-trigger="load" hx-swap="innerHTML"></div>
        </div>
        
        <div class="flex gap-3">
            <a href="/diagnostics/informix" class="inline-block px-4 py-2 bg-orange-600 text-white rounded font-semibold hover:bg-orange-700">Informix Connection Test</a>
            <a href="/" class="inline-block px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700">Back to Search</a>
        </div>
    </div>
    
    <script>
        async function updateDatabasePathFromFile() {{
            const fileInput = document.getElementById('dbFileInput');
            const file = fileInput.files[0];
            const statusDiv = document.getElementById('path-status');
            
            if (!file) {{
                statusDiv.classList.remove('hidden');
                statusDiv.innerHTML = '<div class="text-red-600">Please select a database file</div>';
                return;
            }}
            
            // Get full path from file
            const newPath = file.webkitRelativePath || file.name;
            
            statusDiv.classList.remove('hidden');
            statusDiv.innerHTML = '<div class="text-blue-600">Updating...</div>';
            
            try {{
                const response = await fetch('/api/admin/set-database-path', {{\n                    method: 'POST',\n                    headers: {{'Content-Type': 'application/json'}},\n                    body: JSON.stringify({{path: file.name, full_path: newPath}})\n                }});
                
                const result = await response.json();
                
                if (result.status === 'success') {{
                    statusDiv.innerHTML = `<div class="text-green-600 font-semibold">✓ Database path updated!</div>
                        <p class="text-sm text-gray-600 mt-2">New path: <code class="bg-gray-100 px-2">${{result.path}}</code></p>
                        <p class="text-sm text-gray-600">Refresh the page to apply changes.</p>`;
                    setTimeout(() => {{
                        location.reload();
                    }}, 2000);
                }} else {{
                    statusDiv.innerHTML = `<div class="text-red-600">✗ Error: ${{result.message}}</div>`;
                }}
            }} catch (err) {{
                statusDiv.innerHTML = `<div class="text-red-600">✗ Error: ${{err.message}}</div>`;
            }}
        }}
        
        async function syncBigQuery() {{
            const statusDiv = document.getElementById('sync-status');
            statusDiv.classList.remove('hidden');
            statusDiv.innerHTML = '<div class="text-blue-600">Syncing... please wait</div>';
            
            try {{
                const response = await fetch('/api/admin/sync-bigquery', {{\n                    method: 'POST',\n                    headers: {{'Content-Type': 'application/json'}}\n                }});
                
                const result = await response.json();
                
                if (result.status === 'success') {{
                    statusDiv.innerHTML = `
                        <div class="text-green-600 font-semibold">✓ Sync Complete</div>
                        <div class="text-sm text-gray-700 mt-2">
                            Rows appended: ${{result.rows_appended}}<br>
                            Dates synced: ${{result.dates_synced}}<br>
                            <a href="/admin" class="text-blue-600 underline mt-2 inline-block">Refresh page</a>
                        </div>
                    `;
                }} else {{
                    statusDiv.innerHTML = `<div class="text-red-600">✗ Error: ${{result.message}}</div>`;
                }}
            }} catch (err) {{
                statusDiv.innerHTML = `<div class="text-red-600">✗ Error: ${{err.message}}</div>`;
            }}
        }}
    </script>
    <script src="https://unpkg.com/htmx.org"></script>
</body>
</html>"""
