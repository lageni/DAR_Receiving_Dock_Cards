# Scheduler.walmart.com - Automatic SSO (Single Sign-On) Setup

## What Is SSO?

SSO (Single Sign-On) is a redirect-based authentication system:

```
[1] Your server tells browser: "Go to login.walmart.com"
    ↓
[2] Browser displays login form
    ↓
[3] User enters credentials
    ↓
[4] Browser redirects back to your server with auth code
    ↓
[5] Your server exchanges code for access token
    ↓
[6] Your server stores token and uses it for API calls
```

For **server-side automation**, steps [2-3] are manual (user logs in), but [1], [4-6] are automatic.

---

## 3-Step Setup

### Step 1: Capture the SSO Endpoints (10 minutes)

Follow the **SSO_INSPECTION_GUIDE.md** to find:

1. **AUTH_ENDPOINT** - Where to send users to login
   - Usually: `https://login.walmart.com/authorize`

2. **TOKEN_ENDPOINT** - Where to exchange auth code for token
   - Usually: `https://login.walmart.com/token`

3. **CLIENT_ID** - Application ID
   - Found in: DevTools → Page Source → search for "client_id"
   - Or: DevTools → Application → Session Storage → look for "client_id"

4. **CLIENT_SECRET** - Application secret
   - Found in: DevTools → Network tab → response body of token request
   - May be provided by Walmart IT if not visible

5. **REDIRECT_URI** - Where to redirect back after login
   - Usually: `https://scheduler.walmart.com/callback`

### Step 2: Add to .env

Edit `CodePuppyDAR/.env`:

```env
# Walmart SSO Configuration
SCHEDULER_CLIENT_ID=your_client_id_here
SCHEDULER_CLIENT_SECRET=your_client_secret_here
SCHEDULER_AUTH_ENDPOINT=https://login.walmart.com/authorize
SCHEDULER_TOKEN_ENDPOINT=https://login.walmart.com/token
SCHEDULER_REDIRECT_URI=https://scheduler.walmart.com/callback

# Optional: For programmatic login (username/password in backend)
SCHEDULER_USERNAME=your.name@walmart.com
SCHEDULER_PASSWORD=your_password_here
```

### Step 3: Test & Done!

1. **Restart server** (Ctrl+C, then run `RUN.bat`)
2. Go to **http://localhost:8000/admin**
3. Scroll to **"Scheduler.walmart.com - SSO"** section
4. Click **"Test SSO Configuration"**
5. Green message = Success!

---

## How to Find Each Value

### Finding CLIENT_ID

**Method 1: DevTools Network Tab**
1. Open scheduler.walmart.com
2. F12 → Network tab
3. Look for requests to login.walmart.com
4. Click on token exchange request
5. Go to **Request** tab
6. Look for `"client_id": "..."`

**Method 2: DevTools Application Tab**
1. F12 → Application → Session Storage
2. Look for key `client_id`
3. Copy the value

**Method 3: Page Source**
1. Right-click on page → View Page Source
2. Search (Ctrl+F): "client_id"
3. Find the value near it

### Finding CLIENT_SECRET

**Method 1: Token Response**
1. F12 → Network tab
2. Find POST to token endpoint
3. Go to **Response** tab
4. Look for `"client_secret": "..."`

**Method 2: Contact Walmart IT**
If you can't find it publicly, ask Walmart IT for the client secret for scheduler.walmart.com

### Finding AUTH_ENDPOINT

1. F12 → Network tab
2. Reload scheduler.walmart.com
3. Look for first request that redirects to login.walmart.com
4. Copy the URL (should be `/authorize` endpoint)

### Finding TOKEN_ENDPOINT

1. F12 → Network tab
2. Log in and watch network requests
3. Find POST request after entering credentials
4. Should be to `/token` endpoint
5. Copy the URL

### Finding REDIRECT_URI

This is where you get redirected back after login:
1. F12 → Network tab
2. After login, look for redirect back to scheduler.walmart.com
3. Usually has `?code=...` in the URL
4. The base is your REDIRECT_URI (usually `/callback`)

---

## What Happens After Setup

### Automatic Token Management
```
Client runs get_token()
    ↓
Check if token exists
    ├─ If valid: Use it
    └─ If expired: Refresh it
    ├─ If no refresh: Re-authenticate
```

### Transparent API Calls
```python
from sso_client import SSOClient

client = SSOClient()
response = await client.api_call("/api/endpoint")
# Token automatically injected!
```

### Token Refresh
- Token checked before every API call
- Auto-refreshed if expiring soon (5-min buffer)
- Auto-re-authenticates if refresh fails

---

## Environment Variables Reference

| Variable | Example | Required |
|----------|---------|----------|
| `SCHEDULER_CLIENT_ID` | `scheduler_app_123` | YES |
| `SCHEDULER_CLIENT_SECRET` | `secret_xyz_abc_123` | YES |
| `SCHEDULER_AUTH_ENDPOINT` | `https://login.walmart.com/authorize` | YES |
| `SCHEDULER_TOKEN_ENDPOINT` | `https://login.walmart.com/token` | YES |
| `SCHEDULER_REDIRECT_URI` | `https://scheduler.walmart.com/callback` | YES |
| `SCHEDULER_USERNAME` | `john.doe@walmart.com` | Optional |
| `SCHEDULER_PASSWORD` | `my_password` | Optional |

---

## Admin Page Features

Once configured, the admin page shows:

### Configuration Status
- Shows which SSO variables are set
- Green checkmarks = Ready
- Red X = Missing

### Test Button
- "Test SSO Configuration"
- Validates SSO setup
- Shows if ready to use

### Login URL Display
- Shows the exact login URL
- Useful for debugging
- Can be expanded/collapsed

---

## Troubleshooting

### Issue: "SSO Not Yet Configured"
**Solution:**
1. Check all 5 required .env variables are set
2. Restart server
3. Try again

### Issue: "SSO Configuration Loaded" but test fails
**Solution:**
1. Verify each value in .env matches what you found in DevTools
2. Check for typos
3. Verify REDIRECT_URI is correct

### Issue: Can't find CLIENT_SECRET
**Solution:**
1. It may not be publicly visible
2. Ask Walmart IT for the client secret
3. Or capture it from a network request

### Issue: Not sure which login URL is correct
**Solution:**
1. Use SSO_INSPECTION_GUIDE.md Phase 1-2
2. Follow the network requests step-by-step
3. The AUTH_ENDPOINT is the first redirect

---

## Using SSO in Your Code

### Basic Usage
```python
from sso_client import SSOClient

async def my_endpoint():
    client = SSOClient()
    
    # Auto-refresh token if needed
    response = await client.api_call(
        "/api/schedules",
        method="GET"
    )
    
    return response.json()
```

### Get Token Directly
```python
client = SSOClient()
token = await client.ensure_valid_token()
print(f"Current token: {token}")
```

### Exchange Auth Code
```python
client = SSOClient()
# After user logs in and gets redirected with code
success = await client.exchange_code_for_token(auth_code)
if success:
    print(f"Token: {client.access_token}")
```

---

## Security Notes

- **Never commit .env to Git** (it's already in .gitignore)
- **CLIENT_SECRET is sensitive** - don't share it
- **PASSWORD is sensitive** - don't hardcode it
- **Tokens in memory only** - not persisted to disk
- **Use HTTPS in production** - SSO requires secure connections

---

## Files Involved

| File | Purpose |
|------|---------|
| `sso_client.py` | Core SSO client (handles token management) |
| `SSO_INSPECTION_GUIDE.md` | How to find SSO endpoints in DevTools |
| `main.py` | `/diagnostics/scheduler-sso` endpoint + admin integration |
| `.env` | Your SSO configuration |

---

## Typical Error Messages & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "SSO Not Yet Configured" | Missing .env variables | Add all 5 required vars |
| "client_id not found" | Wrong CLIENT_ID value | Re-check in DevTools |
| "HTTP 401 Unauthorized" | Wrong CLIENT_SECRET | Verify secret value |
| "Redirect URI mismatch" | REDIRECT_URI doesn't match | Check exact value in auth request |
| "Invalid auth code" | Code expired | Codes only valid for seconds |

---

## Next Steps

1. **Read SSO_INSPECTION_GUIDE.md** (10 min)
2. **Follow the inspection process** (capture endpoints)
3. **Fill in .env** with the 5 required values
4. **Restart server**
5. **Visit /admin** and click "Test SSO Configuration"
6. **Green = Done!** You're ready to use SSO

---

## Quick Reference

### Typical Walmart SSO Flow
```
Endpoint: https://login.walmart.com/authorize
  ↓
User logs in
  ↓
Redirect: https://scheduler.walmart.com/callback?code=ABC123
  ↓
Exchange: POST https://login.walmart.com/token
  ├─ grant_type: authorization_code
  ├─ code: ABC123
  ├─ client_id: scheduler_app_123
  ├─ client_secret: secret_xyz
  └─ redirect_uri: https://scheduler.walmart.com/callback
  ↓
Response:
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "Bearer",
    "expires_in": 3600
  }
  ↓
Use token: Authorization: Bearer {access_token}
```

---

## Help, It Still Doesn't Work!

If you're stuck:

1. **Double-check all 5 variables** in .env
2. **Restart server** (sometimes changes don't take effect)
3. **Check browser console** for JavaScript errors
4. **Use SSO_INSPECTION_GUIDE.md** to re-verify endpoint URLs
5. **Post your findings** (sanitized) and I can help debug

The most common issue is a typo in one of the 5 values. Verify each one character-by-character!

