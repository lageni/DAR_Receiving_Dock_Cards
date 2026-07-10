"""
Scheduler.walmart.com API Client

Uses JWT token stored in .env to make API calls.
No browser automation needed.
"""

import os
import httpx
import json
import base64
from typing import Optional, Dict, Any
from datetime import datetime


class SchedulerClient:
    """Simple JWT-based client for Scheduler API."""
    
    def __init__(self):
        self.token = os.getenv("SCHEDULER_JWT_TOKEN", "").strip()
        self.base_url = "https://scheduler.walmart.com"
        
        if self.token:
            self._log_token_info()
    
    def _log_token_info(self):
        """Log token info on init."""
        try:
            parts = self.token.split(".")
            if len(parts) == 3:
                payload_str = parts[1]
                padding = 4 - (len(payload_str) % 4)
                if padding != 4:
                    payload_str += "=" * padding
                
                payload = json.loads(base64.urlsafe_b64decode(payload_str))
                
                if "exp" in payload:
                    exp_dt = datetime.fromtimestamp(payload["exp"])
                    if datetime.now() > exp_dt:
                        print("[SCHEDULER] WARNING: Token has expired!")
                    else:
                        remaining_hours = (exp_dt - datetime.now()).total_seconds() / 3600
                        print(f"[SCHEDULER] Token ready. Valid for {remaining_hours:.1f} more hours")
        except:
            pass
    
    def is_configured(self) -> bool:
        """Check if token is configured."""
        return bool(self.token)
    
    def get_token_info(self) -> Optional[Dict[str, Any]]:
        """Get decoded token payload."""
        if not self.token:
            return None
        
        try:
            parts = self.token.split(".")
            if len(parts) != 3:
                return None
            
            payload_str = parts[1]
            padding = 4 - (len(payload_str) % 4)
            if padding != 4:
                payload_str += "=" * padding
            
            return json.loads(base64.urlsafe_b64decode(payload_str))
        except:
            return None
    
    async def api_call(
        self,
        endpoint: str,
        method: str = "GET",
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Make API call with JWT token.
        
        Args:
            endpoint: API path (e.g., "/api/schedules")
            method: HTTP method
            json_data: JSON payload
            params: Query parameters
        
        Returns:
            httpx.Response
        """
        if not self.token:
            raise Exception("SCHEDULER_JWT_TOKEN not configured in .env")
        
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        headers["Content-Type"] = "application/json"
        
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            return await client.request(
                method,
                url,
                headers=headers,
                json=json_data,
                params=params,
                **kwargs
            )


# Global instance
_scheduler = None

def get_scheduler_client() -> SchedulerClient:
    """Get or create scheduler client."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerClient()
    return _scheduler
