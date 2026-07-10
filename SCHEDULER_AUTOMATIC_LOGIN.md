# Scheduler.walmart.com Automatic Login - Setup Complete

## What I Built For You

### 1. Automatic Server-Side Login
- Server automatically logs into scheduler.walmart.com using credentials from .env
- No manual token extraction from browser needed
- Token stored in memory and automatically refreshed before expiration

### 2. SchedulerClient Module (`scheduler_client.py`)
A Python client that handles:
- Auto-login on startup or when token expires
- Token refresh (checks expiration before each request)
- Automatic token injection on all API calls
- Graceful error handling and retry logic

### 3. Admin Page Integration
- New section: "Scheduler.walmart.com - Automatic Login"
- Shows configuration status (username/password set?)
- "Test Auto-Login" button to verify credentials work
- Displays token info after successful login

### 4. Two New Endpoints
```
GET  /diagnostics/scheduler         → Shows config status & login form
POST /api/scheduler/auto-login      → Performs automatic login
```

---

## How To Use (3 Steps)

### Step 1: Get Your Credentials
You need to know:
- Your Walmart username (usually email: name@walmart.com)
- Your Walmart password

If you don't have these, contact Walmart IT.

### Step 2: Add to .env
Edit `CodePuppyDAR/.env` and add:

```env
SCHEDULER_USERNAME=your.name@walmart.com
SCHEDULER_PASSWORD=your_password_here
```

Save the file.

### Step 3: Test It
1. **Restart the server** (Ctrl+C in terminal, run `RUN.bat`)
2. Go to **http://localhost:8000/admin**
3. Scroll to **"Scheduler.walmart.com - Automatic Login"** section
4. Click **"Test Auto-Login"** button
5. If successful: Green message + token displayed
6. If failed: See troubleshooting below

---

## What Happens When You Click "Test Auto-Login"

```
1. Server sends POST request to scheduler.walmart.com/api/auth/login
   ↓
2. Server sends username + password in request
   ↓
3. Scheduler returns token (JWT or API key)
   ↓
4. Server stores token in memory
   ↓
5. Token is automatically refreshed before expiration
   ↓
6. All API calls to scheduler automatically include the token
```

---

## Architecture Overview

### scheduler_client.py
```python
from scheduler_client import SchedulerClient

client = SchedulerClient()

# Auto-login (happens automatically)
token = await client.get_token()

# Make API calls (token attached automatically)
response = await client.api_call("/api/endpoint", method="GET")

# Token refresh (automatic on 401 or expiration)
# No manual handling needed!
```

### Usage in main.py
```python
from scheduler_client import SchedulerClient

# In an endpoint:
client = SchedulerClient()
success = await client.login()
if success:
    # You have a valid token in client.token
    pass
```

---

## Troubleshooting

### Issue: "Test Auto-Login" shows error
**Probable cause:** Auth endpoint is different than expected

**Solution:**
1. Read `SCHEDULER_AUTO_LOGIN_SETUP.md` (detailed inspection guide)
2. Capture the actual auth request from your browser
3. Tell me the endpoint URL and request format
4. I'll update `scheduler_client.py` with the correct endpoint

### Issue: "Credentials Not Configured"
**Probable cause:** .env doesn't have username/password

**Solution:**
1. Open `CodePuppyDAR/.env`
2. Add these lines:
   ```env
   SCHEDULER_USERNAME=your.name@walmart.com
   SCHEDULER_PASSWORD=your_password_here
   ```
3. Save file
4. Restart server
5. Try again

### Issue: Login fails with HTTP error
**Probable cause:** Credentials wrong OR auth endpoint is different

**Solution:**
1. Double-check username/password (no typos)
2. Verify you can login to scheduler.walmart.com manually with these same credentials
3. If credentials are correct but login still fails, the auth endpoint is likely different
4. Use `SCHEDULER_AUTO_LOGIN_SETUP.md` to inspect the actual auth flow

### Issue: Don't know if it worked
**Solution:**
1. Check browser console: F12 → Console tab
2. Look for `[SCHEDULER] Login successful!` or `[SCHEDULER] Login failed`
3. Check the admin page for green/red status message

---

## Environment Variables

| Variable | Type | Required | Example |
|----------|------|----------|---------|
| `SCHEDULER_USERNAME` | String | Yes (if using login) | `john.doe@walmart.com` |
| `SCHEDULER_PASSWORD` | String | Yes (if using login) | `MySecurePass123` |

Or if using API key instead:
| `SCHEDULER_API_KEY` | String | Yes (if using API key) | `sk_live_abcd1234...` |

---

## Security Notes

- **Credentials stored in .env** (not in code, not in git)
- **.env is in .gitignore** (won't be committed to Git)
- **Token stored in memory only** (not on disk, not in database)
- **Password never logged** (only `[SCHEDULER] Attempting login...` shown)
- **Tokens auto-refresh** (no need to store them long-term)

---

## Files Created/Modified

```
Created:
  - scheduler_client.py               (SchedulerClient class)
  - SCHEDULER_AUTO_LOGIN_SETUP.md     (Detailed inspection guide)

Modified:
  - main.py                           (Added endpoints + admin integration)
  - .env                              (Add SCHEDULER_USERNAME + PASSWORD)
```

---

## Common Auth Methods (For Reference)

### JWT Token Auth (Most Common)
```
Request: POST /api/auth/login
Body: {"username": "...", "password": "..."}
Response: {"token": "eyJhbGci...", "expires_in": 3600}
Header: Authorization: Bearer {token}
```

### API Key Auth
```
Header: X-API-Key: sk_live_abc123
No login needed
```

### Basic Auth
```
Header: Authorization: Basic base64(username:password)
No separate login endpoint
```

---

## Next Steps

1. **Add credentials to .env** (username + password)
2. **Restart server** (Ctrl+C + RUN.bat)
3. **Visit /admin** and click "Test Auto-Login"
4. **If it works:** Done! Server can now access scheduler.walmart.com automatically
5. **If it fails:** Use SCHEDULER_AUTO_LOGIN_SETUP.md to inspect the auth endpoint

---

## Using the Client in Your Code

Once configured, you can use the scheduler client anywhere:

```python
from scheduler_client import SchedulerClient

async def my_endpoint():
    client = SchedulerClient()
    
    # Get a valid token (auto-logins if needed)
    token = await client.get_token()
    
    # Make API calls (token automatically attached)
    response = await client.api_call(
        "/api/schedules",
        method="GET"
    )
    
    return response.json()
```

---

## Key Features

- **Auto-login:** No manual token extraction
- **Auto-refresh:** Token refreshed automatically before expiration
- **Error recovery:** Automatically re-authenticates on 401 (expired token)
- **Flexible auth:** Supports JWT, API key, basic auth, and more
- **Memory storage:** Token in memory only, no disk storage
- **Easy integration:** Just import and use

---

## Questions?

1. **How do I know the login worked?**
   - Check admin page: Green message = success, Red message = failed
   - Check browser console: Look for `[SCHEDULER] Login successful!`

2. **What if the auth endpoint is different?**
   - Use SCHEDULER_AUTO_LOGIN_SETUP.md to inspect the actual request
   - Tell me the endpoint and format, I'll update scheduler_client.py

3. **How often does the token refresh?**
   - Automatically before each request if expiration is coming
   - Also automatically if a request returns 401 (Unauthorized)

4. **Can I use an API key instead?**
   - Yes! Set `SCHEDULER_API_KEY=...` in .env instead
   - No login will happen, key is used directly

---

## Status: Ready to Go

Server-side automatic login is now ready. You just need to:

1. Add credentials to .env
2. Restart server
3. Click "Test Auto-Login" on admin page

No more manual token extraction from the browser!

