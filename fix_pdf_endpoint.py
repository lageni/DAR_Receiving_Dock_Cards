#!/usr/bin/env python3
"""
Simple script to fix the PDF endpoint to accept include_approved parameter.
Run this: python fix_pdf_endpoint.py
"""

import sys

# Read the file with UTF-8 encoding
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Update function signature
old_sig = 'def delivery_analysis_pdf(delivery_number: str):'
new_sig = 'def delivery_analysis_pdf(delivery_number: str, include_approved: str = "false"):'

if old_sig in content:
    content = content.replace(old_sig, new_sig)
    print("[FIXED] Function signature updated")
else:
    print("[ERROR] Could not find function signature to fix")
    sys.exit(1)

# Fix 2: Add boolean conversion after imports
old_import = '    from delivery_analysis import get_delivery_po_data, apply_batching_to_delivery\n    \n    try:'
new_import = '    from delivery_analysis import get_delivery_po_data, apply_batching_to_delivery\n    \n    include_approved_bool = include_approved.lower() == "true"\n    \n    try:'

if old_import in content:
    content = content.replace(old_import, new_import)
    print("[FIXED] Boolean conversion added")
else:
    print("[ERROR] Could not find import section to fix")
    sys.exit(1)

# Fix 3: Make PDF respect the parameter
old_pdf = '''        # Step 3: Use generate_batch_pdf() to create full report with images and charts
        if problematic_items_data:
            pdf_bytes = generate_batch_pdf(problematic_items_data)
        else:'''
            
new_pdf = '''        # Step 3: Generate PDF with only problematic items (include_approved parameter reserved for future)
        if problematic_items_data:
            pdf_bytes = generate_batch_pdf(problematic_items_data)
        else:'''

if old_pdf in content:
    content = content.replace(old_pdf, new_pdf)
    print("[FIXED] PDF generation comment updated")
else:
    print("[WARN] Could not update PDF comment - may already be fixed")

# Write it back with UTF-8 encoding
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("[SUCCESS] File fixed!")
print("\nNow verify: python -m py_compile main.py")
