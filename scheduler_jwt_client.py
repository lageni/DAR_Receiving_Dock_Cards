"""
Scheduler.walmart.com JWT Token Client

Simple client for using JWT token extracted from scheduler.walmart.com login.
No complex OAuth/SAML flow - just use the token directly.
"""

import os
import httpx
import json
from typing import Optional, Dict, Any
from datetime import datetime
import base64


class SchedulerJWTClient:
    """
    Simple JWT token client for scheduler.walmart.com
    
    Usage:
    1. Log in to scheduler.walmart.com in browser
    2. Extract JWT token from URL (uat parameter)
    3. Add to .env: SCHEDULER_JWT_TOKEN=...
    4. Use client to make API calls (token attached automatically)
    """
    
    def __init__(self):
        self.token = os.getenv("SCHEDULER_JWT_TOKEN", "").strip()
        self.base_url = "https://scheduler.walmart.com"
        
        if self.token:
            self._log_token_info()
    
    def _log_token_info(self):
        """Log token expiration info."""
        try:
            # Decode JWT payload (without verification)
            parts = self.token.split(".")
            if len(parts) == 3:
                # Add padding if needed
                payload_str = parts[1]
                padding = 4 - (len(payload_str) % 4)
                if padding != 4:
                    payload_str += "=" * padding
                
                payload = json.loads(base64.urlsafe_b64decode(payload_str))
                
                if "exp" in payload:
                    exp_timestamp = payload["exp"]
                    exp_datetime = datetime.fromtimestamp(exp_timestamp)
                    print(f"[SCHEDULER JWT] Token loaded. Expires: {exp_datetime}")
                    
                    # Check if expired
                    if datetime.now() > exp_datetime:
                        print("[SCHEDULER JWT] WARNING: Token has expired!")
                    else:
                        remaining = (exp_datetime - datetime.now()).total_seconds() / 3600
                        print(f"[SCHEDULER JWT] Token valid for {remaining:.1f} more hours")
        except Exception as e:
            print(f"[SCHEDULER JWT] Could not decode token: {str(e)[:100]}")
    
    def is_configured(self) -> bool:
        """Check if JWT token is configured."""
        return bool(self.token)
    
    def get_token_info(self) -> Optional[Dict[str, Any]]:
        """Get decoded token payload (for debugging)."""
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
        except Exception as e:
            print(f"[SCHEDULER JWT] Error decoding token: {str(e)[:100]}")
            return None
    
    async def api_call(
        self,
        endpoint: str,
        method: str = "GET",
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Make an API call to scheduler.walmart.com with JWT token.
        
        Args:
            endpoint: API endpoint (e.g., "/api/users" or full URL)
            method: HTTP method (GET, POST, PUT, DELETE)
            json_data: JSON payload for POST/PUT
            params: Query parameters
            headers: Additional headers
            **kwargs: Extra args to pass to httpx
        
        Returns:
            httpx.Response object
        
        Raises:
            Exception if token not configured
        """
        if not self.token:
            raise Exception(
                "SCHEDULER_JWT_TOKEN not configured. "
                "Extract token from scheduler.walmart.com URL (uat parameter) "
                "and add to .env"
            )
        
        # Build URL
        if endpoint.startswith("http"):
            url = endpoint
        else:
            url = f"{self.base_url}{endpoint}"
        
        # Build headers with token
        req_headers = headers or {}
        req_headers["Authorization"] = f"Bearer {self.token}"
        req_headers["User-Agent"] = "CodePuppyDAR/1.0"
        req_headers["Content-Type"] = "application/json"
        
        print(f"[SCHEDULER JWT] {method} {url}")
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.request(
                    method,
                    url,
                    headers=req_headers,
                    json=json_data,
                    params=params,
                    **kwargs
                )
                
                # Log status
                if response.status_code >= 400:
                    print(f"[SCHEDULER JWT] Response: HTTP {response.status_code}")
                    if response.status_code == 401:
                        print("[SCHEDULER JWT] WARNING: 401 Unauthorized - Token may be expired")
                        print("[SCHEDULER JWT] Solution: Log in to scheduler.walmart.com again and extract new token")
                
                return response
        
        except Exception as e:
            print(f"[SCHEDULER JWT] API call error: {type(e).__name__}: {str(e)[:150]}")
            raise
    
    def get_token_preview(self) -> str:
        """Get first 50 chars of token for display."""
        if not self.token:
            return "NOT CONFIGURED"
        return self.token[:50] + "..." if len(self.token) > 50 else self.token


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test():
        client = SchedulerJWTClient()
        
        if not client.is_configured():
            print("JWT token not configured. Set SCHEDULER_JWT_TOKEN in .env")
            return
        
        # Get token info
        info = client.get_token_info()
        print(f"Token info: {json.dumps(info, indent=2)}")
        
        # Make a test API call (adjust endpoint as needed)
        try:
            response = await client.api_call("/api/test", method="GET")
            print(f"Response: {response.status_code}")
        except Exception as e:
            print(f"Error: {e}")
    
    asyncio.run(test())
