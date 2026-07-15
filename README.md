# CodePuppy DAR - Delivery Analysis & Reporting

## Quick Start

```bash
# Run the server
python main.py
# OR use the batch file
RUN.bat
```

Navigate to: http://localhost:8000

## Features

- **Item Lookup**: Search by MDS Family ID with ACL performance data
- **Delivery Analysis**: Full PO analysis with batching and performance metrics
- **ACL Freight Awareness**: Monitor active deliveries across ACL 1, 2, and 3
- **Batch PDF Reports**: Generate PDFs for problematic items

## Core Files

- `main.py` - FastAPI application
- `delivery_analysis.py` - Informix queries and batching logic
- `batch_report.py` - Read rate calculations
- `cache_manager.py` - 2-day delivery cache
- `informix_connect.py` - Database connection
- `db.py` - SQLite operations

## Documentation

See `_docs/` folder for detailed documentation and changelog.

## Archive

- `_archive/` - Old scripts and backups
- `_installers/` - Feature installers and utilities
