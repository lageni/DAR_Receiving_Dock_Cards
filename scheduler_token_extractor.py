import os
import re
import requests
import warnings
from urllib.parse import parse_qs, urlparse

warnings.filterwarnings('ignore')


def extract_form_action(html: str) -> str:
    match = re.search(r'<form[^>]*action=["\']([^"\']+)["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def extract_form_data(html: str) -> dict:
    data = {}
    for match in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\'](?:[^>]*value=["\']([^"\']*)["\'])?', html, re.IGNORECASE):
        name = match.group(1)
        value = match.group(2) or ""
        if name:
            data[name] = value
    return data


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
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    
    try:
        print(f"[TOKEN] Logging in as {username}...")
        
        resp = session.get("https://scheduler.walmart.com/", timeout=15, allow_redirects=True)
        
        # Extract form
        form_action = extract_form_action(resp.text)
        if not form_action:
            print("[TOKEN] Form not found")
            return {"status": "error", "message": "Login form not found"}
        
        if not form_action.startswith("http"):
            parsed = urlparse(resp.url)
            form_action = f"{parsed.scheme}://{parsed.netloc}{form_action}"
        
        print(f"[TOKEN] Submitting to {form_action}")
        
        # Get form fields
        form_data = extract_form_data(resp.text)
        form_data['username'] = username
        form_data['password'] = password
        
        # Submit
        resp = session.post(form_action, data=form_data, timeout=15, allow_redirects=True)
        
        # Check URL
        token = extract_token_from_url(resp.url)
        if token:
            print("[TOKEN] Got token from URL")
            return {"status": "success", "token": token}
        
        # Check HTML
        token = extract_token_from_html(resp.text)
        if token:
            print("[TOKEN] Got token from HTML")
            return {"status": "success", "token": token}
        
        print(f"[TOKEN] No token found. URL: {resp.url}")
        return {"status": "error", "message": "Token not found"}
    
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
