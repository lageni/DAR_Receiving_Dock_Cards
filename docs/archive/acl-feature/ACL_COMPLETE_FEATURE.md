# ACL Freight Awareness - Complete Feature

## Overview
3 ACL pages monitoring active deliveries with on-demand problematic item analysis.

## Architecture
- Fetches from: https://abia.wal-mart.com/aclaware/fetchData/?dc=6068&acl={acl}
- Reuses: delivery_analysis.py cached pipeline
- Filters: Items with performance < 90%

## Installation
Run the attached Python installer or manually add code blocks to main.py at line 2917.

See installation scripts in repo for complete code.
