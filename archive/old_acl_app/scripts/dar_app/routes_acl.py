"""Routes: "/", "/{acl}", "/api/acl-rendered/{acl}" - the ACL freight monitor views."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from acl_background_worker import acl_monitor

router = APIRouter()

@router.get("/")
async def root():
    """Redirect home to ACL1"""
    return RedirectResponse(url="/acl1")


@router.get("/{acl}", response_class=HTMLResponse)
async def acl_page(acl: str):
    """ACL Freight Awareness - Grid layout with instant loads from background cache"""
    
    if acl not in ["acl1", "acl2", "acl3"]:
        raise HTTPException(status_code=404, detail="ACL must be acl1, acl2, or acl3")
    
    def tab_class(tab_acl):
        if tab_acl == acl:
            return "px-6 py-3 bg-blue-600 text-white font-bold rounded-t border-b-4 border-blue-800"
        return "px-6 py-3 bg-gray-200 text-gray-700 font-semibold rounded-t hover:bg-gray-300 cursor-pointer"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACL Freight Awareness - {acl.upper()}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        /* Edge-to-edge grid layout */
        .delivery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }}
        
        @media (min-width: 1024px) {{
            .delivery-grid {{
                grid-template-columns: repeat(4, 1fr);
            }}
        }}
        
        @media (min-width: 768px) and (max-width: 1023px) {{
            .delivery-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <main class="container mx-auto p-4">
        <!-- Header -->
        <div class="bg-white rounded-lg shadow-md p-6 mb-4">
            <h1 class="text-3xl font-bold text-blue-700 mb-2"> ACL Freight Awareness</h1>
            <p class="text-gray-600">Real-time monitoring • Background analysis every 2 minutes • Instant page loads</p>
        </div>

        <!-- ACL Tabs -->
        <div class="flex gap-2 mb-4">
            <a href="/acl1" class="{tab_class('acl1')}">ACL 1</a>
            <a href="/acl2" class="{tab_class('acl2')}">ACL 2</a>
            <a href="/acl3" class="{tab_class('acl3')}">ACL 3</a>
        </div>

        <!-- Delivery Grid - Auto-refresh every 60s -->
        <div 
            id="delivery-grid" 
            class="delivery-grid"
            hx-get="/api/acl-rendered/{acl}"
            hx-trigger="load, every 60s"
            hx-swap="innerHTML"
        >
            <!-- Loading spinner -->
            <div class="col-span-full text-center py-12">
                <div class="animate-spin inline-block w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full"></div>
                <p class="mt-4 text-gray-600 font-semibold">Loading {acl.upper()} deliveries from cache...</p>
            </div>
        </div>

        <!-- Navigation -->
        <div class="mt-6 flex gap-4">
            <a href="/item-analysis" class="px-4 py-2 bg-gray-600 text-white rounded font-semibold hover:bg-gray-700">
                 Item Analysis
            </a>
            <a href="/delivery-analysis" class="px-4 py-2 bg-gray-600 text-white rounded font-semibold hover:bg-gray-700">
                 Delivery Analysis
            </a>
        </div>
    </main>
</body>
</html>
"""


@router.get("/api/acl-rendered/{acl}", response_class=HTMLResponse)
async def get_acl_rendered(acl: str):
    """Return pre-analyzed HTML from background worker cache - INSTANT load!"""
    try:
        # Get cached data from background worker
        cached_data = acl_monitor.get_acl_data(acl)
        
        print(f"[ACL-ENDPOINT-DEBUG] {acl}: Received cached_data: {cached_data is not None}")
        
        if not cached_data:
            print(f"[ACL-ENDPOINT-DEBUG] {acl}: No cached_data! Returning initialization message")
            return f"""
            <div class="col-span-full bg-yellow-50 border-2 border-yellow-400 rounded-lg p-6 text-center">
                <p class="text-yellow-800 font-bold text-lg">No cached data available for {acl.upper()}</p>
                <p class="text-yellow-700 mt-2">Background worker may still be initializing. Please wait 2 minutes.</p>
                <p class="text-xs text-gray-600 mt-2">Status: {cached_data.get('status') if cached_data else 'null'}</p>
            </div>
            """
        
        deliveries = cached_data.get('deliveries', [])
        last_updated = cached_data.get('last_update', 'Unknown')
        status = cached_data.get('status', 'unknown')
        
        print(f"[ACL-ENDPOINT-DEBUG] {acl}: Found {len(deliveries)} deliveries, status={status}, last_update={last_updated}")
        
        if not deliveries:
            print(f"[ACL-ENDPOINT-DEBUG] {acl}: No deliveries in list! Status={status}")
            return f"""
            <div class="col-span-full bg-green-50 border-2 border-green-400 rounded-lg p-6 text-center">
                <p class="text-green-800 font-bold text-lg">No active deliveries in {acl.upper()}</p>
                <p class="text-green-700 mt-2">All clear! Updated: {last_updated}</p>
                <p class="text-xs text-gray-600 mt-2">Status: {status}</p>
            </div>
            """
        
        # Build delivery cards
        cards_html = []
        for delivery in deliveries:
            delivery_num = delivery.get('delivery_number', 'Unknown')
            station = delivery.get('station', 'Unknown')
            
            # Access nested analysis data
            analysis = delivery.get('analysis', {})
            problematic_count = analysis.get('problematic_count', 0)
            problematic_items = analysis.get('problematic_items', [])[:10]  # Top 10
            
            # Color coding based on issue count
            if problematic_count == 0:
                border_color = "border-green-500"
                header_color = "bg-gradient-to-r from-green-600 to-green-700"
                badge_color = "bg-green-100 text-green-800"
                status_emoji = ""
            elif problematic_count < 5:
                border_color = "border-yellow-500"
                header_color = "bg-gradient-to-r from-yellow-600 to-yellow-700"
                badge_color = "bg-yellow-100 text-yellow-800"
                status_emoji = ""
            else:
                border_color = "border-red-500"
                header_color = "bg-gradient-to-r from-red-600 to-red-700"
                badge_color = "bg-red-100 text-red-800"
                status_emoji = ""
            
            # Build item list HTML
            items_html = []
            if problematic_items:
                for item in problematic_items:
                    perf = item.get('performance', 0)
                    if perf < 50:
                        perf_badge = f"<span class='bg-red-200 text-red-900 px-2 py-1 rounded text-xs font-bold'>{perf:.1f}%</span>"
                    elif perf < 70:
                        perf_badge = f"<span class='bg-orange-200 text-orange-900 px-2 py-1 rounded text-xs font-bold'>{perf:.1f}%</span>"
                    else:
                        perf_badge = f"<span class='bg-yellow-200 text-yellow-900 px-2 py-1 rounded text-xs font-bold'>{perf:.1f}%</span>"
                    
                    items_html.append(f"""
                    <div class="flex justify-between items-center py-2 border-b border-gray-200 last:border-0">
                        <div class="flex-1">
                            <a href="/item-analysis?item_id={item.get('mds_fam_id', '')}" 
                               target="_blank"
                               class="text-blue-600 hover:text-blue-800 font-mono text-sm font-semibold underline">
                                {item.get('mds_fam_id', 'N/A')}
                            </a>
                            <p class="text-xs text-gray-500">Qty: {item.get('qty', 0)} • Dept: {item.get('dept', 'N/A')}</p>
                        </div>
                        <div>
                            {perf_badge}
                        </div>
                    </div>
                    """)
            else:
                items_html.append("""
                <div class="text-center py-4 text-green-700 font-semibold">
                     All items performing well!
                </div>
                """)
            
            card = f"""
            <div class="border-2 {border_color} rounded-lg overflow-hidden shadow-lg hover:shadow-xl transition-shadow">
                <!-- Header -->
                <div class="{header_color} p-4 text-white">
                    <div class="flex items-center justify-between">
                        <div>
                            <h3 class="text-xl font-bold">{status_emoji} Delivery #{delivery_num}</h3>
                            <p class="text-sm opacity-90">{station}</p>
                        </div>
                        <div class="{badge_color} px-3 py-1 rounded-full font-bold text-sm">
                            {problematic_count} issues
                        </div>
                    </div>
                </div>
                
                <!-- Problematic Items -->
                <div class="p-4 bg-white">
                    <h4 class="font-bold text-gray-700 mb-3 text-sm uppercase tracking-wide">
                        Top Problematic Items (Performance &lt; 90%)
                    </h4>
                    <div class="space-y-1">
                        {''.join(items_html)}
                    </div>
                    
                    {f'<p class="text-xs text-gray-500 mt-3 text-center">+ {problematic_count - 10} more items</p>' if problematic_count > 10 else ''}
                </div>
                
                <!-- Footer -->
                <div class="bg-gray-50 px-4 py-2 border-t border-gray-200">
                    <a href="/delivery-analysis?delivery={delivery_num}" 
                       target="_blank"
                       class="text-blue-600 hover:text-blue-800 text-sm font-semibold">
                         Full Analysis →
                    </a>
                </div>
            </div>
            """
            cards_html.append(card)
        
        # Add last updated footer
        footer = f"""
        <div class="col-span-full bg-blue-50 border border-blue-300 rounded p-3 text-center">
            <p class="text-blue-800 text-sm font-semibold">
                 Last updated: {last_updated} • Auto-refreshes every 60 seconds
            </p>
        </div>
        """
        
        return '\n'.join(cards_html) + footer
    
    except Exception as e:
        import traceback
        return f"""
        <div class="col-span-full bg-red-50 border-2 border-red-400 rounded-lg p-6">
            <p class="text-red-800 font-bold text-lg"> Error loading {acl.upper()} data</p>
            <p class="text-red-700 mt-2">{str(e)}</p>
            <pre class="text-xs text-gray-600 mt-3 overflow-auto bg-white p-3 rounded">{traceback.format_exc()}</pre>
        </div>
        """
