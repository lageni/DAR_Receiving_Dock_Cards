"""
Scheduler JWT Token Extractor

Automatically logs into Walmart Scheduler via PingFederate SAML
and extracts the JWT token. No browser required - uses requests library
with proper session and cookie handling.
"""

import os
import re
import json
import requests
import warnings
from urllib.parse import urlparse, parse_qs, urljoin

# Suppress SSL warnings
warnings.filterwarnings('ignore')


async def auto_extract_scheduler_token(username: str, password: str) -> dict:
    """
    Automatically extract JWT token from Walmart Scheduler.
    
    Handles the full PingFederate SAML authentication flow.
    
    Args:
        username: Walmart username (email)
        password: Walmart password
    
    Returns:
        Dict with status, token, and message
    """
    
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
    })
    
    try:
        print("[SCHEDULER AUTO-EXTRACT] Starting login sequence...")
        
        # Step 1: Request scheduler homepage - will redirect to PingFederate
        print("[SCHEDULER AUTO-EXTRACT] Requesting scheduler.walmart.com...")
        resp = session.get(
            "https://scheduler.walmart.com/",
            timeout=20,
            allow_redirects=True
        )
        current_url = resp.url
        print(f"[SCHEDULER AUTO-EXTRACT] Redirected to: {current_url}")
        
        # Step 2: Look for login form and extract it
        print("[SCHEDULER AUTO-EXTRACT] Parsing login page...")
        
        # Try to find form action and fields using regex
        form_action_match = re.search(r'<form[^>]+action=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
        form_action = None
        
        if form_action_match:
            form_action = form_action_match.group(1)
            print(f"[SCHEDULER AUTO-EXTRACT] Found form action: {form_action}")
        else:
            # Try common OAuth endpoints
            print("[SCHEDULER AUTO-EXTRACT] Form action not found, trying common endpoints...")
            form_action = "https://pfedprod.wal-mart.com/as/authorization.oauth2"
        
        # Make action absolute URL if relative
        if form_action and not form_action.startswith("http"):
            parsed = urlparse(current_url)
            form_action = f"{parsed.scheme}://{parsed.netloc}{form_action}"
        
        # Step 3: Extract hidden form fields
        print("[SCHEDULER AUTO-EXTRACT] Extracting form fields...")
        
        form_data = {}
        
        # Find all hidden inputs
        for match in re.finditer(r'<input[^>]+name=["\']([^"\']+)["\'][^>]+value=["\']([^"\']*)["\']', resp.text, re.IGNORECASE):
            field_name = match.group(1)
            field_value = match.group(2)
            form_data[field_name] = field_value
            print(f"[SCHEDULER AUTO-EXTRACT]   Field: {field_name}")
        
        # Add username and password
        username_field = None
        password_field = None
        
        # Find username field
        for pattern in [r'name=["\']?username["\']?', r'name=["\']?user["\']?', r'name=["\']?email["\']?', r'id=["\']?username["\']?']:
            if re.search(pattern, resp.text, re.IGNORECASE):
                username_field = "username"
                break
        
        if not username_field:
            # Try to extract from form
            match = re.search(r'<input[^>]+name=["\']([^"\']*user[^"\']*)["\']', resp.text, re.IGNORECASE)
            if match:
                username_field = match.group(1)
        
        if not username_field:
            username_field = "username"
        
        # Find password field
        match = re.search(r'<input[^>]+name=["\']([^"\']+)["\'][^>]*type=["\']?password', resp.text, re.IGNORECASE)
        if match:
            password_field = match.group(1)
        else:
            password_field = "password"
        
        form_data[username_field] = username
        form_data[password_field] = password
        
        print(f"[SCHEDULER AUTO-EXTRACT] Username field: {username_field}")
        print(f"[SCHEDULER AUTO-EXTRACT] Password field: {password_field}")
        
        # Step 4: Submit the form
        print("[SCHEDULER AUTO-EXTRACT] Submitting login form...")
        
        resp = session.post(
            form_action,
            data=form_data,
            timeout=20,
            allow_redirects=True
        )
        
        print(f"[SCHEDULER AUTO-EXTRACT] After login: {resp.url}")
        
        # Step 5: Extract token from URL or content
        print("[SCHEDULER AUTO-EXTRACT] Extracting JWT token...")
        
        # Try from URL first
        token = extract_token_from_url(resp.url)
        
        if not token:
            # Try from page content
            token = extract_token_from_html(resp.text)
        
        if token and token.startswith("eyJ"):
            print(f"[SCHEDULER AUTO-EXTRACT] Token extracted: {token[:50]}...")
            return {
                "status": "success",
                "token": token,
                "message": "Token extracted successfully"
            }
        else:
            print("[SCHEDULER AUTO-EXTRACT] No token found in response")
            print(f"[SCHEDULER AUTO-EXTRACT] Final URL: {resp.url}")
            
            # Log first 500 chars of response for debugging
            print(f"[SCHEDULER AUTO-EXTRACT] Response preview: {resp.text[:500]}")
            
            return {
                "status": "error",
                "message": "Token not found. Login may have failed or form structure is different."
            }
    
    except requests.exceptions.Timeout:
        print("[SCHEDULER AUTO-EXTRACT] Request timeout")
        return {
            "status": "error",
            "message": "Request timeout - Walmart servers unreachable"
        }
    except requests.exceptions.ConnectionError as e:
        print(f"[SCHEDULER AUTO-EXTRACT] Connection error: {str(e)[:100]}")
        return {
            "status": "error",
            "message": "Connection error - check network/VPN"
        }
    except Exception as e:
        print(f"[SCHEDULER AUTO-EXTRACT] Error: {type(e).__name__}: {str(e)[:150]}")
        return {
            "status": "error",
            "message": f"Error: {str(e)[:200]}"
        }


def extract_token_from_url(url: str) -> str:
    """Extract JWT token from URL parameters."""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        if "uat" in params:
            token = params["uat"][0]
            if token.startswith("eyJ"):
                return token
    except:
        pass
    
    return None


def extract_token_from_html(html: str) -> str:
    """Extract JWT token from HTML content."""
    try:
        # Look for uat parameter in any context
        pattern = r'uat[=:](["\']?)([a-zA-Z0-9_\-\.]+)["\']?'
        match = re.search(pattern, html)
        
        if match:
            token = match.group(2)
            if token.startswith("eyJ"):
                return token
        
        # Also try looking for redirect URLs with uat
        pattern = r'href=["\']([^"\']*uat=[^&"\']+)["\']'
        match = re.search(pattern, html)
        
        if match:
            url = match.group(1)
            token = extract_token_from_url(url)
            if token:
                return token
    except:
        pass
    
    return None


def save_token_to_env(token: str) -> bool:
    """Save token to .env file."""
    try:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        
        # Read existing content
        content = ""
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                content = f.read()
        
        # Remove old SCHEDULER_JWT_TOKEN line
        lines = content.split("\n")
        lines = [line for line in lines if not line.startswith("SCHEDULER_JWT_TOKEN=")]
        
        # Add new token
        lines.append(f"SCHEDULER_JWT_TOKEN={token}")
        
        # Write back
        with open(env_file, "w") as f:
            f.write("\n".join(lines))
        
        print("[SCHEDULER AUTO-EXTRACT] Token saved to .env")
        return True
    
    except Exception as e:
        print(f"[SCHEDULER AUTO-EXTRACT] Error saving token: {str(e)[:100]}")
        return False
