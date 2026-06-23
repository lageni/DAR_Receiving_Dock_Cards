@app.get("/admin/debug", response_class=HTMLResponse)
async def admin_debug():
    """Debug page for testing Google Cloud sync and database status"""
    stats = get_database_stats()
    sync_status = get_sync_status()
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodePuppyDAR - Admin Debug</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
</head>
<body class="bg-gray-100">
    <script>
        // Define all functions FIRST before HTML that uses them
        let itemChart = null;
        let itemSortAsc = true;
        
        async function testItemLookup() {{
            const itemId = document.getElementById('testItemId').value;
            if (!itemId) {{ alert('Enter an Item ID'); return; }}
            document.getElementById('testResult').innerHTML = 'Loading...';
            try {{
                const response = await fetch(`/api/test/item-lookup?item_id=${{itemId}}`);
                const data = await response.json();
                if (data.records === 0) {{
                    document.getElementById('testResult').innerHTML = `<div class="bg-yellow-50 p-3 rounded border border-yellow-300">No ACL records found for item ${{itemId}}</div>`;
                    document.getElementById('itemLookupTable').style.display = 'none';
                    document.getElementById('itemChartContainer').style.display = 'none';
                }} else {{
                    document.getElementById('testResult').innerHTML = `<div class="bg-green-50 p-3 rounded border border-green-300"><strong>Found:</strong> ${{data.records}} records<br><strong>Range:</strong> ${{data.min_date}} to ${{data.max_date}}</div>`;
                    populateItemTable(data.rows);
                    document.getElementById('itemLookupTable').style.display = 'block';
                    drawItemChart(data.rows);
                    document.getElementById('itemChartContainer').style.display = 'block';
                }}
            }} catch (e) {{
                document.getElementById('testResult').innerHTML = `<div class="bg-red-50 p-3 rounded border border-red-300">Error: ${{e.message}}</div>`;
            }}
        }}
        
        function populateItemTable(rows) {{
            const tbody = document.getElementById('itemTableBody');
            tbody.innerHTML = '';
            rows.forEach(row => {{
                const tr = document.createElement('tr');
                tr.innerHTML = `<td class="border p-2">${{row.date}}</td><td class="border p-2 text-right">${{row.null_pct.toFixed(2)}}%</td><td class="border p-2 text-right">${{row.event_cnt}}</td><td class="border p-2 text-right">${{row.null_cnt}}</td>`;
                tbody.appendChild(tr);
            }});
        }}
        
        function toggleItemTableSort() {{
            itemSortAsc = !itemSortAsc;
            const rows = Array.from(document.querySelectorAll('#itemTableBody tr'));
            rows.sort((a, b) => itemSortAsc ? a.cells[0].textContent.localeCompare(b.cells[0].textContent) : b.cells[0].textContent.localeCompare(a.cells[0].textContent));
            const tbody = document.getElementById('itemTableBody');
            tbody.innerHTML = '';
            rows.forEach(row => tbody.appendChild(row));
        }}
        
        function drawItemChart(rows) {{
            const ctx = document.getElementById('itemChart').getContext('2d');
            if (itemChart) itemChart.destroy();
            const dates = rows.map(r => r.date);
            const nullPcts = rows.map(r => r.null_pct);
            itemChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: dates,
                    datasets: [{{
                        label: 'Null Read %',
                        data: nullPcts,
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        tension: 0.1,
                        fill: true
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{display: true, position: 'top'}},
                        title: {{display: true, text: 'ACL Null Read % Over Time'}}
                    }},
                    scales: {{y: {{beginAtZero: true, max: 100}}}}
                }}
            }});
        }}
        
        async function testGCSConnection() {{
            document.getElementById('gcsResult').innerHTML = 'Testing connection...';
            try {{
                const response = await fetch('/api/admin/gcs-init', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{project_id: 'wmt-ambient-centeng', dataset_id: '6068_Engineering', table_id: 'ACL_READ_RATE'}})
                }});
                const data = await response.json();
                if (data.status === 'success') {{
                    document.getElementById('gcsResult').innerHTML = `<div class="bg-green-50 p-3 rounded border border-green-300">BigQuery connection initialized successfully!</div>`;
                }} else {{
                    document.getElementById('gcsResult').innerHTML = `<div class="bg-red-50 p-3 rounded border border-red-300">${{data.message}}</div>`;
                }}
            }} catch (e) {{
                document.getElementById('gcsResult').innerHTML = `<div class="bg-red-50 p-3 rounded border border-red-300">Error: ${{e.message}}</div>`;
            }}
        }}
        
        async function syncFromGCS() {{
            document.getElementById('gcsResult').innerHTML = 'Syncing...';
            try {{
                const response = await fetch('/api/admin/gcs-sync', {{method: 'POST'}});
                const data = await response.json();
                if (data.status === 'success') {{
                    document.getElementById('gcsResult').innerHTML = `<div class="bg-green-50 p-3 rounded border border-green-300"><strong>Sync Complete!</strong><br>Inserted: ${{data.inserted}}<br>Skipped: ${{data.skipped}}<br>Errors: ${{data.errors}}</div>`;
                }} else {{
                    document.getElementById('gcsResult').innerHTML = `<div class="bg-red-50 p-3 rounded border border-red-300">${{data.message}}</div>`;
                }}
            }} catch (e) {{
                document.getElementById('gcsResult').innerHTML = `<div class="bg-red-50 p-3 rounded border border-red-300">Error: ${{e.message}}</div>`;
            }}
        }}
        
        async function checkMissingPartitions() {{
            const daysBack = document.getElementById('daysBackInput').value;
            document.getElementById('missingPartitionsResult').innerHTML = 'Checking...';
            try {{
                const response = await fetch(`/api/admin/missing-partitions?days_back=${{daysBack}}`);
                const data = await response.json();
                if (data.missing_dates && data.missing_dates.length > 0) {{
                    const datesList = data.missing_dates.map(d => `<code class="bg-yellow-100 px-2 py-1 rounded">${{d}}</code>`).join(' ');
                    document.getElementById('missingPartitionsResult').innerHTML = `<div class="bg-yellow-50 p-3 rounded border border-yellow-300"><strong>Missing: ${{data.days_missing}} dates<br>Range: ${{data.date_range}}<br>${{datesList}}</strong></div>`;
                }} else {{
                    document.getElementById('missingPartitionsResult').innerHTML = `<div class="bg-green-50 p-3 rounded border border-green-300">All current!</div>`;
                }}
            }} catch (e) {{
                document.getElementById('missingPartitionsResult').innerHTML = `<div class="bg-red-50 p-3 rounded border border-red-300">Error: ${{e.message}}</div>`;
            }}
        }}
        
        async function autoSyncMissingDates() {{
            const daysBack = document.getElementById('daysBackInput').value;
            document.getElementById('missingPartitionsResult').innerHTML = 'Syncing...';
            try {{
                const response = await fetch('/api/admin/sync-specific-dates', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{days_back: parseInt(daysBack)}})
                }});
                const data = await response.json();
                if (data.status === 'success') {{
                    document.getElementById('missingPartitionsResult').innerHTML = `<div class="bg-green-50 p-3 rounded border border-green-300"><strong>Synced!</strong> Inserted: ${{data.inserted}}</div>`;
                }} else {{
                    document.getElementById('missingPartitionsResult').innerHTML = `<div class="bg-red-50 p-3 rounded border border-red-300">Error: ${{data.message}}</div>`;
                }}
            }} catch (e) {{
                document.getElementById('missingPartitionsResult').innerHTML = `<div class="bg-red-50 p-3 rounded border border-red-300">Error: ${{e.message}}</div>`;
            }}
        }}
        
        async function viewErrorLogs() {{
            document.getElementById('errorLogsResult').innerHTML = 'Loading...';
            try {{
                const response = await fetch('/api/admin/error-logs');
                const data = await response.json();
                if (data.status === 'success' && data.logs.length > 0) {{
                    let html = `<table class="w-full text-xs border-collapse border"><tr class="bg-gray-100"><th class="border p-2">Time</th><th class="border p-2">Type</th><th class="border p-2">Message</th></tr>`;
                    data.logs.slice(0, 20).forEach(log => {{
                        html += `<tr><td class="border p-2">${{log.timestamp.substring(11, 19)}}</td><td class="border p-2">${{log.error_type}}</td><td class="border p-2">${{log.message}}</td></tr>`;
                    }});
                    html += `</table>`;
                    document.getElementById('errorLogsResult').innerHTML = html;
                }} else {{
                    document.getElementById('errorLogsResult').innerHTML = `<div class="bg-green-50 p-3 rounded border border-green-300">No errors</div>`;
                }}
            }} catch (e) {{
                document.getElementById('errorLogsResult').innerHTML = `<div class="bg-red-50 p-3 rounded border border-red-300">Error: ${{e.message}}</div>`;
            }}
        }}
        
        async function clearErrorLogs() {{
            if (!confirm('Delete all error logs?')) return;
            try {{
                const response = await fetch('/api/admin/clear-error-logs', {{method: 'POST'}});
                const data = await response.json();
                document.getElementById('errorLogsResult').innerHTML = `<div class="bg-green-50 p-3 rounded border border-green-300">${{data.message}}</div>`;
            }} catch (e) {{
                document.getElementById('errorLogsResult').innerHTML = `<div class="bg-red-50 p-3 rounded border border-red-300">Error: ${{e.message}}</div>`;
            }}
        }}
    </script>

    <div class="max-w-6xl mx-auto p-6">
        <h1 class="text-3xl font-bold text-blue-600 mb-6">CodePuppyDAR - Admin Debug</h1>
        
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <div class="bg-white p-6 rounded-lg border shadow">
                <h2 class="text-xl font-bold mb-4">Database Status</h2>
                <table class="w-full text-sm">
                    <tr><td class="py-2 font-semibold">Total Rows:</td><td class="py-2 text-right text-blue-600 font-bold">{stats['total_rows']:,}</td></tr>
                    <tr><td class="py-2 font-semibold">Unique Items:</td><td class="py-2 text-right text-blue-600 font-bold">{stats['unique_items']:,}</td></tr>
                    <tr><td class="py-2 font-semibold">Min Date:</td><td class="py-2 text-right font-mono">{stats['min_date']}</td></tr>
                    <tr><td class="py-2 font-semibold">Max Date:</td><td class="py-2 text-right font-mono">{stats['max_date']}</td></tr>
                </table>
            </div>
            <div class="bg-white p-6 rounded-lg border shadow">
                <h2 class="text-xl font-bold mb-4">Test Item Lookup</h2>
                <div class="flex gap-2 mb-2">
                    <input type="text" id="testItemId" placeholder="Item ID (e.g., 659608850)" class="flex-1 px-3 py-2 border rounded">
                    <button onclick="testItemLookup()" class="px-4 py-2 bg-blue-600 text-white rounded font-semibold">Test</button>
                </div>
                <div id="testResult" class="text-sm"></div>
                <div id="itemLookupTable" style="display:none;" class="mt-3">
                    <button onclick="toggleItemTableSort()" class="text-xs px-2 py-1 bg-gray-200 rounded">Sort</button>
                    <table id="itemDataTable" class="w-full text-xs border-collapse border mt-2">
                        <thead class="bg-gray-100"><tr><th class="border p-2">Date</th><th class="border p-2">Null %</th><th class="border p-2">Events</th><th class="border p-2">Nulls</th></tr></thead>
                        <tbody id="itemTableBody"></tbody>
                    </table>
                </div>
                <div id="itemChartContainer" style="display:none;" class="mt-3">
                    <canvas id="itemChart" style="max-height: 300px;"></canvas>
                </div>
            </div>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Google Cloud Sync</h2>
            <p class="text-xs text-gray-500 mb-2">wmt-ambient-centeng | 6068_Engineering | ACL_READ_RATE</p>
            <button onclick="testGCSConnection()" class="px-4 py-2 bg-green-600 text-white rounded font-semibold">Test Connection</button>
            <button onclick="syncFromGCS()" class="ml-2 px-4 py-2 bg-purple-600 text-white rounded font-semibold">Sync (7 Days)</button>
            <div id="gcsResult" class="mt-3 text-sm"></div>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Missing Partitions</h2>
            <div class="flex gap-2">
                <input type="number" id="daysBackInput" value="7" min="1" max="90" class="w-20 px-3 py-2 border rounded">
                <button onclick="checkMissingPartitions()" class="px-4 py-2 bg-orange-600 text-white rounded font-semibold">Check</button>
                <button onclick="autoSyncMissingDates()" class="px-4 py-2 bg-red-600 text-white rounded font-semibold">Auto-Sync</button>
            </div>
            <div id="missingPartitionsResult" class="mt-3 text-sm"></div>
        </div>
        
        <div class="bg-white p-6 rounded-lg border shadow mb-6">
            <h2 class="text-xl font-bold mb-4">Error Logs</h2>
            <button onclick="viewErrorLogs()" class="px-4 py-2 bg-blue-600 text-white rounded font-semibold">Load Logs</button>
            <button onclick="clearErrorLogs()" class="ml-2 px-4 py-2 bg-red-600 text-white rounded font-semibold">Clear</button>
            <div id="errorLogsResult" class="mt-3 text-sm"></div>
        </div>
        
        <a href="/" class="inline-block px-4 py-2 bg-blue-600 text-white rounded font-semibold">Back to Search</a>
    </div>
</body>
</html>"""
