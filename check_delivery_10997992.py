#!/usr/bin/env python
"""Check if delivery 10997992 has item 550508254"""

import asyncio
import httpx

async def check_delivery():
    # Check ABIA for active deliveries
    print("Checking ABIA for delivery 10997992...")
    
    for acl in ['acl1', 'acl2', 'acl3']:
        url = f"https://abia.wal-mart.com/aclaware/fetchData/?dc=6068&acl={acl}"
        
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            try:
                response = await client.get(url)
                data = response.json()
                deliveries = data.get('data', [])
                
                delivery_numbers = [d.get('delivery') for d in deliveries]
                
                if '10997992' in delivery_numbers:
                    print(f"\nFound delivery 10997992 in {acl.upper()}!")
                    delivery_info = [d for d in deliveries if d.get('delivery') == '10997992'][0]
                    print(f"Station: {delivery_info.get('station')}")
                    return True
            except Exception as e:
                print(f"Error checking {acl}: {e}")
    
    print("\nDelivery 10997992 NOT FOUND in any ACL!")
    print("This means it's no longer active in ABIA")
    return False

if __name__ == "__main__":
    asyncio.run(check_delivery())
