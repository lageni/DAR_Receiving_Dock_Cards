"""
ACL Freight Awareness - CLIENT VIEWER

Lightweight FastAPI app that ONLY READS from cache.
Server writes to cache, client displays cached data.

Port: 8001
Cache: L:\\Engineering\\DAR Docktag Cards\\cache_data
"""

import json
import time
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from cache_manager import get_cache_manager

app = FastAPI(title="ACL Viewer Client")

# Shared cache location
CACHE_DIR = Path(r"L:\Engineering\DAR Docktag Cards\cache_data")


@app.get("/", response_class=HTMLResponse)
async def home():
    """ACL Viewer home page with tabs"""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACL Freight Awareness - Live Monitor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .pulse-slow { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    </style>
</head>
<body class="bg-gray-50">
    <div class="container mx-auto p-6 max-w-7xl">
        <div class="bg-gradient-to-r from-blue-600 to-blue-800 text-white rounded-lg shadow-lg p-6 mb-6">
            <h1 class="text-4xl font-bold mb-2">ACL Freight Awareness - Live Monitor</h1>
            <p class="text-blue-100">Real-time cache viewer • Auto-refresh every 30s • No server load</p>
            <div class="mt-4 flex items-center space-x-4">
                <span class="px-3 py-1 bg-white/20 rounded text-sm font-semibold" id="lastUpdate">Loading...</span>
                <span class="px-3 py-1 bg-green-400 text-green-900 rounded text-sm font-semibold pulse-slow" id="refreshIndicator">Auto-refresh: 30s</span>
                <span class="px-3 py-1 bg-purple-400 text-purple-900 rounded text-sm font-semibold">Client Mode</span>
            </div>
        </div>

        <div class="bg-white rounded-lg shadow-lg mb-6">
            <div class="border-b border-gray-200">
                <nav class="flex space-x-8 px-6" aria-label="Tabs">
                    <button onclick="switchACL('acl1')" id="tab-acl1" class="acl-tab border-b-2 border-blue-500 py-4 px-1 text-center font-medium text-blue-600">ACL 1</button>
                    <button onclick="switchACL('acl2')" id="tab-acl2" class="acl-tab border-b-2 border-transparent py-4 px-1 text-center font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300">ACL 2</button>
                    <button onclick="switchACL('acl3')" id="tab-acl3" class="acl-tab border-b-2 border-transparent py-4 px-1 text-center font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300">ACL 3</button>
                </nav>
            </div>
        </div>

        <div id="contentArea">
            <div class="text-center py-12">
                <div class="inline-block h-12 w-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                <p class="mt-4 text-gray-600">Loading ACL data from cache...</p>
            </div>
        </div>

        <div class="mt-6 text-center text-gray-500 text-sm">
            <p>Cache Status: <span id="cacheStatus" class="font-semibold">Checking...</span></p>
            <p class="mt-2 text-xs">Client Port: 8001 (Read-Only) | Server Port: 8000 (Analysis)</p>
        </div>
    </div>

    <script>
        const CLIENT_URL = 'http://localhost:8001';
        let currentACL = 'acl1';
        let refreshInterval = null;
        let secondsUntilRefresh = 30;

        function switchACL(acl) {
            currentACL = acl;
            document.querySelectorAll('.acl-tab').forEach(tab => {
                tab.classList.remove('border-blue-500', 'text-blue-600');
                tab.classList.add('border-transparent', 'text-gray-500');
            });
            document.getElementById(`tab-${acl}`).classList.remove('border-transparent', 'text-gray-500');
            document.getElementById(`tab-${acl}`).classList.add('border-blue-500', 'text-blue-600');
            loadACLData(acl);
        }

        async function loadACLData(acl) {
            try {
                const response = await fetch(`${CLIENT_URL}/api/cache/${acl}`);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                renderACLData(acl, data);
                document.getElementById('cacheStatus').textContent = 'Connected';
                document.getElementById('cacheStatus').className = 'font-semibold text-green-600';
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('contentArea').innerHTML = `
                    <div class="bg-red-50 border-2 border-red-400 rounded-lg p-6 text-center">
                        <p class="text-red-800 font-bold text-lg">Cannot read cache</p>
                        <p class="text-red-700 mt-2">Make sure server is running and cache exists</p>
                        <p class="text-sm text-gray-600 mt-2">Error: ${error.message}</p>
                    </div>
                `;
                document.getElementById('cacheStatus').textContent = 'Error';
                document.getElementById('cacheStatus').className = 'font-semibold text-red-600';
            }
        }

        function renderACLData(acl, data) {
            const deliveries = data.deliveries || [];
            const lastUpdate = data.last_update || 'Unknown';
            
            document.getElementById('lastUpdate').textContent = `Last updated: ${lastUpdate}`;
            
            if (deliveries.length === 0) {
                document.getElementById('contentArea').innerHTML = `
                    <div class="bg-green-50 border-2 border-green-400 rounded-lg p-8 text-center">
                        <p class="text-green-800 font-bold text-2xl">No active deliveries in ${acl.toUpperCase()}</p>
                        <p class="text-green-700 mt-2">All clear!</p>
                    </div>
                `;
                return;
            }
            
            let html = '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">';
            
            deliveries.forEach(delivery => {
                const deliveryNum = delivery.delivery_number || 'Unknown';
                const station = delivery.station || 'Unknown';
                const problematicCount = delivery.problematic_count || 0;
                const problematicItems = delivery.problematic_items || [];
                
                let borderColor, headerBg, badgeBg;
                if (problematicCount === 0) {
                    borderColor = 'border-green-500';
                    headerBg = 'bg-gradient-to-r from-green-600 to-green-700';
                    badgeBg = 'bg-green-100 text-green-800';
                } else if (problematicCount < 5) {
                    borderColor = 'border-yellow-500';
                    headerBg = 'bg-gradient-to-r from-yellow-600 to-yellow-700';
                    badgeBg = 'bg-yellow-100 text-yellow-800';
                } else {
                    borderColor = 'border-red-500';
                    headerBg = 'bg-gradient-to-r from-red-600 to-red-700';
                    badgeBg = 'bg-red-100 text-red-800';
                }
                
                html += `
                    <div class="bg-white rounded-lg shadow-lg border-2 ${borderColor} overflow-hidden hover:shadow-xl transition">
                        <div class="${headerBg} text-white px-4 py-3">
                            <h3 class="font-bold text-lg">#${deliveryNum}</h3>
                            <p class="text-sm opacity-90">Station: ${station}</p>
                        </div>
                        <div class="p-4">
                            <div class="flex justify-between items-center mb-3">
                                <span class="text-sm text-gray-600">Problematic Items</span>
                                <span class="px-3 py-1 ${badgeBg} rounded-full text-sm font-bold">${problematicCount}</span>
                            </div>
                `;
                
                if (problematicItems.length > 0) {
                    html += '<div class="space-y-2">';
                    problematicItems.slice(0, 5).forEach(item => {
                        const perf = item.performance || 0;
                        const perfColor = perf < 50 ? 'text-red-600' : perf < 70 ? 'text-yellow-600' : 'text-orange-600';
                        html += `
                            <div class="text-xs bg-gray-50 p-2 rounded border">
                                <div class="flex justify-between">
                                    <span class="font-mono">${item.mds_fam_id || 'N/A'}</span>
                                    <span class="${perfColor} font-bold">${perf.toFixed(0)}%</span>
                                </div>
                                ${item.item_name ? `<div class="text-gray-600 mt-1 truncate">${item.item_name}</div>` : ''}
                            </div>
                        `;
                    });
                    html += '</div>';
                    if (problematicItems.length > 5) {
                        html += `<p class="text-xs text-gray-500 mt-2">+ ${problematicItems.length - 5} more</p>`;
                    }
                }
                
                html += `
                            <a href="http://localhost:8000/delivery-analysis?delivery=${deliveryNum}" target="_blank" class="mt-4 block w-full px-4 py-2 bg-blue-600 text-white rounded text-center font-semibold hover:bg-blue-700">
                                Full Analysis
                            </a>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            document.getElementById('contentArea').innerHTML = html;
        }

        function startAutoRefresh() {
            if (refreshInterval) clearInterval(refreshInterval);
            refreshInterval = setInterval(() => {
                loadACLData(currentACL);
                secondsUntilRefresh = 30;
            }, 30000);
            
            setInterval(() => {
                secondsUntilRefresh--;
                document.getElementById('refreshIndicator').textContent = `Auto-refresh: ${secondsUntilRefresh}s`;
                if (secondsUntilRefresh <= 0) secondsUntilRefresh = 30;
            }, 1000);
        }

        document.addEventListener('DOMContentLoaded', () => {
            loadACLData(currentACL);
            startAutoRefresh();
        });
    </script>
</body>
</html>'''


@app.get("/api/cache/{acl}")
async def get_acl_cache(acl: str):
    """Read ACL data from shared cache - FAST!"""
    try:
        cache = get_cache_manager()
        
        # Read from shared cache structure written by server
        cache_key = f"acl_{acl}_deliveries"
        cached_data = cache.get(cache_key, category="acl")
        
        if not cached_data:
            print(f"[CLIENT] No cache found for {acl}")
            return JSONResponse({
                "deliveries": [],
                "last_update": "Never",
                "status": "no_cache"
            })
        
        print(f"[CLIENT] Serving {len(cached_data.get('deliveries', []))} deliveries for {acl} from cache")
        
        return JSONResponse(cached_data)
        
    except Exception as e:
        print(f"[CLIENT] Error reading cache: {e}")
        return JSONResponse({
            "deliveries": [],
            "last_update": "Error",
            "status": "error",
            "error": str(e)
        }, status_code=500)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    cache_exists = CACHE_DIR.exists()
    return JSONResponse({
        "status": "healthy",
        "mode": "client",
        "port": 8001,
        "cache_accessible": cache_exists,
        "cache_path": str(CACHE_DIR)
    })


if __name__ == "__main__":
    import uvicorn
    print("[CLIENT] Starting ACL Viewer Client on port 8001...")
    print("[CLIENT] Reading from cache: L:\\Engineering\\DAR Docktag Cards\\cache_data")
    print("[CLIENT] Open browser: http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
