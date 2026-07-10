# Scheduler.walmart.com - SSO (Single Sign-On) Automation

## Understanding SSO Flow

Walmart SSO is a redirect-based authentication. Here's the typical flow:

```
1. User visits: https://scheduler.walmart.com
2. Redirects to: https://login.walmart.com/login
3. User enters credentials
4. Redirects back to: https://scheduler.walmart.com/callback?code=ABC123
5. Client exchanges code for token
6. Token stored and used for API calls
```

For **server-side automation**, we need to:
1. Capture the redirect endpoints
2. Extract the auth code
3. Exchange code for token
4. Store and refresh token

---

## Phase 1: Inspect the SSO Flow (10 minutes)

### Step 1.1: Open DevTools Network Inspector

1. Open **scheduler.walmart.com** in a fresh browser tab
2. **If already logged in: LOGOUT first**
3. Press **F12** (DevTools)
4. Click **Network** tab
5. **Clear all requests** (trash icon)
6. **Make sure "Preserve log" is UNCHECKED**

### Step 1.2: Trigger Login

1. **Reload the page** (F5)
2. You should see a login form appear OR redirect to login.walmart.com
3. Watch the Network tab - requests will start appearing

### Step 1.3: Follow the Redirects

Look for these request patterns:

**Request 1: Initial redirect**
- URL will change to something like: `https://login.walmart.com/login`
- Status: 302 (redirect)
- **Copy this URL**

**Request 2: Login form submission**
- Look for a POST request after you enter credentials
- Should be to login.walmart.com domain
- **Copy the request details**

**Request 3: Redirect back with code**
- After login, you'll see a redirect back to scheduler.walmart.com
- URL will look like: `https://scheduler.walmart.com/callback?code=eyJhbGciOi...`
- OR: `https://scheduler.walmart.com?code=ABC123&state=XYZ`
- **Copy this entire URL**

### Step 1.4: Find the Token Exchange

After the redirect, look for:
- A POST request to `/token` or `/auth/token`
- May go to: login.walmart.com, scheduler.walmart.com, or auth.walmart.com
- Request body should contain:
  ```json
  {
    "code": "ABC123...",
    "client_id": "some_id",
    "client_secret": "some_secret",
    "redirect_uri": "https://scheduler.walmart.com/callback"
  }
  ```

**Response should contain:**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "..."
}
```

---

## Phase 2: Document the SSO Configuration

Fill this out based on what you found:

```
=== WALMART SSO CONFIGURATION ===

1. LOGIN REDIRECT
   From URL: https://scheduler.walmart.com
   Redirect to: https://________________________________
   Status Code: _____

2. LOGIN SUBMISSION
   Method: POST / GET
   URL: _________________________________
   Headers needed: 
     - ___________: ___________
     - ___________: ___________
   Body (if POST):
     {
       "username": "_________",
       "password": "_________",
       other fields: ___________
     }

3. CALLBACK URL (redirect back)
   URL pattern: https://scheduler.walmart.com/________________________
   Query params:
     - code: __________ (looks like JWT? UUID?)
     - state: __________ (random string?)
     - other: __________

4. TOKEN EXCHANGE
   Endpoint: https://________________________________
   Method: POST
   Headers:
     - Authorization: __________ (if needed)
     - Content-Type: __________ 
   Body:
     {
       "grant_type": "authorization_code",
       "code": "_________",
       "client_id": "_________",
       "client_secret": "_________",
       "redirect_uri": "_________"
     }

5. TOKEN RESPONSE
   Field name: __________ (access_token? token?)
   Format: __________ (JWT? Bearer? etc)
   Expires in: __________ (seconds? hours?)

6. USAGE
   All API requests include:
     Authorization: Bearer {token}
     OR
     X-Auth-Token: {token}
     OR
     other: __________
```

---

## Phase 3: Capture Actual Requests

### Method A: Copy as cURL (Easiest)

For each important request:
1. Right-click request in Network tab
2. Select **"Copy as cURL"**
3. Paste into a text file

**Important requests to capture:**
- Login form submission
- Token exchange request
- Any other POST requests

### Method B: View Request Headers

For each request:
1. Click on it in Network tab
2. Go to **"Headers"** tab
3. Note the:
   - Request URL
   - Request Method
   - All headers (especially Authorization, Content-Type)
   - Request body

### Method C: View Response

1. Click on request
2. Go to **"Response"** tab
3. Copy the full JSON response

---

## Phase 4: Find Client ID & Secret

Walmart SSO needs a `client_id` and `client_secret`. These are somewhere:

### Check 1: In the request body
When you POST to the token endpoint, these might be included in:
```
POST /token
{
  "client_id": "scheduler_app_123",
  "client_secret": "secret_xyz_abc"
}
```

### Check 2: In response headers
```
Set-Cookie: client_id=...; Path=/
X-Client-ID: scheduler_app_123
```

### Check 3: In page source
1. Go to scheduler.walmart.com
2. Right-click → View Page Source
3. Search for: `client_id`, `clientId`, `CLIENT_ID`

### Check 4: In browser storage
1. DevTools → Application tab
2. Session Storage → Look for `client_id`, `clientSecret`
3. Local Storage → Same

### Check 5: Contact Walmart IT
If you can't find it, ask:
- What's the client ID for scheduler.walmart.com?
- What's the client secret?
- What's the token endpoint?

---

## Phase 5: Document the Flow

Here's what a typical Walmart SSO flow looks like:

```
[1] User clicks login on scheduler.walmart.com
    ↓
[2] GET https://login.walmart.com/authorize
    ?client_id=scheduler_app_123
    &redirect_uri=https://scheduler.walmart.com/callback
    &response_type=code
    &state=random_state_123
    ↓
[3] User enters credentials on login.walmart.com
    ↓
[4] POST https://login.walmart.com/login
    username=...&password=...
    ↓
[5] Redirect to callback URL with auth code:
    https://scheduler.walmart.com/callback?code=AUTH_CODE_123&state=random_state_123
    ↓
[6] POST https://login.walmart.com/token
    {
      "grant_type": "authorization_code",
      "code": "AUTH_CODE_123",
      "client_id": "scheduler_app_123",
      "client_secret": "secret_xyz",
      "redirect_uri": "https://scheduler.walmart.com/callback"
    }
    ↓
[7] Response with token:
    {
      "access_token": "eyJhbGciOi...",
      "token_type": "Bearer",
      "expires_in": 3600
    }
    ↓
[8] Store token in sessionStorage
[9] All future API calls include: Authorization: Bearer {token}
```

---

## Automated Implementation (What I'll Build)

Once you give me the details above, I'll create:

### 1. SSO Client (`sso_client.py`)
```python
from sso_client import SSOClient

client = SSOClient()
token = await client.get_token()  # Auto-login + exchange
response = await client.api_call("/api/endpoint")  # Token attached
```

### 2. How It Works
```
[Server] Stores client_id + client_secret in .env
   ↓
[Server] On first request, gets auth code
   ↓
[Server] Exchanges code for token
   ↓
[Server] Stores token in memory
   ↓
[Server] Auto-refreshes token before expiration
   ↓
[All API calls] Token automatically attached
```

### 3. Configuration
```env
# Walmart SSO
SCHEDULER_CLIENT_ID=scheduler_app_123
SCHEDULER_CLIENT_SECRET=secret_xyz_abc
SCHEDULER_REDIRECT_URI=https://scheduler.walmart.com/callback
SCHEDULER_AUTH_ENDPOINT=https://login.walmart.com/authorize
SCHEDULER_TOKEN_ENDPOINT=https://login.walmart.com/token

# Optional
SCHEDULER_USERNAME=your.name@walmart.com
SCHEDULER_PASSWORD=your_password
```

---

## Next Steps

1. **Follow Phase 1-2 above** (inspect the SSO flow in DevTools)
2. **Fill out the configuration template** (Phase 2)
3. **Tell me:**
   - Login redirect URL
   - Token endpoint URL
   - Client ID + Secret (if you can find them)
   - Auth code format (JWT? UUID?)
4. **I'll build the SSO client** that automates all of it

---

## Quick Checklist

- [ ] Opened scheduler.walmart.com + logged out
- [ ] Opened DevTools Network tab
- [ ] Captured redirect to login.walmart.com
- [ ] Captured token exchange request
- [ ] Found client_id and client_secret
- [ ] Documented token response format
- [ ] Filled out the configuration template above

---

## If You Get Stuck

**Most common issues:**

1. **Can't find token exchange request**
   - Look for POST requests to any domain
   - Filter by "XHR" (XMLHttpRequest) in Network tab
   - Search for "token" in request names

2. **Can't find client_id/secret**
   - Check page source (Ctrl+U)
   - Search for "client" in DevTools Console
   - Ask Walmart IT

3. **Redirect chain is complex**
   - Take screenshots of each redirect
   - Note the exact URLs
   - I can help untangle it

4. **Not sure which request is the token exchange**
   - Look for the one with "token" in the response
   - Should return `access_token` or `token` field
   - Status should be 200 (success)

---

## Example Capture (Real Flow)

Here's what a real capture might look like:

```
REQUEST 1 - GET (redirect to SSO)
URL: https://login.walmart.com/authorize?client_id=scheduler_app&redirect_uri=https://scheduler.walmart.com/callback&response_type=code&state=abc123
Status: 302

REQUEST 2 - POST (login submission)
URL: https://login.walmart.com/login
Body: username=john.doe@walmart.com&password=secret123
Status: 302

REQUEST 3 - GET (callback with code)
URL: https://scheduler.walmart.com/callback?code=AUTH_CODE_XYZ&state=abc123
Status: 302

REQUEST 4 - POST (exchange code for token)
URL: https://login.walmart.com/token
Body: {
  "grant_type": "authorization_code",
  "code": "AUTH_CODE_XYZ",
  "client_id": "scheduler_app",
  "client_secret": "secret123",
  "redirect_uri": "https://scheduler.walmart.com/callback"
}
Response: {
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

---

## Post Your Findings Here

Once you capture the flow:
1. Tell me the redirect URL
2. Tell me the token endpoint
3. Tell me how to get client_id/secret
4. Tell me the token response format
5. I'll automate it!

