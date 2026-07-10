"""
Walmart SSO (Single Sign-On) Client

Handles OAuth2 authorization code flow:
1. Redirect to login.walmart.com
2. Exchange code for token
3. Auto-refresh token on expiration
4. Transparent token injection on API calls

Configuration needed from .env:
- SCHEDULER_CLIENT_ID
- SCHEDULER_CLIENT_SECRET
- SCHEDULER_AUTH_ENDPOINT
- SCHEDULER_TOKEN_ENDPOINT
- SCHEDULER_REDIRECT_URI
- Optional: SCHEDULER_USERNAME, SCHEDULER_PASSWORD (for programmatic login)
"""

import os
import json
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode, parse_qs, urlparse
import secrets

class SSOClient:
    """
    Walmart SSO OAuth2 client with automatic token management.
    """
    
    def __init__(self):
        # OAuth2 Configuration
        self.client_id = os.getenv("SCHEDULER_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("SCHEDULER_CLIENT_SECRET", "").strip()
        self.auth_endpoint = os.getenv("SCHEDULER_AUTH_ENDPOINT", "").strip()
        self.token_endpoint = os.getenv("SCHEDULER_TOKEN_ENDPOINT", "").strip()
        self.redirect_uri = os.getenv("SCHEDULER_REDIRECT_URI", "").strip()
        
        # Optional: username/password for programmatic login
        self.username = os.getenv("SCHEDULER_USERNAME", "").strip()
        self.password = os.getenv("SCHEDULER_PASSWORD", "").strip()
        
        # Token management
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.state = None  # CSRF protection
        
        self.base_url = "https://scheduler.walmart.com"
        
        self._validate_config()
    
    def _validate_config(self):
        """Validate that SSO configuration is complete."""
        if not all([self.client_id, self.client_secret, self.auth_endpoint, self.token_endpoint, self.redirect_uri]):
            print("[SSO] WARNING: Incomplete SSO configuration")
            print(f"[SSO]   CLIENT_ID: {self.client_id if self.client_id else 'MISSING'}")
            print(f"[SSO]   CLIENT_SECRET: {self.client_secret if self.client_secret else 'MISSING'}")
            print(f"[SSO]   AUTH_ENDPOINT: {self.auth_endpoint if self.auth_endpoint else 'MISSING'}")
            print(f"[SSO]   TOKEN_ENDPOINT: {self.token_endpoint if self.token_endpoint else 'MISSING'}")
            print(f"[SSO]   REDIRECT_URI: {self.redirect_uri if self.redirect_uri else 'MISSING'}")
            print("[SSO] See SSO_INSPECTION_GUIDE.md to capture these values")
            return False
        return True
    
    def get_login_url(self) -> str:
        """
        Generate the login URL to redirect user to.
        
        In browser-based flow, user would visit this URL.
        For server-side, this is informational only.
        
        Returns:
            Full login URL with auth code request
        """
        if not self._validate_config():
            raise Exception("SSO not configured")
        
        # Generate state for CSRF protection
        self.state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": self.state,
            # Add username/password if available (for programmatic login)
            **({"username": self.username} if self.username else {}),
            **({"password": self.password} if self.password else {}),
        }
        
        login_url = f"{self.auth_endpoint}?{urlencode(params)}"
        print(f"[SSO] Login URL: {login_url}")
        return login_url
    
    async def exchange_code_for_token(self, auth_code: str) -> bool:
        """
        Exchange authorization code for access token.
        
        Args:
            auth_code: Authorization code from callback URL
        
        Returns:
            True if successful, False otherwise
        """
        if not self._validate_config():
            return False
        
        print(f"[SSO] Exchanging auth code for token...")
        
        try:
            token_data = {
                "grant_type": "authorization_code",
                "code": auth_code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            }
            
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                print(f"[SSO] POST {self.token_endpoint}")
                response = await client.post(
                    self.token_endpoint,
                    json=token_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    print(f"[SSO] Token exchange failed: HTTP {response.status_code}")
                    print(f"[SSO] Response: {response.text[:200]}")
                    return False
                
                data = response.json()
                
                # Extract token fields (try common names)
                self.access_token = data.get("access_token") or data.get("token")
                self.refresh_token = data.get("refresh_token")
                
                if not self.access_token:
                    print(f"[SSO] No access_token in response: {list(data.keys())}")
                    return False
                
                # Extract expiration
                expires_in = data.get("expires_in")
                if expires_in:
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                    print(f"[SSO] Token obtained. Expires at: {self.token_expires_at}")
                else:
                    print("[SSO] Token obtained (no expiration info)")
                
                return True
        
        except Exception as e:
            print(f"[SSO] Token exchange error: {type(e).__name__}: {str(e)[:150]}")
            return False
    
    async def refresh_access_token(self) -> bool:
        """
        Refresh the access token using refresh token.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.refresh_token:
            print("[SSO] No refresh token available")
            return False
        
        if not self._validate_config():
            return False
        
        print("[SSO] Refreshing access token...")
        
        try:
            refresh_data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.post(
                    self.token_endpoint,
                    json=refresh_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    print(f"[SSO] Token refresh failed: HTTP {response.status_code}")
                    return False
                
                data = response.json()
                self.access_token = data.get("access_token") or data.get("token")
                
                # Update expiration
                expires_in = data.get("expires_in")
                if expires_in:
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                print("[SSO] Token refreshed successfully")
                return True
        
        except Exception as e:
            print(f"[SSO] Token refresh error: {type(e).__name__}: {str(e)[:150]}")
            return False
    
    def _token_expired(self) -> bool:
        """Check if token is expired or about to expire (5-min buffer)."""
        if not self.access_token or not self.token_expires_at:
            return True
        
        return datetime.now() >= (self.token_expires_at - timedelta(minutes=5))
    
    async def ensure_valid_token(self) -> bool:
        """
        Ensure we have a valid token. Refresh if needed.
        
        Returns:
            True if token is valid, False if unable to obtain
        """
        if self._token_expired():
            if self.refresh_token:
                return await self.refresh_access_token()
            else:
                print("[SSO] Token expired and no refresh token available")
                return False
        
        return bool(self.access_token)
    
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
        if not await self.ensure_valid_token():
            raise Exception("Unable to obtain valid SSO token")
        
        # Build URL
        if endpoint.startswith("http"):
            url = endpoint
        else:
            url = f"{self.base_url}{endpoint}"
        
        # Build headers with token
        req_headers = headers or {}
        req_headers["Authorization"] = f"Bearer {self.access_token}"
        req_headers["User-Agent"] = "CodePuppyDAR/1.0"
        
        # Make request
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            print(f"[SSO] {method} {url}")
            
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
                print("[SSO] Got 401 Unauthorized - refreshing token...")
                if await self.refresh_access_token():
                    req_headers["Authorization"] = f"Bearer {self.access_token}"
                    print(f"[SSO] Retrying {method} {url}")
                    
                    response = await client.request(
                        method,
                        url,
                        headers=req_headers,
                        json=json_data,
                        params=params,
                        **kwargs
                    )
            
            return response


# Example usage
if __name__ == "__main__":
    async def test():
        client = SSOClient()
        
        # In real flow:
        # 1. Get user to visit login URL
        login_url = client.get_login_url()
        print(f"Send user to: {login_url}")
        
        # 2. User logs in, gets redirected back with code
        # 3. Extract code from callback and exchange it
        # auth_code = "code_from_callback_url"
        # await client.exchange_code_for_token(auth_code)
        
        # 4. Make API calls (token handled automatically)
        # response = await client.api_call("/api/endpoint")
    
    asyncio.run(test())
