"""
Scheduler Token Auto-Extraction via API

POST /api/scheduler/auto-extract with username and password
Server handles full login flow and stores token in .env
"""

import os
import re
import requests
from urllib.parse import urlparse, parse_qs
from html.parser import HTMLParser


class FormParser(HTMLParser):
    """Parse HTML forms to extract fields and actions."""
    
    def __init__(self):
        super().__init__()
        self.form_action = None
        self.form_method = "POST"
        self.fields = {}
        self.in_form = False
    
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == "form":
            self.in_form = True
            self.form_action = attrs_dict.get("action", "")
            self.form_method = attrs_dict.get("method", "POST").upper()
        
        elif tag == "input" and self.in_form:
            name = attrs_dict.get("name")
            value = attrs_dict.get("value", "")
            if name:
                self.fields[name] = value
    
    def handle_endtag(self, tag):
        if tag == "form":
            self.in_form = False


def extract_token_from_url(url: str) -> str:
    """Extract JWT token from URL."""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        if "uat" in params:
            return params["uat"][0]
    except:
        pass
    
    return None


async def auto_extract_scheduler_token(username: str, password: str) -> dict:
    """
    Automatically extract JWT token from Walmart Scheduler.
    
    Args:
        username: Walmart username
        password: Walmart password
    
    Returns:
        Dict with token and status
    """
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    try:
        print("[SCHEDULER AUTO-EXTRACT] Starting token extraction...")
        
        # Step 1: Initial request to scheduler
        print("[SCHEDULER AUTO-EXTRACT] Step 1: Requesting scheduler.walmart.com...")
        resp = session.get("https://scheduler.walmart.com/", timeout=15, allow_redirects=True)
        
        print(f"[SCHEDULER AUTO-EXTRACT] Redirected to: {resp.url}")
        
        # Step 2: Check if we're on Walmart login
        if "pfedprod.wal-mart.com" in resp.url or "login" in resp.url.lower():
            print("[SCHEDULER AUTO-EXTRACT] Step 2: On login page, extracting form...")
            
            # Parse the form
            parser = FormParser()
            parser.feed(resp.text)
            
            form_action = parser.form_action
            form_fields = parser.fields.copy()
            
            if not form_action:
                print("[SCHEDULER AUTO-EXTRACT] ERROR: Could not find login form")
                return {"status": "error", "message": "Could not find login form"}
            
            # Make form action absolute URL
            if form_action.startswith("/"):
                parsed_url = urlparse(resp.url)
                form_action = f"{parsed_url.scheme}://{parsed_url.netloc}{form_action}"
            
            print(f"[SCHEDULER AUTO-EXTRACT] Form action: {form_action}")
            
            # Step 3: Submit login form
            print("[SCHEDULER AUTO-EXTRACT] Step 3: Submitting credentials...")
            
            # Add username and password
            login_data = form_fields.copy()
            login_data["username"] = username
            login_data["password"] = password
            
            # Some forms use different field names
            for key in list(login_data.keys()):
                if "user" in key.lower():
                    login_data[key] = username
                if "pass" in key.lower():
                    login_data[key] = password
            
            resp = session.post(
                form_action,
                data=login_data,
                timeout=15,
                allow_redirects=True
            )
            
            print(f"[SCHEDULER AUTO-EXTRACT] After login: {resp.url}")
        
        # Step 4: Extract token from final URL
        print("[SCHEDULER AUTO-EXTRACT] Step 4: Extracting token...")
        
        token = extract_token_from_url(resp.url)
        
        if not token:
            # Check page content
            token_match = re.search(r'uat=([^&\s"]+)', resp.text)
            if token_match:
                token = token_match.group(1)
        
        if token:
            print(f"[SCHEDULER AUTO-EXTRACT] Token extracted: {token[:50]}...")
            return {
                "status": "success",
                "token": token,
                "message": "Token extracted successfully"
            }
        else:
            print("[SCHEDULER AUTO-EXTRACT] ERROR: Could not extract token from response")
            return {
                "status": "error",
                "message": "Token not found in response. Login may have failed."
            }
    
    except requests.exceptions.Timeout:
        print("[SCHEDULER AUTO-EXTRACT] ERROR: Request timeout")
        return {
            "status": "error",
            "message": "Request timeout. Walmart servers may be unreachable."
        }
    except Exception as e:
        print(f"[SCHEDULER AUTO-EXTRACT] ERROR: {str(e)[:150]}")
        return {
            "status": "error",
            "message": f"Error: {str(e)[:200]}"
        }


def save_token_to_env(token: str) -> bool:
    """Save token to .env file."""
    try:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        
        # Read existing .env
        content = ""
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                content = f.read()
        
        # Remove old token if exists
        lines = content.split("\n")
        lines = [line for line in lines if not line.startswith("SCHEDULER_JWT_TOKEN=")]
        
        # Add new token
        lines.append(f"SCHEDULER_JWT_TOKEN={token}")
        
        # Write back
        with open(env_file, "w") as f:
            f.write("\n".join(lines))
        
        print(f"[SCHEDULER AUTO-EXTRACT] Token saved to .env")
        return True
    
    except Exception as e:
        print(f"[SCHEDULER AUTO-EXTRACT] Error saving to .env: {str(e)[:100]}")
        return False
