import os
import re
import requests
import warnings
from urllib.parse import parse_qs, urlparse

warnings.filterwarnings('ignore')


def extract_token_from_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if 'uat' in params:
        token = params['uat'][0]
        if token.startswith('eyJ'):
            return token
    return None


def extract_token_from_html(html: str) -> str:
    match = re.search(r'uat[=:](["\']?)([a-zA-Z0-9_\-\.]+)\1', html)
    if match:
        token = match.group(2)
        if token.startswith('eyJ') and len(token) > 50:
            return token
    return None


async def extract_token(username: str, password: str) -> dict:
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    
    try:
        print(f"[TOKEN] Logging in as {username}...")
        
        # Get initial redirect to PingFederate
        resp = session.get("https://scheduler.walmart.com/", timeout=15, allow_redirects=True)
        print(f"[TOKEN] Redirected to: {resp.url}")
        
        # Submit credentials directly to authorization endpoint
        auth_url = "https://pfedprod.wal-mart.com/as/authorization.oauth2"
        
        login_data = {
            "username": username,
            "password": password,
            "client_id": "scheduler",
        }
        
        print(f"[TOKEN] Submitting to {auth_url}")
        resp = session.post(auth_url, data=login_data, timeout=15, allow_redirects=True)
        
        print(f"[TOKEN] Response: {resp.url[:100]}")
        
        # Check URL for token
        token = extract_token_from_url(resp.url)
        if token:
            print("[TOKEN] Token found!")
            return {"status": "success", "token": token}
        
        # Check HTML for token
        token = extract_token_from_html(resp.text)
        if token:
            print("[TOKEN] Token found in HTML!")
            return {"status": "success", "token": token}
        
        # Check for redirect with form
        if 'form' in resp.text.lower():
            match = re.search(r'<form[^>]*action=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
            if match:
                form_action = match.group(1)
                if not form_action.startswith("http"):
                    parsed = urlparse(resp.url)
                    form_action = f"{parsed.scheme}://{parsed.netloc}{form_action}"
                
                print(f"[TOKEN] Found form, submitting to {form_action}")
                
                form_data = {}
                for m in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\'](?:[^>]*value=["\']([^"\']*)["\'])?', resp.text, re.IGNORECASE):
                    form_data[m.group(1)] = m.group(2) or ""
                
                form_data['username'] = username
                form_data['password'] = password
                
                resp = session.post(form_action, data=form_data, timeout=15, allow_redirects=True)
                print(f"[TOKEN] Form response: {resp.url[:100]}")
                
                token = extract_token_from_url(resp.url)
                if token:
                    return {"status": "success", "token": token}
                
                token = extract_token_from_html(resp.text)
                if token:
                    return {"status": "success", "token": token}
        
        print("[TOKEN] No token found in response")
        return {"status": "error", "message": "Login failed or credentials invalid"}
    
    except Exception as e:
        print(f"[TOKEN] Error: {str(e)}")
        return {"status": "error", "message": str(e)[:100]}


def save_token(token: str) -> bool:
    try:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        content = ""
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                content = f.read()
        
        lines = [l for l in content.split("\n") if not l.startswith("SCHEDULER_JWT_TOKEN=")]
        lines.append(f"SCHEDULER_JWT_TOKEN={token}")
        
        with open(env_file, "w") as f:
            f.write("\n".join(lines))
        
        return True
    except:
        return False
