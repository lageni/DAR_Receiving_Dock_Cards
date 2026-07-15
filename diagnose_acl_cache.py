"""
DIAGNOSTIC SCRIPT - Check ACL Worker Cache

Run this to see what's actually in the ACL worker's memory cache
"""

import sys
sys.path.insert(0, 'C:\\Users\\d0h0pf7\\Documents\\puppy_workspace\\CodePuppyDAR')

from acl_background_worker import acl_monitor

print("=== ACL WORKER CACHE DIAGNOSTIC ===\n")

for acl in ['acl1', 'acl2', 'acl3']:
    print(f"\n{acl.upper()}:")
    print("-" * 50)
    
    cache = acl_monitor.cache.get(acl, {})
    print(f"Status: {cache.get('status', 'NOT FOUND')}")
    print(f"Last Update: {cache.get('last_update', 'NOT FOUND')}")
    print(f"Deliveries (raw): {len(cache.get('deliveries', []))}")
    print(f"Analyzed: {len(cache.get('analyzed', []))}")
    
    analyzed = cache.get('analyzed', [])
    if analyzed:
        print(f"\nFirst delivery:")
        first = analyzed[0]
        print(f"  Delivery Number: {first.get('delivery_number', 'MISSING')}")
        print(f"  Station: {first.get('station', 'MISSING')}")
        print(f"  Analysis: {first.get('analysis', 'MISSING')}")
    else:
        print("\n  NO ANALYZED DELIVERIES!")
    
    # Check what get_acl_data returns
    returned_data = acl_monitor.get_acl_data(acl)
    print(f"\nget_acl_data() returns:")
    print(f"  deliveries: {len(returned_data.get('deliveries', []))}")
    print(f"  status: {returned_data.get('status')}")
    print(f"  last_update: {returned_data.get('last_update')}")

print("\n" + "=" * 50)
print("DIAGNOSTIC COMPLETE")
