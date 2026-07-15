"""ACL Background Worker

Continuously monitors ACL 1, 2, and 3 for active deliveries.
Pre-caches delivery analysis data for instant page loads.

Runs every 120 seconds (2 minutes) in the background.
"""

import asyncio
import httpx
from datetime import datetime
from typing import Dict, List, Optional
from delivery_analysis import get_delivery_po_data, apply_batching_to_delivery


class ACLMonitor:
    """Background worker that monitors ACLs and pre-caches delivery analysis"""
    
    def __init__(self):
        """Initialize the ACL monitor with empty cache"""
        self.cache: Dict[str, Dict] = {
            "acl1": {"deliveries": [], "analyzed": [], "last_update": None, "status": "idle"},
            "acl2": {"deliveries": [], "analyzed": [], "last_update": None, "status": "idle"},
            "acl3": {"deliveries": [], "analyzed": [], "last_update": None, "status": "idle"},
        }
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def fetch_acl_deliveries(self, acl: str) -> List[Dict]:
        """Fetch active deliveries from ABIA API for specified ACL
        
        Args:
            acl: ACL identifier (acl1, acl2, or acl3)
            
        Returns:
            List of delivery dictionaries with 'delivery' and 'station' keys
        """
        try:
            api_url = f"https://abia.wal-mart.com/aclaware/fetchData/?dc=6068&acl={acl}"
            
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                response = await client.get(api_url)
                response.raise_for_status()
                data = response.json()
            
            deliveries = data.get('data', [])
            print(f"[ACL-WORKER] {acl.upper()}: Fetched {len(deliveries)} active deliveries")
            return deliveries
            
        except Exception as e:
            print(f"[ACL-WORKER] Error fetching {acl.upper()} deliveries: {e}")
            return []
    
    def analyze_delivery_sync(self, delivery_number: str) -> Optional[Dict]:
        """Synchronously analyze a delivery and return enriched data
        
        Args:
            delivery_number: Delivery number to analyze
            
        Returns:
            Enriched delivery data with batching performance, or None on error
        """
        try:
            # CHECK ANALYSIS CACHE FIRST - avoid re-analyzing!
            from cache_manager import get_cache_manager
            cache = get_cache_manager()
            analysis_cache_key = f"analysis_{delivery_number}"
            
            cached_analysis = cache.get(analysis_cache_key, category="deliveries")
            if cached_analysis:
                print(f"[ACL-WORKER] Delivery {delivery_number}: Using CACHED analysis (skipping full analysis)")
                # Return minimal structure with cached data
                return {
                    'success': True,
                    'delivery_number': delivery_number,
                    'data': [],  # Not needed for ACL display
                    'cached': True,
                    'problematic_items_data': cached_analysis.get('problematic_items_data', []),
                    'problematic_details': cached_analysis.get('problematic_details', {}),
                }
            
            print(f"[ACL-WORKER] Delivery {delivery_number}: No cache found, running FULL analysis")
            
            # Fetch raw delivery data (uses Informix cache if available)
            delivery_data = get_delivery_po_data(delivery_number)
            
            if not delivery_data.get('success'):
                print(f"[ACL-WORKER] Failed to fetch delivery {delivery_number}: {delivery_data.get('error')}")
                return None
            
            # Apply batching analysis to get performance metrics
            # WARNING: This still uses old batch_get_read_rates() - slow!
            # TODO: Replace with optimized version
            enriched = apply_batching_to_delivery(delivery_data)
            
            return enriched
            
        except Exception as e:
            print(f"[ACL-WORKER] Error analyzing delivery {delivery_number}: {e}")
            return None
    
    async def analyze_acl(self, acl: str):
        """Fetch and analyze all deliveries for an ACL
        
        Args:
            acl: ACL identifier (acl1, acl2, or acl3)
        """
        print(f"[ACL-WORKER] Starting analysis for {acl.upper()}...")
        self.cache[acl]["status"] = "analyzing"
        
        # Fetch active deliveries from ABIA API
        deliveries = await self.fetch_acl_deliveries(acl)
        self.cache[acl]["deliveries"] = deliveries
        
        # Analyze each delivery synchronously
        analyzed = []
        for item in deliveries:
            delivery_number = item.get('delivery', '')
            if not delivery_number:
                continue
            
            print(f"[ACL-WORKER] {acl.upper()}: Analyzing delivery {delivery_number}...")
            enriched = self.analyze_delivery_sync(delivery_number)
            
            if enriched:
                # Check if this was from cache (different structure)
                if enriched.get('cached'):
                    # Use cached problematic items
                    problematic_items = enriched.get('problematic_items_data', [])
                    problematic_details = enriched.get('problematic_details', {})
                    
                    problematic = []
                    for item in problematic_items[:10]:  # Top 10
                        mds_id = item.get('mds_fam_id', '')
                        acl_details = item.get('acl_details', problematic_details.get(str(mds_id), {}))
                        
                        problematic.append({
                            'mds_fam_id': mds_id,
                            'item_name': item.get('item_name', ''),
                            'performance': acl_details.get('avg_perf', 0),
                            'bad_cases': acl_details.get('bad_cases', 0),
                        })
                    
                    analyzed.append({
                        'delivery_number': delivery_number,
                        'station': item.get('station', 'Unknown'),
                        'analysis': {
                            'total_items': len(problematic_items),
                            'problematic_count': len(problematic_items),
                            'problematic_items': problematic,
                            'cached': True
                        }
                    })
                else:
                    # Extract problematic items from fresh analysis (performance < 90%)
                    # Use 'data' array and extract batching_info
                    problematic = []
                    for po_item in enriched.get('data', []):
                        batching = po_item.get('batching_info', {})
                        perf = batching.get('performance', 100)
                        
                        if perf < 90:
                            problematic.append({
                                'mds_fam_id': po_item.get('mds_fam_id'),
                                'dept': po_item.get('dept', ''),
                                'qty': po_item.get('total_freight_qty', 0),
                                'performance': perf,
                                'bad_cases': batching.get('bad_cases_projected', 0),
                            })
                    
                    # Sort by worst performance first
                    problematic.sort(key=lambda x: x['performance'])
                    
                    # Nest analysis data under 'analysis' key
                    analyzed.append({
                        'delivery_number': delivery_number,
                        'station': item.get('station', 'Unknown'),
                        'analysis': {
                            'total_items': len(enriched.get('data', [])),
                            'problematic_count': len(problematic),
                            'problematic_items': problematic[:10],  # Top 10 worst
                            'cached': False
                        }
                    })
        
        # Update cache
        self.cache[acl]["analyzed"] = analyzed
        self.cache[acl]["last_update"] = datetime.now().isoformat()
        self.cache[acl]["status"] = "ready"
        
        print(f"[ACL-WORKER] {acl.upper()}: Analysis complete! {len(analyzed)} deliveries cached.")
    
    async def monitor_loop(self):
        """Continuously monitor all ACLs every 120 seconds"""
        while self._running:
            try:
                print(f"\n[ACL-WORKER] Starting monitoring cycle at {datetime.now().strftime('%H:%M:%S')}")
                
                # Analyze all three ACLs
                await asyncio.gather(
                    self.analyze_acl("acl1"),
                    self.analyze_acl("acl2"),
                    self.analyze_acl("acl3"),
                    return_exceptions=True  # Don't fail entire cycle if one ACL fails
                )
                
                print(f"[ACL-WORKER] Monitoring cycle complete. Next run in 120 seconds.\n")
                
                # Wait 120 seconds before next cycle
                await asyncio.sleep(120)
                
            except Exception as e:
                print(f"[ACL-WORKER] Error in monitor loop: {e}")
                await asyncio.sleep(120)  # Still wait before retrying
    
    async def start(self):
        """Start the background monitoring loop
        
        Runs initial analysis immediately, then starts continuous monitoring.
        """
        if self._running:
            print("[ACL-WORKER] Already running!")
            return
        
        print("[ACL-WORKER] Starting ACL background monitor...")
        self._running = True
        
        # Run initial analysis immediately
        print("[ACL-WORKER] Running initial analysis for all ACLs...")
        await asyncio.gather(
            self.analyze_acl("acl1"),
            self.analyze_acl("acl2"),
            self.analyze_acl("acl3"),
            return_exceptions=True
        )
        
        # Start background loop
        print("[ACL-WORKER] Initial analysis complete. Starting continuous monitoring loop...")
        self._task = asyncio.create_task(self.monitor_loop())
    
    async def stop(self):
        """Stop the background monitoring loop"""
        if not self._running:
            return
        
        print("[ACL-WORKER] Stopping monitor...")
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        print("[ACL-WORKER] Monitor stopped.")
    
    def get_acl_data(self, acl: str) -> Dict:
        """Get cached analysis data for an ACL
        
        Args:
            acl: ACL identifier (acl1, acl2, or acl3)
            
        Returns:
            Dictionary with deliveries (analyzed data), status, and last_update
        """
        cache = self.cache.get(acl, {
            "deliveries": [],
            "analyzed": [],
            "last_update": None,
            "status": "not_initialized"
        })
        
        # Return 'analyzed' array as 'deliveries' for frontend consumption
        return {
            "deliveries": cache.get("analyzed", []),  # Use analyzed data!
            "last_update": cache.get("last_update"),
            "status": cache.get("status")
        }


# Global instance - imported by main.py
acl_monitor = ACLMonitor()
