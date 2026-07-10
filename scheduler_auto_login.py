"""
Walmart Scheduler Automatic SSO Login & JWT Extraction

Automatically logs into scheduler.walmart.com using Playwright,
extracts the JWT token, and stores it for API calls.

No manual token extraction needed!
"""

import os
import asyncio
import json
import re
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse, parse_qs


class SchedulerAutoLogin:
    """
    Automatically login to Walmart Scheduler and extract JWT token.
    Uses Playwright to handle PingFederate SSO.
    """
    
    def __init__(self):
        self.username = os.getenv("WALMART_USERNAME", "").strip()
        self.password = os.getenv("WALMART_PASSWORD", "").strip()
        self.jwt_token = None
        self.token_expires_at = None
        
        if not (self.username and self.password):
            print("[SCHEDULER AUTO-LOGIN] ERROR: WALMART_USERNAME and WALMART_PASSWORD required in .env")
            print("[SCHEDULER AUTO-LOGIN] Add to .env:")
            print("[SCHEDULER AUTO-LOGIN]   WALMART_USERNAME=your.name@walmart.com")
            print("[SCHEDULER AUTO-LOGIN]   WALMART_PASSWORD=your_password")
    
    async def login(self) -> bool:
        """
        Automatically login to scheduler.walmart.com and extract JWT token.
        
        Returns:
            True if successful, False otherwise
        """
        if not (self.username and self.password):
            print("[SCHEDULER AUTO-LOGIN] Cannot login: credentials not configured")
            return False
        
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            print("[SCHEDULER AUTO-LOGIN] ERROR: Playwright not installed")
            print("[SCHEDULER AUTO-LOGIN] Run: uv sync")
            return False
        
        print("[SCHEDULER AUTO-LOGIN] Starting automatic login...")
        
        try:
            async with async_playwright() as p:
                # Launch browser (headless - no UI)
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                # Set a custom header to look like a browser
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => false,
                    });
                """)
                
                print("[SCHEDULER AUTO-LOGIN] Navigating to scheduler.walmart.com...")
                
                # Navigate to scheduler
                try:
                    await page.goto("https://scheduler.walmart.com/", timeout=30000, wait_until="networkidle")
                except:
                    # Page might redirect, that's ok
                    pass
                
                # Check if we're on login page
                current_url = page.url
                print(f"[SCHEDULER AUTO-LOGIN] Current URL: {current_url}")
                
                # Look for login form
                login_page_loaded = False
                for attempt in range(5):
                    try:
                        # Try to find username input
                        username_input = await page.query_selector("input[type='text']")
                        if username_input:
                            login_page_loaded = True
                            print("[SCHEDULER AUTO-LOGIN] Found login form")
                            break
                        
                        # Also try common login field names
                        for selector in ["input[name*='username']", "input[name*='user']", "input[name*='email']", "input[id*='username']"]:
                            elem = await page.query_selector(selector)
                            if elem:
                                login_page_loaded = True
                                print("[SCHEDULER AUTO-LOGIN] Found login form")
                                break
                        
                        if login_page_loaded:
                            break
                        
                        await asyncio.sleep(1)
                    except:
                        pass
                
                if not login_page_loaded:
                    print("[SCHEDULER AUTO-LOGIN] Could not find login form")
                    await browser.close()
                    return False
                
                # Find and fill username
                print(f"[SCHEDULER AUTO-LOGIN] Entering username: {self.username}")
                
                username_selector = None
                for selector in ["input[type='text']", "input[name*='username']", "input[name*='user']", "input[name*='email']", "input[id*='username']"]:
                    elem = await page.query_selector(selector)
                    if elem:
                        username_selector = selector
                        break
                
                if username_selector:
                    await page.fill(username_selector, self.username)
                
                # Find and fill password
                print("[SCHEDULER AUTO-LOGIN] Entering password...")
                password_input = await page.query_selector("input[type='password']")
                if password_input:
                    await page.fill("input[type='password']", self.password)
                
                # Submit form
                submit_button = None
                for selector in ["button[type='submit']", "input[type='submit']", "button:has-text('Login')", "button:has-text('Sign in')"]:
                    try:
                        btn = await page.query_selector(selector)
                        if btn:
                            submit_button = selector
                            break
                    except:
                        pass
                
                if submit_button:
                    print("[SCHEDULER AUTO-LOGIN] Submitting login form...")
                    await page.click(submit_button)
                    
                    # Wait for redirect after login
                    try:
                        await page.wait_for_url("**/scheduler/**", timeout=30000)
                    except:
                        pass
                
                # Wait for page to settle
                await asyncio.sleep(2)
                
                # Get current URL
                current_url = page.url
                print(f"[SCHEDULER AUTO-LOGIN] After login URL: {current_url}")
                
                # Extract JWT token from URL
                self.jwt_token = self._extract_token_from_url(current_url)
                
                if not self.jwt_token:
                    # Try to get from page content
                    content = await page.content()
                    self.jwt_token = self._extract_token_from_html(content)
                
                await browser.close()
                
                if self.jwt_token:
                    print(f"[SCHEDULER AUTO-LOGIN] JWT token extracted successfully!")
                    self._log_token_info()
                    return True
                else:
                    print("[SCHEDULER AUTO-LOGIN] Failed to extract JWT token")
                    return False
        
        except Exception as e:
            print(f"[SCHEDULER AUTO-LOGIN] Error: {type(e).__name__}: {str(e)[:200]}")
            return False
    
    def _extract_token_from_url(self, url: str) -> Optional[str]:
        """Extract JWT token from URL parameters."""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            # Look for uat parameter (JWT token)
            if "uat" in params:
                token = params["uat"][0]
                if token.startswith("eyJ"):
                    return token
            
            return None
        except:
            return None
    
    def _extract_token_from_html(self, html: str) -> Optional[str]:
        """Extract JWT token from HTML content."""
        try:
            # Look for uat= in the page
            pattern = r'uat=([^&\s"]+)'
            match = re.search(pattern, html)
            if match:
                token = match.group(1)
                if token.startswith("eyJ"):
                    return token
            
            return None
        except:
            return None
    
    def _log_token_info(self):
        """Log token expiration info."""
        if not self.jwt_token:
            return
        
        try:
            import base64
            parts = self.jwt_token.split(".")
            if len(parts) == 3:
                payload_str = parts[1]
                padding = 4 - (len(payload_str) % 4)
                if padding != 4:
                    payload_str += "=" * padding
                
                payload = json.loads(base64.urlsafe_b64decode(payload_str))
                
                if "exp" in payload:
                    exp_timestamp = payload["exp"]
                    exp_datetime = datetime.fromtimestamp(exp_timestamp)
                    print(f"[SCHEDULER AUTO-LOGIN] Token expires: {exp_datetime}")
                    self.token_expires_at = exp_datetime
                    
                    remaining = (exp_datetime - datetime.now()).total_seconds() / 3600
                    print(f"[SCHEDULER AUTO-LOGIN] Token valid for {remaining:.1f} hours")
        except Exception as e:
            print(f"[SCHEDULER AUTO-LOGIN] Could not decode token: {str(e)[:100]}")
    
    def get_token(self) -> Optional[str]:
        """Get the extracted JWT token."""
        return self.jwt_token
    
    def save_to_env(self, env_file: str = ".env") -> bool:
        """Save token to .env file for persistent storage."""
        if not self.jwt_token:
            print("[SCHEDULER AUTO-LOGIN] No token to save")
            return False
        
        try:
            # Read existing .env
            env_content = ""
            if os.path.exists(env_file):
                with open(env_file, "r") as f:
                    env_content = f.read()
            
            # Remove old SCHEDULER_JWT_TOKEN if exists
            lines = env_content.split("\n")
            new_lines = [line for line in lines if not line.startswith("SCHEDULER_JWT_TOKEN=")]
            
            # Add new token
            new_lines.append(f"SCHEDULER_JWT_TOKEN={self.jwt_token}")
            
            # Write back
            with open(env_file, "w") as f:
                f.write("\n".join(new_lines))
            
            print(f"[SCHEDULER AUTO-LOGIN] Token saved to {env_file}")
            return True
        
        except Exception as e:
            print(f"[SCHEDULER AUTO-LOGIN] Error saving to .env: {str(e)[:100]}")
            return False


# Auto-login on module import (runs on startup)
async def auto_login_on_startup():
    """Run automatic login when the application starts."""
    client = SchedulerAutoLogin()
    
    if client.username and client.password:
        print("[SCHEDULER AUTO-LOGIN] Running automatic login on startup...")
        success = await client.login()
        
        if success and client.jwt_token:
            # Save to .env for next restart
            client.save_to_env()
            print("[SCHEDULER AUTO-LOGIN] Ready to use!")
            return client.jwt_token
    
    return None


if __name__ == "__main__":
    async def test():
        token = await auto_login_on_startup()
        if token:
            print(f"Token: {token[:50]}...")
    
    asyncio.run(test())
