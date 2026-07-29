"""Unloader Manager Summary - Horizontal progress bars by door.

Port: 8062
Shows: Good/Bad/Unknown case distribution by door
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from unloader_client import get_deliveries_from_cache, get_door_assignments, CACHE_DIR
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Unloader Manager", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def manager_view(door_start: int = 425, door_end: int = 500):
    """Manager summary view with horizontal progress bars by door."""
    
    deliveries = get_deliveries_from_cache(door_start, door_end)
    
    # Group by door
    doors_data = {}
    for delivery in deliveries:
        door = delivery.get("door_number", 0)
        if door not in doors_data:
            doors_data[door] = {
                "door": door,
                "deliveries": [],
                "trailers": [],
                "total_good": 0,
                "total_bad": 0,
                "total_unknown": 0
            }
        
        doors_data[door]["deliveries"].append(delivery.get("delivery_nbr"))
        doors_data[door]["trailers"].append(delivery.get("trailer_nbr"))
        
        for item in delivery.get("items", []):
            doors_data[door]["total_good"] += item.get("estimated_good_cases", 0)
            doors_data[door]["total_bad"] += item.get("estimated_bad_cases", 0)
            doors_data[door]["total_unknown"] += item.get("estimated_unknown_cases", 0)
    
    # Sort by door number
    sorted_doors = sorted(doors_data.values(), key=lambda d: d["door"])
    
    # Generate HTML for each door
    door_cards = []
    for door in sorted_doors:
        total = door["total_good"] + door["total_bad"] + door["total_unknown"]
        if total == 0:
            continue
            
        good_pct = (door["total_good"] / total * 100) if total > 0 else 0
        bad_pct = (door["total_bad"] / total * 100) if total > 0 else 0
        unknown_pct = (door["total_unknown"] / total * 100) if total > 0 else 0
        
        deliveries_str = ", ".join([str(d) for d in door["deliveries"][:2]])
        if len(door["deliveries"]) > 2:
            deliveries_str += f" +{len(door['deliveries'])-2} more"
        
        door_cards.append(f'''
        <div class="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div class="flex justify-between items-center mb-2">
                <div>
                    <h3 class="text-xl font-bold">Door {door["door"]}</h3>
                    <p class="text-sm text-gray-400">{len(door["deliveries"])} delivery, {len(set(door["trailers"]))} trailer(s)</p>
                    <p class="text-xs text-gray-500">{deliveries_str}</p>
                </div>
                <div class="text-right">
                    <p class="text-2xl font-bold">{int(total)}</p>
                    <p class="text-xs text-gray-400">Total Cases</p>
                </div>
            </div>
            <div class="progress-bar">
                {f'<div class="progress-segment bg-green-600" style="width: {good_pct}%;">{int(door["total_good"])} Good</div>' if door["total_good"] > 0 else ''}
                {f'<div class="progress-segment bg-red-600" style="width: {bad_pct}%;">{int(door["total_bad"])} Bad</div>' if door["total_bad"] > 0 else ''}
                {f'<div class="progress-segment bg-gray-600" style="width: {unknown_pct}%;">{int(door["total_unknown"])} Unknown</div>' if door["total_unknown"] > 0 else ''}
            </div>
            <div class="flex justify-between mt-2 text-xs text-gray-400">
                <span>Good: {int(door["total_good"])} ({good_pct:.1f}%)</span>
                <span>Bad: {int(door["total_bad"])} ({bad_pct:.1f}%)</span>
                <span>Unknown: {int(door["total_unknown"])} ({unknown_pct:.1f}%)</span>
            </div>
        </div>
        ''')
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unloader Manager View - Doors {door_start}-{door_end}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .progress-bar {{
            height: 40px;
            display: flex;
            width: 100%;
            border-radius: 4px;
            overflow: hidden;
        }}
        .progress-segment {{
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
            color: white;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
            transition: width 0.3s;
        }}
    </style>
</head>
<body class="bg-gray-900 text-white">
    <div class="bg-blue-600 px-4 py-3">
        <div class="flex justify-between items-center mb-2">
            <div>
                <h1 class="text-2xl font-bold">Unloader Manager Summary</h1>
                <p class="text-sm">Doors {door_start}-{door_end} | Case distribution by door | Auto-refresh: 30s</p>
            </div>
            <div class="flex gap-2">
                <a href="http://localhost:8061" class="px-4 py-2 bg-white text-blue-600 rounded font-semibold hover:bg-gray-100">
                    Item View
                </a>
                <a href="http://localhost:8060" class="px-4 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700">
                    Server
                </a>
            </div>
        </div>
        <div class="flex gap-2 items-center">
            <label class="text-sm font-semibold">Door Range:</label>
            <input type="number" id="doorStart" value="{door_start}" class="px-2 py-1 rounded text-gray-900 w-20" />
            <span>to</span>
            <input type="number" id="doorEnd" value="{door_end}" class="px-2 py-1 rounded text-gray-900 w-20" />
            <button onclick="updateDoorRange()" class="px-4 py-1 bg-white text-blue-600 rounded font-semibold hover:bg-gray-100">
                Update
            </button>
        </div>
    </div>
    
    <div class="p-4">
        <div class="grid gap-3" style="grid-template-columns: repeat(auto-fill, minmax(600px, 1fr));">
            {"".join(door_cards)}
        </div>
    </div>
    
    <script>
        function updateDoorRange() {{
            const start = document.getElementById('doorStart').value;
            const end = document.getElementById('doorEnd').value;
            window.location.href = `/?door_start=${{start}}&door_end=${{end}}`;
        }}
        
        // Auto-refresh every 30 seconds
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8062)
