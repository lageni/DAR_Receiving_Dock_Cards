"""
Helper to fetch MDM data and build delivery analysis items
(Mirrors batch_random pattern exactly)
"""

async def get_delivery_problematic_items(problematic_mds_ids: list) -> list:
    """Fetch MDM data for each problematic mds_id, return formatted items_data.
    
    Mirrors batch_random() pattern exactly.
    """
    api_key = os.getenv("MDM_API_KEY", "")
    facility_num = os.getenv("MDM_FACILITY_NUM", "6068")
    facility_country = os.getenv("MDM_FACILITY_COUNTRY_CODE", "US")
    wmt_userid = os.getenv("MDM_WMT_USERID", "mdm-ui")
    
    headers = {
        "Api-Key": api_key,
        "Facilitynum": facility_num,
        "Facilitycountrycode": facility_country,
        "Wmt-Userid": wmt_userid
    }
    
    items_data = []
    
    for mds_id in problematic_mds_ids:
        try:
            # Use mds_id as item_id for MDM lookup (EXACTLY like batch)
            api_url = f"https://uwms-item.prod.us.walmart.net/items/wm/{mds_id}/?xrefItemInfo=false"
            
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.get(api_url, headers=headers)
                response.raise_for_status()
                mdm_data = response.json()
                
                # Extract item data using same function as batch
                item_data = extract_item_data(mdm_data)
                
                # Add MDS ID for reference
                item_data["mds_fam_id"] = str(mds_id)
                
                items_data.append(item_data)
                print(f"[DELIVERY-MDM] Fetched MDM data for MDS {mds_id}")
        
        except Exception as e:
            print(f"[DELIVERY-MDM] Error fetching MDS {mds_id}: {str(e)}")
            # Still include in results with minimal data
            items_data.append({
                "mds_fam_id": str(mds_id),
                "item_name": f"MDS {mds_id}",
                "image_url": "",
                "error": str(e)
            })
    
    return items_data
