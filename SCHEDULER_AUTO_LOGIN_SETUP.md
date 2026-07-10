# Scheduler.walmart.com - Automatic Auth Setup

## Goal
Get the server to **automatically login** to scheduler.walmart.com and manage the session token without you manually extracting it from the browser each time.

---

## Step 1: Capture the Actual Auth Request (5 min)

We need to see exactly what scheduler.walmart.com does when you login. This requires inspecting ONE successful login request.

### 1.1 Open Browser DevTools Network Inspector

1. Open scheduler.walmart.com in your browser
2. Press **F12** (DevTools)
3. Click **Network** tab
4. **Clear all requests** (click the trash icon)
5. **Make sure "Preserve log" is UNCHECKED** so we only see new requests

### 1.2 Perform a Fresh Login

1. If you're already logged in: **Logout first** (look for logout button)
2. Now **reload the page** (F5)
3. You should see a login form appear
4. **Type your credentials** (if you don't have them, you'll need to get them from Walmart IT)
5. **Click Login button**

### 1.3 Find the Auth Request

After clicking login, the Network tab will fill with requests. Look for one of these patterns:

- **POST to `/auth`, `/login`, `/session`, `/token`** ← Most likely
- **Largest POST request** ← Could be it
- **First POST request after form submission** ← Probably it

**Tips to identify the right request:**
- It should happen **immediately after** you click login
- It should have a **POST** method
- Status should be **200** (success) or **302** (redirect)
- Response should contain a **token**, **session_id**, or **cookie**

### 1.4 Copy the Full Request Details

Right-click the request → **Copy as cURL**

Paste it in a text file. It will look like:

```bash
curl 'https://scheduler.walmart.com/api/v1/auth/login' \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: Mozilla/5.0...' \
  --data-raw '{"username":"your.name@walmart.com","password":"your_password"}' \
  --compressed
```

This shows us:
- **URL**: The endpoint we need to hit
- **Method**: GET/POST/PUT/DELETE
- **Headers**: What to include
- **Body**: What data to send

---

## Step 2: Document the Auth Flow

Fill this out based on what you found:

```
LOGIN ENDPOINT
URL: https://scheduler.walmart.com/____________
Method: POST / GET / PUT
Content-Type: application/json / application/x-www-form-urlencoded / form-data

REQUEST BODY (what we send):
{
  ___________: ___________,
  ___________: ___________
}

RESPONSE (what we get back):
HTTP Status: _____ (200? 302?)
Response contains:
  - token? (key name: _______)
  - session_id? (key name: _______)
  - cookie? (cookie name: _______)
  - auth header? (header name: _______)

RESPONSE BODY (first 500 chars):
{
_________________________________
}

TOKEN/SESSION STORAGE
After login, where does the token go?
  - Session Storage key: _______
  - Local Storage key: _______
  - Cookie name: _______
  - Response header: _______
```

---

## Step 3: Tell Me What You Found

Once you have the curl command, post:
1. The **curl command** (sanitized of passwords if sharing)
2. The **response body** (first 500 characters)
3. The **token location** (session storage key? cookie? etc.)

### Example of What I'm Looking For:

```bash
curl 'https://scheduler.walmart.com/api/auth/login' \
  -H 'Content-Type: application/json' \
  --data-raw '{"username":"user@walmart.com","password":"PASSWORD_HIDDEN"}' \
  -v  # verbose shows headers too
```

Response:
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {"name": "John Doe", "email": "john@walmart.com"},
  "expires_in": 3600
}
```

Headers response should include:
```
Set-Cookie: session_id=abc123; Path=/; HttpOnly
Authorization: Bearer eyJhbGciOi...
```

---

## Step 4: I'll Build the Server-Side Login

Once I see the request, I'll build:

1. **Auto-login endpoint** (`/api/scheduler/login`)
   - Hits the auth endpoint you found
   - Gets the token automatically
   - Stores it securely

2. **Token refresh logic**
   - Checks if token is expired
   - Auto-refreshes when needed
   - No manual intervention required

3. **Scheduler API wrapper** 
   - Every scheduler.walmart.com request automatically includes the token
   - Handles 401 (expired token) by re-authenticating

---

## Example of Final Result

Once set up, you'd just do:

```python
# In your code:
from scheduler_client import SchedulerClient

scheduler = SchedulerClient()
token = await scheduler.get_token()  # Automatically logins if needed
response = await scheduler.api_call("/some/endpoint")  # Token attached automatically
```

Or from the admin page:
```
Click: "Get Scheduler Token" → Auto-login → Token obtained → Ready to use
```

---

## Security Notes

- We'll store credentials (**encrypted**) in .env:
  ```env
  SCHEDULER_USERNAME=your.name@walmart.com
  SCHEDULER_PASSWORD=your_password_here
  ```

- Token is stored in **memory** (not in .env)
- Token is **automatically refreshed** before expiration
- **No manual token extraction** needed

---

## Next Action

1. **Open scheduler.walmart.com** in your browser
2. **Logout** if you're already logged in
3. **Open DevTools** (F12) → Network tab
4. **Login again** and capture the auth request
5. **Copy the cURL command** (Right-click request → Copy as cURL)
6. **Paste it** back here or in a file

That's all I need to build the auto-login system!

---

## If You Get Stuck on Inspection

Alternative: Just tell me:
1. What's the login URL? (where do you type username/password?)
2. Is there a "Forgot Password" flow? (shows what system it uses)
3. Does it redirect to another domain? (sso.walmart.com? login.walmart.com?)
4. Any hints in page source? (View → View Page Source, search for "api" or "auth")

