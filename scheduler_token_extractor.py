import os
import re
import requests
import warnings
from urllib.parse import parse_qs, urlparse

warnings.filterwarnings('ignore')


async def extract_token(username: str, password: str) -> dict:
    session = requests.Session()
    session.verify = False
    
    try:
        resp = session.get("https://scheduler.walmart.com/", timeout=15, allow_redirects=True)
        url = resp.url
        
        form_match = re.search(r'<form[^>]*action=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
        if not form_match:
            return {"status": "error", "message": "Form not found"}
        
        form_action = form_match.group(1)
        if not form_action.startswith("http"):
            parsed = urlparse(url)
            form_action = f"{parsed.scheme}://{parsed.netloc}{form_action}"
        
        form_data = {}
        for match in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']', resp.text, re.IGNORECASE):
            form_data[match.group(1)] = match.group(2)
        
        form_data['username'] = username
        form_data['password'] = password
        
        resp = session.post(form_action, data=form_data, timeout=15, allow_redirects=True)
        
        parsed = urlparse(resp.url)
        params = parse_qs(parsed.query)
        
        if 'uat' in params:
            token = params['uat'][0]
            if token.startswith('eyJ'):
                return {"status": "success", "token": token}
        
        return {"status": "error", "message": "Token not found"}
    
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
