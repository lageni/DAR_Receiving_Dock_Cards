"""
CodePuppyDAR - ACL Freight Awareness + Delivery Analysis server (port 8050).

This used to be a single ~4300-line file. It's now a thin FastAPI app that
wires together the pieces in scripts/dar_app/ (data access, rendering, PDF
export, and one router module per feature area).
"""
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from acl_background_worker import acl_monitor
from dar_app.logging_setup import logger

# Route modules - each owns one slice of the URL space
from dar_app import (
    routes_acl,
    routes_admin,
    routes_batch,
    routes_delivery_page,
    routes_delivery_pdf,
    routes_delivery_search,
    routes_diagnostics,
    routes_item,
)

# Re-exports kept for backward compatibility: acl_background_worker.py,
# unloader_client.py, and scripts/debug/*.py import these directly from
# `main` (e.g. `from main import get_avg_performance`). Keep them working.
from dar_app.card_render import extract_item_data, format_results, generate_print_card
from dar_app.charts import get_read_rate_chart
from dar_app.department_bands import (
    check_non_conveyable,
    get_contrasting_text_rgb,
    get_department_band,
    load_department_bands,
)
from dar_app.metrics import (
    format_date_for_chart,
    get_avg_performance,
    get_color_for_performance,
    get_recommendation,
    get_trend_status,
)
from dar_app.pdf_export import generate_pdf, sanitize_for_pdf
from dar_app.pdf_export_batch import generate_batch_pdf
from dar_app.read_rates_data import get_database_path, load_read_rates, load_read_rates_for_items

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

app = FastAPI(title="CodePuppy DAR")


@app.on_event("startup")
async def startup_event():
    logger.info("[STARTUP] Starting ACL background monitor...")
    asyncio.create_task(acl_monitor.start())  # Don't block server startup!
    logger.info("[STARTUP] ACL monitor running in background")


app.include_router(routes_item.router)
app.include_router(routes_admin.router)
app.include_router(routes_diagnostics.router)
app.include_router(routes_batch.router)
# NOTE: routes_acl registers a catch-all "/{acl}" path. Starlette matches
# routes in registration order (not by specificity), so anything registered
# after this point that shares a path segment with an acl name would be
# shadowed. This matches the original main.py's route order exactly -
# don't reorder without checking for path collisions first.
app.include_router(routes_acl.router)
app.include_router(routes_delivery_page.router)
app.include_router(routes_delivery_search.router)
app.include_router(routes_delivery_pdf.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8050)
