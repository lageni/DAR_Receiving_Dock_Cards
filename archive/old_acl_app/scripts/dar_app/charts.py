"""Chart.js HTML generation for the ACL performance trend chart."""
import json

from dar_app.department_bands import check_non_conveyable
from dar_app.metrics import (
    format_date_for_chart,
    get_avg_performance,
    get_color_for_performance,
    get_recommendation,
    get_trend_status,
)
from dar_app.read_rates_data import load_read_rates

def get_read_rate_chart(mds_fam_id: str, length: str = "", width: str = "", height: str = "") -> str:
    """Generate Chart.js HTML for read rate trend from read_rates.db."""
    is_non_convey, non_convey_text, _ = check_non_conveyable(length, width, height)
    if is_non_convey:
        print(f"[RECOMMENDATION] Item {mds_fam_id}: {non_convey_text}")
        return f'''<div class="mt-4 bg-white p-4 rounded border max-w-md mx-auto">
            <h2 class="text-2xl font-bold text-center text-blue-600 mb-3">ACL Performance %</h2>
            <div class="bg-red-50 border-2 border-red-300 p-6 rounded-xl text-center shadow-lg">
                <div class="text-3xl font-black text-red-600">{non_convey_text}</div>
            </div>
            <div class="mt-3 text-xs text-gray-600 text-center border-t pt-2">
                <p>Total PO Qty: <strong>{total_po_qty:,}</strong></p>
            </div>
        </div>'''
    
    rates = load_read_rates()
    data = rates.get(str(mds_fam_id), [])
    
    # Debug: if no data, show message
    if not data or len(data) == 0:
        return f'''<div class="mt-4 bg-yellow-50 p-4 rounded border-2 border-yellow-300">
            <p class="text-yellow-700 text-sm">No ACL Performance data available for MDS_FAM_ID: {mds_fam_id}</p>
        </div>'''
    
    # Format data for Chart.js - use abbreviated month+year for labels
    labels = [format_date_for_chart(d["date"]) for d in data]
    values = [d["null_pct"] for d in data]
    
    # Calculate metrics
    avg_perf = get_avg_performance(data)
    trend_status = get_trend_status(data)
    color = get_color_for_performance(avg_perf)
    
    # Create chart ID
    chart_id = f"chart_{mds_fam_id}"
    
    # Get recommendation based on performance and trend
    recommendation, rec_color, rec_bg = get_recommendation(avg_perf, trend_status)
    
    # Safely build the data JSON string
    labels_json = json.dumps(labels)
    values_json = json.dumps(values)
    
    # Create performance cards (prettier, much bigger)
    perf_card = f'''<div class="grid grid-cols-2 gap-4 mb-4">
        <div class="bg-gradient-to-br from-amber-50 via-yellow-50 to-yellow-100 p-6 rounded-xl border-2 border-yellow-300 shadow-lg hover:shadow-xl transition transform hover:scale-105">
            <div class="text-center">
                <div class="text-sm text-yellow-700 font-bold uppercase tracking-widest">Avg Performance</div>
                <div class="text-5xl font-black mt-3" style="color: {color};">{avg_perf:.1f}%</div>
            </div>
        </div>
        <div class="bg-gradient-to-br from-purple-50 via-indigo-50 to-indigo-100 p-6 rounded-xl border-2 border-purple-300 shadow-lg hover:shadow-xl transition transform hover:scale-105">
            <div class="text-center">
                <div class="text-sm text-purple-700 font-bold uppercase tracking-widest">Trend</div>
                <div class="text-4xl font-black mt-3 text-purple-900">{trend_status}</div>
            </div>
        </div>
    </div>'''
    
    # Create recommendation card (big and bold)
    rec_card = f'''<div class="bg-gradient-to-br {rec_bg} p-8 rounded-xl border-2 shadow-lg mb-4">
        <div class="text-center">
            <div class="text-5xl font-black" style="color: {rec_color};">{recommendation}</div>
        </div>
    </div>'''
    
    return f'''<div class="mt-4 bg-white p-4 rounded border max-w-md mx-auto">
        <h2 class="text-2xl font-bold text-center text-blue-600 mb-3">ACL Performance %</h2>
        {rec_card}
        {perf_card}
        <div style="height: 300px; position: relative; max-width: 400px; margin: 0 auto;">
            <canvas id="{chart_id}"></canvas>
        </div>
        <script>
            (function() {{
                // Wait for Chart.js to be ready
                if (typeof Chart === 'undefined') {{
                    setTimeout(arguments.callee, 100);
                    return;
                }}
                var ctx = document.getElementById("{chart_id}").getContext("2d");
                var labels = {labels_json};
                var values = {values_json};
                new Chart(ctx, {{
                    type: "line",
                    data: {{
                        labels: labels,
                        datasets: [{{
                            label: "ACL Performance %",
                            data: values,
                            borderColor: "#0053e2",
                            backgroundColor: "rgba(0, 83, 226, 0.1)",
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3,
                            pointRadius: 3,
                            pointBackgroundColor: "#0053e2"
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                display: false
                            }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                max: 100
                            }}
                        }}
                    }}
                }});
            }})();
        </script>
    </div>'''
