import os
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import ibm_db

# Load environment variables
load_dotenv()

# Database connection config
DB_CONFIG = {
    "host": os.getenv("INFORMIX_HOST"),
    "server": os.getenv("INFORMIX_SERVER"),
    "port": int(os.getenv("INFORMIX_PORT", 23301)),
    "user": os.getenv("INFORMIX_USER"),
    "password": os.getenv("INFORMIX_PASSWORD"),
    "database": os.getenv("INFORMIX_DATABASE"),
}


class Delivery(BaseModel):
    delivery_id: str
    customer_name: Optional[str] = None
    delivery_date: Optional[str] = None
    status: Optional[str] = None
    address: Optional[str] = None


def get_db_connection():
    """Create Informix database connection."""
    try:
        conn_str = (
            f"DRIVER={{IBM INFORMIX ODBC DRIVER}};SERVER={DB_CONFIG['server']};DATABASE={DB_CONFIG['database']};HOST={DB_CONFIG['host']};PORT={DB_CONFIG['port']};UID={DB_CONFIG['user']};PWD={DB_CONFIG['password']}"
        )
        return ibm_db.connect(conn_str, "", "")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to Informix: {str(e)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle management."""
    # Startup
    print("[CodePuppy DAR] Starting up...")
    print("[CodePuppy DAR] Dashboard ready at http://localhost:8000")
    yield
    # Shutdown
    print("[CodePuppy DAR] Shutting down...")


app = FastAPI(title="CodePuppy DAR - Deliveries", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve main dashboard."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CodePuppy DAR - Deliveries</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://unpkg.com/htmx.org@1.9.10"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
        <style>
            :root {
                --color-primary: #0053e2;
                --color-accent: #ffc220;
                --color-success: #2a8703;
                --color-error: #ea1100;
            }
        </style>
    </head>
    <body class="bg-gray-50">
        <div class="min-h-screen">
            <!-- Header -->
            <header class="bg-white border-b border-gray-100">
                <div class="max-w-7xl mx-auto px-4 py-6">
                    <h1 class="text-3xl font-bold" style="color: var(--color-primary);">
                        🐶 CodePuppy DAR
                    </h1>
                    <p class="text-gray-600 mt-1">Informix Deliveries Dashboard</p>
                </div>
            </header>

            <!-- Main Content -->
            <main class="max-w-7xl mx-auto px-4 py-8">
                <!-- Stats Grid -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                    <div class="bg-white rounded-lg border border-gray-100 p-6">
                        <p class="text-gray-600 text-sm">Total Deliveries</p>
                        <p class="text-3xl font-bold mt-2" style="color: var(--color-primary);">
                            <span hx-get="/api/stats/total" hx-trigger="load">-</span>
                        </p>
                    </div>
                    <div class="bg-white rounded-lg border border-gray-100 p-6">
                        <p class="text-gray-600 text-sm">Pending</p>
                        <p class="text-3xl font-bold mt-2" style="color: var(--color-accent);">
                            <span hx-get="/api/stats/pending" hx-trigger="load">-</span>
                        </p>
                    </div>
                    <div class="bg-white rounded-lg border border-gray-100 p-6">
                        <p class="text-gray-600 text-sm">Delivered</p>
                        <p class="text-3xl font-bold mt-2" style="color: var(--color-success);">
                            <span hx-get="/api/stats/delivered" hx-trigger="load">-</span>
                        </p>
                    </div>
                    <div class="bg-white rounded-lg border border-gray-100 p-6">
                        <p class="text-gray-600 text-sm">Issues</p>
                        <p class="text-3xl font-bold mt-2" style="color: var(--color-error);">
                            <span hx-get="/api/stats/issues" hx-trigger="load">-</span>
                        </p>
                    </div>
                </div>

                <!-- Deliveries Table -->
                <div class="bg-white rounded-lg border border-gray-100 overflow-hidden">
                    <div class="p-6 border-b border-gray-100">
                        <h2 class="text-xl font-bold">Recent Deliveries</h2>
                    </div>
                    <div hx-get="/api/deliveries" hx-trigger="load" hx-swap="innerHTML">
                        <div class="p-6 text-center text-gray-500">Loading deliveries...</div>
                    </div>
                </div>
            </main>
        </div>
    </body>
    </html>
    """


@app.get("/api/deliveries", response_class=HTMLResponse)
async def get_deliveries():
    """Fetch deliveries from Informix and return as HTML table."""
    try:
        conn = get_db_connection()
        
        # TODO: Replace with actual deliveries table query
        query = """
            SELECT 
                1 as delivery_id,
                'John Doe' as customer_name,
                TODAY() as delivery_date,
                'PENDING' as status,
                '123 Main St' as address
        """
        
        stmt = ibm_db.exec_immediate(conn, query)
        rows = ibm_db.fetch_both(stmt)
        rows_list = []
        while rows:
            rows_list.append(rows)
            rows = ibm_db.fetch_both(stmt)
        ibm_db.close(conn)
        
        if not rows:
            return "<div class='p-6 text-center text-gray-500'>No deliveries found</div>"
        
        html = '<table class="w-full text-left">'
        html += '<thead class="bg-gray-50 border-b border-gray-100"><tr>'
        html += '<th class="px-6 py-3 text-xs font-semibold text-gray-700">ID</th>'
        html += '<th class="px-6 py-3 text-xs font-semibold text-gray-700">Customer</th>'
        html += '<th class="px-6 py-3 text-xs font-semibold text-gray-700">Date</th>'
        html += '<th class="px-6 py-3 text-xs font-semibold text-gray-700">Status</th>'
        html += '<th class="px-6 py-3 text-xs font-semibold text-gray-700">Address</th>'
        html += '</tr></thead><tbody>'
        
        for row in rows:
            status_color = {
                'PENDING': 'bg-yellow-50 text-yellow-700',
                'DELIVERED': 'bg-green-50 text-green-700',
                'FAILED': 'bg-red-50 text-red-700',
            }.get(row[3], 'bg-gray-50 text-gray-700')
            
            html += f'<tr class="border-b border-gray-100 hover:bg-gray-50">'
            html += f'<td class="px-6 py-4 text-sm">{row[0]}</td>'
            html += f'<td class="px-6 py-4 text-sm">{row[1]}</td>'
            html += f'<td class="px-6 py-4 text-sm">{row[2]}</td>'
            html += f'<td class="px-6 py-4 text-sm"><span class="px-2 py-1 rounded text-xs font-semibold {status_color}">{row[3]}</span></td>'
            html += f'<td class="px-6 py-4 text-sm">{row[4]}</td>'
            html += '</tr>'
        
        html += '</tbody></table>'
        return html
        
    except Exception as e:
        return f"<div class='p-6 text-center text-red-600'>Error: {str(e)}</div>"


@app.get("/api/stats/total")
async def stats_total():
    """Get total deliveries count."""
    try:
        conn = get_db_connection()
        stmt = ibm_db.exec_immediate(conn, "SELECT COUNT(*) as cnt FROM delivery")
        row = ibm_db.fetch_both(stmt)
        count = row.get(0, row.get('cnt', 0)) if row else 0
        ibm_db.close(conn)
        return str(count)
    except:
        return "0"


@app.get("/api/stats/pending")
async def stats_pending():
    """Get pending deliveries count."""
    try:
        conn = get_db_connection()
        stmt = ibm_db.exec_immediate(conn, "SELECT COUNT(*) as cnt FROM delivery WHERE status = 'PENDING'")
        row = ibm_db.fetch_both(stmt)
        count = row.get(0, row.get('cnt', 0)) if row else 0
        ibm_db.close(conn)
        return str(count)
    except:
        return "0"


@app.get("/api/stats/delivered")
async def stats_delivered():
    """Get delivered count."""
    try:
        conn = get_db_connection()
        stmt = ibm_db.exec_immediate(conn, "SELECT COUNT(*) as cnt FROM delivery WHERE status = 'DELIVERED'")
        row = ibm_db.fetch_both(stmt)
        count = row.get(0, row.get('cnt', 0)) if row else 0
        ibm_db.close(conn)
        return str(count)
    except:
        return "0"


@app.get("/api/stats/issues")
async def stats_issues():
    """Get issues count."""
    try:
        conn = get_db_connection()
        stmt = ibm_db.exec_immediate(conn, "SELECT COUNT(*) as cnt FROM delivery WHERE status IN ('FAILED', 'CANCELLED')")
        row = ibm_db.fetch_both(stmt)
        count = row.get(0, row.get('cnt', 0)) if row else 0
        ibm_db.close(conn)
        return str(count)
    except:
        return "0"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
