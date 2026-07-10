# Capturing Fast SSO Redirects - Practical Solutions

## Problem
When you log in, scheduler.walmart.com redirects so fast that DevTools history clears before you can see the requests.

## Solution 1: Enable "Preserve Log" (EASIEST)

### Critical: Check This First!
1. Open DevTools (F12)
2. Click **Network** tab
3. **Look for checkbox: "Preserve log"** or gear icon → "Preserve log on navigation"
4. **CHECK THIS BOX** (it's unchecked by default!)
5. Now reload and login again
6. **All redirects will be preserved even through page changes**

This alone solves 90% of the problem!

---

## Solution 2: Check Browser History for the Callback URL

After you login, the browser visits the callback URL. You can see it in history:

1. Press **Ctrl+H** (open history)
2. Look for entries like:
   - `scheduler.walmart.com/callback?code=...`
   - `scheduler.walmart.com?code=...&state=...`
3. **Copy the full URL** from history
4. Paste in notepad to see parameters clearly

The `code=...` part is the auth code. The structure tells you about the flow.

---

## Solution 3: Create a Local Callback Endpoint

Set up a temporary endpoint on YOUR server to catch the redirect:

### Step 1: Add to main.py (temporarily)

```python
@app.get("/scheduler_callback")
async def scheduler_callback_capture(code: str = None, state: str = None, error: str = None):
    """Temporary endpoint to capture SSO callback parameters."""
    import json
    
    callback_data = {
        "code": code,
        "state": state,
        "error": error,
        "url": f"http://localhost:8000/scheduler_callback?code={code}&state={state}"
    }
    
    # Log to console and file
    print("[SCHEDULER CALLBACK] Captured redirect!")
    print(json.dumps(callback_data, indent=2))
    
    with open("callback_capture.txt", "a") as f:
        f.write(f"\n{'='*60}\n")
        f.write(json.dumps(callback_data, indent=2))
        f.write(f"\n{'='*60}\n")
    
    return f"""
    <html>
    <head>
        <title>SSO Callback Captured</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-green-50 p-6">
        <div class="max-w-2xl mx-auto">
            <div class="bg-green-100 border-2 border-green-400 rounded-lg p-6">
                <h1 class="text-2xl font-bold text-green-900 mb-4">Callback Captured!</h1>
                <p class="text-green-800 mb-4">The SSO callback was successfully intercepted. Details:</p>
                <div class="bg-white p-4 rounded font-mono text-sm overflow-auto max-h-96">
                    <p><strong>Code:</strong> {code}</p>
                    <p><strong>State:</strong> {state}</p>
                    <p><strong>Error:</strong> {error or 'None'}</p>
                </div>
                <div class="mt-4 p-4 bg-blue-100 border border-blue-400 rounded">
                    <p class="text-sm text-blue-900 mb-2"><strong>Next Steps:</strong></p>
                    <ol class="text-sm text-blue-900 list-decimal list-inside space-y-1">
                        <li>Check server console for full callback details</li>
                        <li>Check <code>callback_capture.txt</code> in project root</li>
                        <li>Use the code + state values in .env configuration</li>
                    </ol>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
```

### Step 2: Change the Redirect URI in .env (temporarily)

```env
SCHEDULER_REDIRECT_URI=http://localhost:8000/scheduler_callback
```

### Step 3: Test the Flow

1. Restart server
2. Go to scheduler.walmart.com
3. Click login
4. The login will redirect to YOUR local callback endpoint
5. You'll see the code + state parameters displayed!
6. Check `callback_capture.txt` file in project root

### Step 4: Restore Original REDIRECT_URI

After capturing, change back to:
```env
SCHEDULER_REDIRECT_URI=https://scheduler.walmart.com/callback
```

---

## Solution 4: Use Network Tab Timing Tricks

### Slow Down the Redirect
1. DevTools → Network tab
2. Click **gear icon** → Throttling → **Slow 3G**
3. This slows network, giving you time to see requests

### Set Network Breakpoint
1. DevTools → Network tab → click **gear icon**
2. Check: "Preserve log"
3. Check: "Disable cache"
4. Right-click any request → "Add request blocking rule" for `/token` endpoint
   - This pauses the redirect, giving you time to capture

---

## Solution 5: Check Browser Cookies/Storage

After login, the auth code might be stored locally:

1. DevTools → **Application** tab
2. **Session Storage** → check for `code`, `auth_code`, `state`
3. **Local Storage** → same
4. **Cookies** → look for auth-related cookies

The code is sometimes stored before the redirect completes.

---

## Solution 6: Monitor Server Logs

When the callback happens, it may be logged:

1. Keep server terminal visible
2. Watch for log entries after login
3. Look for anything with "callback", "redirect", "code"
4. Server logs will show the incoming request with parameters

---

## Best Approach (Combination)

1. **FIRST:** Enable "Preserve log" in DevTools ← This fixes it for most cases!
2. **SECOND:** Use callback capture endpoint (Solution 3) if you need the exact format
3. **THIRD:** Check browser history if redirect is still too fast

---

## Step-by-Step for You

### Method A: Using Preserve Log (30 seconds)

```
1. Open DevTools (F12)
2. Network tab → Check "Preserve log" checkbox
3. Reload page + login
4. Watch all requests (they'll stay in history)
5. Look for:
   - Redirect to login.walmart.com
   - POST to token endpoint
   - Redirect back to callback
6. Copy token endpoint request → Copy as cURL
7. Examine response for token format
```

### Method B: Using Callback Capture (2 minutes)

```
1. Add temporary endpoint to main.py (code above)
2. Change SCHEDULER_REDIRECT_URI in .env to:
   http://localhost:8000/scheduler_callback
3. Restart server
4. Go to scheduler.walmart.com
5. Login
6. Browser redirects to YOUR endpoint
7. See callback parameters displayed
8. Check callback_capture.txt for full details
9. Restore original REDIRECT_URI and remove endpoint
```

### Method C: Using Browser History (1 minute)

```
1. Login to scheduler.walmart.com normally
2. Press Ctrl+H (browser history)
3. Look for callback URL with code parameter
4. Right-click → Copy
5. Paste in notepad to examine
```

---

## What You're Looking For

### From Token Endpoint Request:
```json
{
  "grant_type": "authorization_code",
  "code": "ABC123...",
  "client_id": "...",
  "client_secret": "...",
  "redirect_uri": "https://scheduler.walmart.com/callback"
}
```

### From Token Endpoint Response:
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "..."
}
```

### From Callback URL:
```
https://scheduler.walmart.com/callback?code=AUTH_CODE&state=STATE_VALUE
```

---

## Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| "I can't see the redirect" | Enable "Preserve log" in DevTools Network tab |
| "History got cleared" | Use callback capture endpoint (Solution 3) |
| "Too many requests" | Filter Network tab by "xhr" or "fetch" |
| "Can't find token endpoint" | Look for largest POST request |
| "Still too fast" | Use network throttling (Slow 3G) |

---

## Pro Tips

1. **Preserve log is your friend** - Enable it first, always!
2. **Copy requests as cURL** - Right-click request → Copy as cURL shows everything
3. **Check Response tab** - That's where the token will be
4. **Use your server logs** - Add debug logging to capture incoming requests
5. **Check browser history** - Often overlooked but shows the callback URL

---

## If All Else Fails

Create a simple proxy script to capture traffic:

```python
# Simple capture server (save as capture.py)
from flask import Flask, request

app = Flask(__name__)

@app.route("/callback", methods=["GET"])
def capture():
    print("\n=== CALLBACK CAPTURED ===")
    print(f"URL: {request.url}")
    print(f"Args: {request.args}")
    print(f"Headers: {dict(request.headers)}")
    print("=" * 40 + "\n")
    
    return "Callback captured! Check terminal."

if __name__ == "__main__":
    app.run(port=5000)
```

Then:
1. Set `SCHEDULER_REDIRECT_URI=http://localhost:5000/callback`
2. Run: `python capture.py`
3. Login
4. See all callback parameters printed!

---

## Remember

The redirect itself isn't the problem - you can see it with "Preserve log" enabled. The key information is in:

1. **Token endpoint request** (shows what to send)
2. **Token endpoint response** (shows token format)
3. **Callback URL** (shows redirect_uri format)

**Enable "Preserve log" first - it solves 90% of this issue!**

