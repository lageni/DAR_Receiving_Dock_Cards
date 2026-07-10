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
    })
    
    try:
        print(f"[TOKEN] Logging in as {username}...")
        
        # Get login page
        resp = session.get("https://scheduler.walmart.com/", timeout=15, allow_redirects=True)
        print(f"[TOKEN] Got: {resp.url[:80]}")
        
        # Find form action
        form_match = re.search(r'<form[^>]*action=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
        if not form_match:
            return {"status": "error", "message": "Login form not found"}
        
        form_action = form_match.group(1)
        if not form_action.startswith("http"):
            parsed = urlparse(resp.url)
            form_action = f"{parsed.scheme}://{parsed.netloc}{form_action}"
        
        print(f"[TOKEN] Form: {form_action}")
        
        # Extract form fields
        form_data = {}
        for match in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\'](?:[^>]*value=["\']([^"\']*)["\'])?', resp.text, re.IGNORECASE):
            form_data[match.group(1)] = match.group(2) or ""
        
        # Add credentials
        form_data['pf.username'] = username if "@" in username else f"{username}@wmsc.wal-mart.com"
        form_data['pf.pass'] = password
        form_data['pf.ok'] = "clicked"
        
        print(f"[TOKEN] Submitting form...")
        resp = session.post(form_action, data=form_data, timeout=15, allow_redirects=True)
        print(f"[TOKEN] Response: {resp.url[:80]}")
        
        # Check URL
        token = extract_token_from_url(resp.url)
        if token:
            return {"status": "success", "token": token}
        
        # Check HTML
        token = extract_token_from_html(resp.text)
        if token:
            return {"status": "success", "token": token}
        
        return {"status": "error", "message": "No token received"}
    
    except Exception as e:
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
