"""Route: /delivery-analysis (search form page)."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/delivery-analysis", response_class=HTMLResponse)
async def delivery_analysis_page():
    """Delivery Analysis search page - user inputs delivery number."""
    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Delivery Analysis</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org"></script>
    <style>
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        @keyframes pulse-glow {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .spinner {{
            animation: spin 0.8s linear infinite;
        }}
        .pulse {{
            animation: pulse-glow 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }}
        #loading.htmx-request {{
            display: flex !important;
        }}
        #loading:not(.htmx-request) {{
            display: none !important;
        }}
    </style>
</head>
<body class="bg-gray-50">
    <div class="w-full p-6" style="max-width: none;">
        <h1 class="text-4xl font-bold text-blue-600 mb-2">Delivery Analysis</h1>
        <p class="text-gray-700 mb-6">Enter a delivery number to analyze purchase order data, batching, and item performance.</p>
        
        <div class="bg-white p-6 rounded-lg shadow-lg border-2 border-blue-200" style="max-width: 600px;">
            <form hx-get="/api/delivery-analysis/search" hx-target="#results" hx-indicator="#loading" class="space-y-4">
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">Delivery Number</label>
                    <input 
                        type="text" 
                        name="delivery_number" 
                        placeholder="e.g., 10691042" 
                        class="w-full px-4 py-3 border border-gray-300 rounded font-mono text-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        required
                    >
                    <p class="text-xs text-gray-500 mt-1">Corresponds to rcv.appointment_nbr in the Informix query</p>
                </div>
                
                <button type="submit" class="w-full bg-blue-600 text-white font-semibold py-3 rounded hover:bg-blue-700 transition flex items-center justify-center">
                    <span>Search</span>
                </button>
            </form>
        </div>
        
        <!-- Loading Indicator with Progress -->
        <div id="loading" class="flex-col items-center justify-center mt-12 space-y-8">
            <div class="space-y-4 w-full max-w-2xl">
                <!-- Spinner Header -->
                <div class="flex items-center justify-center space-x-3">
                    <svg class="spinner h-10 w-10 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <div>
                        <div class="text-xl font-bold text-gray-800">Analyzing Delivery...</div>
                        <div class="text-sm text-gray-600">This may take 10-45 seconds depending on data volume</div>
                    </div>
                </div>
                
                <!-- Progress Bar -->
                <div class="bg-gray-200 rounded-full h-3 overflow-hidden">
                    <div id="progressBar" class="bg-blue-600 h-full" style="width: 0%; transition: width 0.3s ease;"></div>
                </div>
                <div class="text-center text-sm text-gray-600">
                    <span id="progressPercent">Starting...</span>
                </div>
                
                <!-- Current Status -->
                <div id="currentStatus" class="bg-blue-50 border-l-4 border-blue-600 p-4 rounded">
                    <div class="text-sm text-blue-800 font-mono">
                        [QUERY] Connecting to Informix...
                    </div>
                </div>
                
                <!-- Steps Progress -->
                <div class="space-y-2">
                    <div id="step1" class="pulse bg-blue-100 border border-blue-300 rounded p-3 text-sm text-blue-700 font-mono">
                        ✓ [QUERY] Connected to Informix
                    </div>
                    <div id="step2" class="bg-gray-100 border border-gray-300 rounded p-3 text-sm text-gray-700 font-mono opacity-50">
                        [BATCH] Loading read rate data...
                    </div>
                    <div id="step3" class="bg-gray-100 border border-gray-300 rounded p-3 text-sm text-gray-700 font-mono opacity-50">
                        [ANALYZE] Analyzing ACL status...
                    </div>
                    <div id="step4" class="bg-gray-100 border border-gray-300 rounded p-3 text-sm text-gray-700 font-mono opacity-50">
                        [BUILD] Building HTML response...
                    </div>
                </div>
                
                <!-- Tips -->
                <div class="bg-yellow-50 border border-yellow-200 rounded p-3 text-xs text-yellow-700">
                    <strong>Tip:</strong> Open browser console (F12) to see detailed progress logs in real-time
                </div>
            </div>
        </div>
        
        <script>
        // Simulate progress based on time elapsed
        let startTime = null;
        let progressInterval = null;
        
        document.addEventListener('htmx:xhr:beforeSend', function(evt) {{
            startTime = Date.now();
            progressInterval = setInterval(function() {{
                let elapsed = (Date.now() - startTime) / 1000;
                let percent = Math.min(80, Math.floor((elapsed / 35) * 100));
                
                document.getElementById('progressBar').style.width = percent + '%';
                
                if (percent < 20) {{
                    document.getElementById('progressPercent').textContent = 'Querying Informix... (' + percent + '%)';
                }} else if (percent < 50) {{
                    document.getElementById('progressPercent').textContent = 'Loading batching data... (' + percent + '%)';
                }} else {{
                    document.getElementById('progressPercent').textContent = 'Analyzing and building report... (' + percent + '%)';
                }}
            }}, 200);
        }});
        
        document.addEventListener('htmx:afterRequest', function(evt) {{
            if (progressInterval) clearInterval(progressInterval);
            if (evt.detail.xhr.status === 200) {{
                document.getElementById('progressBar').style.width = '100%';
                document.getElementById('progressPercent').textContent = 'Complete! (100%)';
            }}
        }});
        </script>
        
        <div id="results" class="mt-8"></div>
        
        <div class="mt-6">
            <a href="/" class="inline-block px-6 py-2 bg-gray-600 text-white rounded font-semibold hover:bg-gray-700">Back to Home</a>
        </div>
    </div>
</body>
</html>'''
