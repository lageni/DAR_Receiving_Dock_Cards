"""
Scheduler.walmart.com Client

Handles automatic authentication, token refresh, and API calls.
Will be configured once we know the exact auth flow.
"""

import os
import json
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import asyncio

class SchedulerClient:
    """
    Automatic scheduler.walmart.com client with:
    - Auto-login from credentials
    - Token refresh on expiration
    - Automatic token injection on API calls
    """
    
    def __init__(self):
        self.username = os.getenv("SCHEDULER_USERNAME", "").strip()
        self.password = os.getenv("SCHEDULER_PASSWORD", "").strip()
        self.api_key = os.getenv("SCHEDULER_API_KEY", "").strip()
        
        self.base_url = "https://scheduler.walmart.com"
        self.token = None
        self.token_expires_at = None
        self.auth_method = None  # Will be 'bearer', 'api_key', 'basic', etc.
        self.client = None
        
        self._determine_auth_method()
    
    def _determine_auth_method(self):
        """Figure out which auth method to use."""
        if self.api_key:
            self.auth_method = "api_key"
            print("[SCHEDULER] Using API Key authentication")
        elif self.username and self.password:
            self.auth_method = "credentials"
            print("[SCHEDULER] Using username/password authentication")
        else:
            print("[SCHEDULER] WARNING: No credentials configured (set SCHEDULER_USERNAME + SCHEDULER_PASSWORD)")
            self.auth_method = None
    
    async def login(self) -> bool:
        """
        Attempt automatic login to scheduler.walmart.com
        
        Returns:
            True if successful, False otherwise
        """
        if not self.auth_method:
            print("[SCHEDULER] Cannot login: no auth method configured")
            return False
        
        if self.auth_method == "api_key":
            print("[SCHEDULER] API Key auth (no login needed)")
            return True
        
        if self.auth_method != "credentials":
            print("[SCHEDULER] Auth method not yet implemented:", self.auth_method)
            return False
        
        # Credentials-based login
        print("[SCHEDULER] Attempting login...")
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                # STUB: Replace this URL with actual endpoint once we know it
                login_url = f"{self.base_url}/api/auth/login"
                
                # STUB: Replace with actual request format
                login_payload = {
                    "username": self.username,
                    "password": self.password
                }
                
                print(f"[SCHEDULER] POST {login_url}")
                response = await client.post(
                    login_url,
                    json=login_payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    print(f"[SCHEDULER] Login failed: HTTP {response.status_code}")
                    print(f"[SCHEDULER] Response: {response.text[:200]}")
                    return False
                
                # STUB: Parse response based on actual format
                data = response.json()
                
                # Try common token field names
                token = None
                for key in ["token", "access_token", "sessionToken", "auth_token"]:
                    if key in data:
                        token = data[key]
                        print(f"[SCHEDULER] Found token in '{key}'")
                        break
                
                if not token:
                    print(f"[SCHEDULER] No token in response: {list(data.keys())}")
                    return False
                
                self.token = token
                
                # Try to extract expiration
                expires_in = data.get("expires_in")
                if expires_in:
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                    print(f"[SCHEDULER] Token expires at: {self.token_expires_at}")
                else:
                    print("[SCHEDULER] No expiration info in response")
                
                print("[SCHEDULER] Login successful!")
                return True
        
        except Exception as e:
            print(f"[SCHEDULER] Login error: {type(e).__name__}: {str(e)[:150]}")
            return False
    
    async def refresh_token(self) -> bool:
        """
        Refresh the token if it's expired or about to expire.
        
        Returns:
            True if still valid or refreshed successfully
        """
        # Check if token exists and is still valid (with 5-min buffer)
        if self.token and self.token_expires_at:
            if datetime.now() < (self.token_expires_at - timedelta(minutes=5)):
                return True  # Token still valid
        
        # Token expired or missing - try to refresh
        print("[SCHEDULER] Token expired or missing, re-authenticating...")
        return await self.login()
    
    async def get_token(self, force_refresh: bool = False) -> Optional[str]:
        """
        Get a valid token, logging in if necessary.
        
        Args:
            force_refresh: Force a new login even if token is valid
        
        Returns:
            Token string, or None if unable to obtain
        """
        if force_refresh:
            success = await self.login()
        else:
            success = await self.refresh_token()
        
        return self.token if success else None
    
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
        Make an API call to scheduler.walmart.com with automatic token injection.
        
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
            Exception if token can't be obtained
        """
        # Ensure valid token
        token = await self.get_token()
        if not token:
            raise Exception("Unable to obtain scheduler token")
        
        # Build URL
        if endpoint.startswith("http"):
            url = endpoint
        else:
            url = f"{self.base_url}{endpoint}"
        
        # Build headers with token
        req_headers = headers or {}
        
        if self.auth_method == "api_key":
            req_headers["X-API-Key"] = self.api_key
        elif self.auth_method == "credentials":
            req_headers["Authorization"] = f"Bearer {token}"
        
        req_headers["User-Agent"] = "CodePuppyDAR/1.0"
        
        # Make request
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            print(f"[SCHEDULER] {method} {url}")
            
            response = await client.request(
                method,
                url,
                headers=req_headers,
                json=json_data,
                params=params,
                **kwargs
            )
            
            # Handle 401 (token expired) - try refresh once
            if response.status_code == 401:
                print("[SCHEDULER] Got 401 Unauthorized - token may be expired, refreshing...")
                token = await self.get_token(force_refresh=True)
                
                if token:
                    req_headers["Authorization"] = f"Bearer {token}"
                    print(f"[SCHEDULER] Retrying {method} {url}")
                    
                    response = await client.request(
                        method,
                        url,
                        headers=req_headers,
                        json=json_data,
                        params=params,
                        **kwargs
                    )
            
            return response
    
    async def close(self):
        """Close the client."""
        if self.client:
            await self.client.aclose()


# Global instance (lazy loaded)
_scheduler_client: Optional[SchedulerClient] = None

async def get_scheduler_client() -> SchedulerClient:
    """Get or create the global scheduler client."""
    global _scheduler_client
    if _scheduler_client is None:
        _scheduler_client = SchedulerClient()
        # Try initial login
        await _scheduler_client.get_token()
    return _scheduler_client


# Example usage (for testing):
if __name__ == "__main__":
    async def test():
        client = SchedulerClient()
        
        # Get token (will auto-login)
        token = await client.get_token()
        print(f"Token obtained: {token[:50] if token else 'FAILED'}...")
        
        # Make API call (token attached automatically)
        try:
            response = await client.api_call("/api/some/endpoint", method="GET")
            print(f"Response: {response.status_code}")
            print(response.json())
        except Exception as e:
            print(f"Error: {e}")
    
    asyncio.run(test())
