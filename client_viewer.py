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
    <div class="container mx-auto p-2 max-w-full">
        <div class="bg-gradient-to-r from-blue-600 to-blue-800 text-white rounded-lg shadow-lg p-4 mb-4">
            <h1 class="text-4xl font-bold mb-2">ACL Freight Awareness - Live Monitor</h1>
            <p class="text-blue-100">Real-time cache viewer • Auto-refresh every 30s • No server load</p>
            <div class="mt-4 flex items-center space-x-4">
                <span class="px-3 py-1 bg-white/20 rounded text-sm font-semibold" id="lastUpdate">Loading...</span>
                <span class="px-3 py-1 bg-green-400 text-green-900 rounded text-sm font-semibold pulse-slow" id="refreshIndicator">Auto-refresh: 30s</span>
                <span class="px-3 py-1 bg-purple-400 text-purple-900 rounded text-sm font-semibold">Client Mode</span>
            </div>
        </div>

        <div class="bg-white rounded-lg shadow-lg mb-4">
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
            
            // Sort deliveries by total bad cases (highest first)
            const sortedDeliveries = [...deliveries].sort((a, b) => {
                const aBadCases = (a.problematic_items || []).reduce((sum, item) => sum + (item.bad_cases || 0), 0);
                const bBadCases = (b.problematic_items || []).reduce((sum, item) => sum + (item.bad_cases || 0), 0);
                return bBadCases - aBadCases;
            });
            
            // Check if we need to update (compare delivery numbers)
            const existingDeliveries = Array.from(document.querySelectorAll('.delivery-section')).map(el => el.dataset.delivery);
            const newDeliveryNumbers = sortedDeliveries.map(d => d.delivery_number);
            
            const needsFullRedraw = JSON.stringify(existingDeliveries.sort()) !== JSON.stringify(newDeliveryNumbers.sort());
            
            if (needsFullRedraw) {
                console.log('[CLIENT] Full redraw needed - delivery list changed');
                buildFullDisplay(acl, sortedDeliveries);
            } else {
                console.log('[CLIENT] Updating existing deliveries in place');
                updateExistingDeliveries(sortedDeliveries);
            }
        }
        function buildFullDisplay(acl, deliveries) {
            let html = '<div class="flex gap-4 overflow-x-auto pb-4" style="scroll-snap-type: x mandatory;">';
            
            deliveries.forEach((delivery, deliveryIndex) => {
                const deliveryNum = delivery.delivery_number || 'Unknown';
                const station = delivery.station || 'Unknown';
                const problematicCount = delivery.problematic_count || 0;
                const problematicItems = delivery.problematic_items || [];
                const isCached = delivery.cached !== false;
                const isPending = delivery.status === 'pending_analysis';
                const totalBadCases = problematicItems.reduce((sum, item) => sum + (item.bad_cases || 0), 0);
                
                let borderColor, headerBg, badgeBg, statusText;
                
                if (isPending) {
                    borderColor = 'border-gray-400';
                    headerBg = 'bg-gradient-to-r from-gray-500 to-gray-600';
                    badgeBg = 'bg-gray-100 text-gray-800';
                    statusText = 'Pending Analysis';
                } else if (problematicCount === 0) {
                    borderColor = 'border-green-500';
                    headerBg = 'bg-gradient-to-r from-green-600 to-green-700';
                    badgeBg = 'bg-green-100 text-green-800';
                    statusText = 'All Clear';
                } else if (problematicCount < 5) {
                    borderColor = 'border-yellow-500';
                    headerBg = 'bg-gradient-to-r from-yellow-600 to-yellow-700';
                    badgeBg = 'bg-yellow-100 text-yellow-800';
                    statusText = 'Minor Issues';
                } else {
                    borderColor = 'border-red-500';
                    headerBg = 'bg-gradient-to-r from-red-600 to-red-700';
                    badgeBg = 'bg-red-100 text-red-800';
                    statusText = 'Needs Attention';
                }
                
                html += `
                    <div class="delivery-section flex-shrink-0 bg-white rounded-lg shadow border-2 ${borderColor} overflow-hidden" 
                         style="width: 400px; scroll-snap-align: start; height: 600px; display: flex; flex-direction: column;"
                         data-delivery="${deliveryNum}" data-item-count="${problematicItems.length}">
                        <div class="${headerBg} text-white px-3 py-2">
                            <div class="flex justify-between items-center">
                                <h3 class="font-bold text-lg">#${deliveryNum}</h3>
                                <span class="text-sm">${station}</span>
                            </div>
                            <div class="flex justify-between items-center mt-1">
                                <span class="text-xs">${statusText}</span>
                                <span class="px-2 py-0.5 ${badgeBg} rounded-full text-xs font-bold">${problematicCount} items</span>
                            </div>
                            ${totalBadCases > 0 ? `<div class="text-sm font-bold mt-1 text-red-200">${totalBadCases} total bad cases</div>` : ''}
                        </div>
                        <div class="carousel-container flex-1 overflow-hidden relative" data-current-index="0">
                `;
                
                if (isPending) {
                    html += `
                        <div class="h-full flex flex-col items-center justify-center p-4">
                            <p class="text-gray-600 font-semibold mb-2">Pending Analysis</p>
                            <p class="text-xs text-gray-500">Click to analyze</p>
                            <a href="http://localhost:8000/delivery-analysis?delivery=${deliveryNum}" target="_blank" 
                               class="mt-4 px-4 py-2 bg-gray-600 text-white rounded text-sm font-semibold hover:bg-gray-700">
                                Analyze Now
                            </a>
                        </div>
                    `;
                } else if (problematicItems.length > 0) {
                    html += '<div class="carousel-items">';
                    problematicItems.forEach((item, itemIndex) => {
                        const perf = item.performance || 0;
                        const badCases = item.bad_cases || 0;
                        const imageUrl = item.image_url || '';
                        const recommendation = item.recommendation || '';
                        const colorHex = item.color_hex || '#6b7280';
                        const dimensions = item.vnpk_length && item.vnpk_width && item.vnpk_height ? 
                            `${item.vnpk_length}x${item.vnpk_width}x${item.vnpk_height}` : '';
                        
                        html += `
                            <div class="carousel-item h-full p-4" style="display: ${itemIndex === 0 ? 'flex' : 'none'}; flex-direction: column; justify-content: center;">
                                <div class="text-center mb-4">
                                    ${imageUrl ? `<img src="${imageUrl}" class="w-32 h-32 object-cover rounded mx-auto mb-2" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27100%27 height=%27100%27%3E%3Crect fill=%27%23ddd%27 width=%27100%27 height=%27100%27/%3E%3Ctext x=%2750%25%27 y=%2750%25%27 text-anchor=%27middle%27 dy=%27.3em%27 fill=%27%23999%27 font-size=%2712%27%3ENo Img%3C/text%3E%3C/svg%3E'" />` : ''}
                                    <div class="font-mono text-lg font-bold mb-1">${item.mds_fam_id || 'N/A'}</div>
                                    ${item.item_name ? `<div class="text-gray-800 text-base font-bold mb-2">${item.item_name}</div>` : ''}
                                    <div class="text-5xl font-bold my-3" style="color: ${colorHex};">${perf.toFixed(0)}%</div>
                                </div>
                                <div class="text-center space-y-2">
                                    ${badCases > 0 ? `<div class="text-red-600 font-bold text-xl">${badCases} bad cases</div>` : ''}
                                    ${dimensions ? `<div class="text-gray-600 text-sm">${dimensions}</div>` : ''}
                                    ${recommendation ? `<div class="mt-3 text-base font-bold px-3 py-2 rounded" style="background-color: ${colorHex}20; color: ${colorHex};">${recommendation}</div>` : ''}
                                </div>
                                <div class="mt-4 text-center text-sm text-gray-500">
                                    Item ${itemIndex + 1} of ${problematicItems.length}
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                } else {
                    html += `
                        <div class="h-full flex items-center justify-center p-4">
                            <p class="text-lg text-gray-500 italic">All items OK</p>
                        </div>
                    `;
                }
                
                html += `
                        </div>
                        <div class="p-3 border-t">
                            <a href="http://localhost:8000/delivery-analysis?delivery=${deliveryNum}" target="_blank" 
                               class="block w-full px-3 py-2 bg-blue-600 text-white rounded text-center text-sm font-semibold hover:bg-blue-700">
                                Full Analysis
                            </a>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            document.getElementById('contentArea').innerHTML = html;
            
            // Start auto-scroll for each delivery
            startAutoScroll();
        }

        function updateExistingDeliveries(deliveries) {
            // Just update counts/badges without full redraw
            deliveries.forEach(delivery => {
                const section = document.querySelector(`.delivery-section[data-delivery="${delivery.delivery_number}"]`);
                if (section) {
                    const newItemCount = (delivery.problematic_items || []).length;
                    const oldItemCount = parseInt(section.dataset.itemCount || '0');
                    if (newItemCount !== oldItemCount) {
                        console.log(`[CLIENT] Delivery ${delivery.delivery_number} changed: ${oldItemCount} -> ${newItemCount} items`);
                        // Full redraw if item count changed
                        buildFullDisplay(currentACL, deliveries);
                        return;
                    }
                }
            });
        }

        let autoScrollIntervals = [];

        function startAutoScroll() {
            // Clear existing intervals
            autoScrollIntervals.forEach(interval => clearInterval(interval));
            autoScrollIntervals = [];
            
            // Start auto-scroll for each delivery carousel
            document.querySelectorAll('.carousel-container').forEach(container => {
                const items = container.querySelectorAll('.carousel-item');
                if (items.length <= 1) return; // No need to scroll if only 1 item
                
                let currentIndex = 0;
                
                const interval = setInterval(() => {
                    // Hide current item
                    items[currentIndex].style.display = 'none';
                    
                    // Move to next item
                    currentIndex = (currentIndex + 1) % items.length;
                    
                    // Show next item
                    items[currentIndex].style.display = 'flex';
                    
                    container.dataset.currentIndex = currentIndex;
                }, 5000); // Change item every 5 seconds
                
                autoScrollIntervals.push(interval);
            });
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
    """Fetch deliveries from ABIA, check server's analysis cache"""
    import httpx
    
    try:
        # Step 1: Call ABIA API to get active deliveries (same as server does)
        abia_url = f"https://abia.wal-mart.com/aclaware/fetchData/?dc=6068&acl={acl}"
        
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.get(abia_url)
            response.raise_for_status()
            abia_data = response.json()
        
        raw_deliveries = abia_data.get('data', [])
        print(f"[CLIENT] ABIA API: Fetched {len(raw_deliveries)} active deliveries for {acl}")
        
        # Step 2: For each delivery, check if server has analyzed it
        cache = get_cache_manager()
        enriched_deliveries = []
        
        for item in raw_deliveries:
            delivery_number = item.get('delivery', '')
            station = item.get('station', 'Unknown')
            
            if not delivery_number:
                continue
            
            # Check server's analysis cache
            analysis_key = f"analysis_{delivery_number}"
            cached_analysis = cache.get(analysis_key, category="deliveries")
            
            if cached_analysis:
                # Server has analyzed this delivery!
                problematic_items = cached_analysis.get('problematic_items_data', [])
                problematic_details = cached_analysis.get('problematic_details', {})
                
                print(f"[CLIENT-DEBUG] Delivery {delivery_number}: Found {len(problematic_items)} problematic items in cache")
                
                # Build display data
                display_items = []
                for prob_item in problematic_items[:10]:  # Top 10
                    mds_id = prob_item.get('mds_fam_id', '')
                    acl_details = prob_item.get('acl_details', problematic_details.get(str(mds_id), {}))
                    
                    display_item = {
                        'mds_fam_id': mds_id,
                        'item_name': prob_item.get('item_name', ''),
                        'performance': acl_details.get('avg_perf', 0),
                        'bad_cases': acl_details.get('bad_cases', 0),
                        'recommendation': acl_details.get('recommendation', ''),
                        'color_hex': acl_details.get('color_hex', '#6b7280'),
                        'image_url': prob_item.get('image_url', ''),
                        'vnpk_length': prob_item.get('vnpk_length', ''),
                        'vnpk_width': prob_item.get('vnpk_width', ''),
                        'vnpk_height': prob_item.get('vnpk_height', '')
                    }
                    display_items.append(display_item)
                    print(f"[CLIENT-DEBUG]   Item {mds_id}: perf={display_item['performance']}%, bad_cases={display_item['bad_cases']}, img={bool(display_item['image_url'])}")
                
                enriched_deliveries.append({
                    'delivery_number': delivery_number,
                    'station': station,
                    'problematic_count': len(problematic_items),
                    'problematic_items': display_items,
                    'cached': True
                })
                print(f"[CLIENT-DEBUG] Delivery {delivery_number}: Added to enriched list (problematic_count={len(problematic_items)})")
            else:
                # Not analyzed yet - show as pending
                print(f"[CLIENT-DEBUG] Delivery {delivery_number}: No analysis cache found - showing as pending")
                enriched_deliveries.append({
                    'delivery_number': delivery_number,
                    'station': station,
                    'problematic_count': 0,
                    'problematic_items': [],
                    'cached': False,
                    'status': 'pending_analysis'
                })
        
        print(f"[CLIENT] Enriched {len(enriched_deliveries)} deliveries for {acl} (checked analysis cache)")
        
        result = {
            "deliveries": enriched_deliveries,
            "last_update": datetime.now().isoformat(),
            "status": "ready"
        }
        
        # DEBUG: Log the result being sent
        print(f"[CLIENT-DEBUG] Returning {len(enriched_deliveries)} deliveries to frontend")
        
        return JSONResponse(result)
        
    except Exception as e:
        print(f"[CLIENT] Error fetching/enriching {acl}: {e}")
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
