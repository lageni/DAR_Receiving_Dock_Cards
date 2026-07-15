#!/usr/bin/env python3
"""
Fix freight_bill_qty calculation in delivery_analysis.py

The issue: freight_bill_qty repeats for each line of a PO because each line shares 
the same freight bill. We need to:
1. Group by unique PO to get total freight per PO
2. Get total whpk_order_qty per PO
3. Calculate adjustment factor for each line
"""

with open('delivery_analysis.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add a new function to apply_batching_to_delivery that handles freight proportions
new_function = '''

def apply_freight_proportions(data: dict) -> dict:
    """Adjust whpk_order_qty values based on freight_bill_qty proportions.
    
    When a PO is split across deliveries, freight_bill_qty shows the actual freight 
    for THIS delivery, but whpk_order_qty is the full PO line quantity.
    
    This calculates: adjusted_qty = whpk_order_qty * (freight_bill_qty / sum_whpk_for_po)
    """
    po_rows = data.get('data', [])
    
    if not po_rows:
        return data
    
    # Group rows by PO number to get freight and qty totals
    po_groups = {}
    for row in po_rows:
        po_nbr = row.get('po_nbr')
        freight_bill = row.get('freight_bill_qty', 0)
        whpk_qty = row.get('whpk_order_qty', 0)
        
        if po_nbr not in po_groups:
            po_groups[po_nbr] = {
                'freight_bill_qty': freight_bill,  # Same for all lines of same PO/freight bill
                'total_whpk': 0,
                'lines': []
            }
        
        po_groups[po_nbr]['lines'].append(row)
        try:
            po_groups[po_nbr]['total_whpk'] += int(whpk_qty) if isinstance(whpk_qty, str) else whpk_qty
        except:
            pass
    
    # Calculate adjustment factors and apply to rows
    for row in po_rows:
        po_nbr = row.get('po_nbr')
        po_info = po_groups.get(po_nbr, {})
        
        freight = po_info.get('freight_bill_qty', 0)
        total_whpk = po_info.get('total_whpk', 1)
        
        if total_whpk > 0 and freight > 0:
            adjustment_factor = freight / total_whpk
            original_qty = row.get('whpk_order_qty', 0)
            try:
                original_qty = int(original_qty) if isinstance(original_qty, str) else original_qty
                adjusted_qty = int(original_qty * adjustment_factor)
                row['whpk_adjusted_qty'] = adjusted_qty
                row['qty_adjustment_factor'] = round(adjustment_factor, 4)
            except:
                row['whpk_adjusted_qty'] = original_qty
                row['qty_adjustment_factor'] = 1.0
    
    return data
'''

# Insert the function before apply_batching_to_delivery
if 'def apply_batching_to_delivery' in content:
    idx = content.find('def apply_batching_to_delivery')
    content = content[:idx] + new_function + '\n\n' + content[idx:]
    print("[ADDED] apply_freight_proportions function")
else:
    print("[ERROR] Could not find apply_batching_to_delivery")

# Modify apply_batching_to_delivery to call the new function
old_apply = '''def apply_batching_to_delivery(delivery_data: dict) -> dict:'''
new_apply = '''def apply_batching_to_delivery(delivery_data: dict) -> dict:
    # First apply freight proportions
    delivery_data = apply_freight_proportions(delivery_data)'''

if old_apply in content:
    content = content.replace(old_apply, new_apply)
    print("[UPDATED] apply_batching_to_delivery to use freight proportions")

with open('delivery_analysis.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("[SUCCESS] delivery_analysis.py updated with freight proportions")
