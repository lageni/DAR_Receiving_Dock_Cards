# Scheduler.walmart.com Session/Token Troubleshooting Guide

## Overview
This guide helps you understand how scheduler.walmart.com authenticates and stores sessions, so we can integrate it into CodePuppyDAR.

---

## Phase 1: Inspect the Browser Auth Flow

### Step 1.1: Open DevTools Network Tab
1. Go to https://scheduler.walmart.com
2. Open **DevTools** (F12)
3. Click **Network** tab
4. **Clear** all requests (Ctrl+Shift+Del on Network tab)
5. **Reload the page** (F5)

### Step 1.2: Identify the Authentication Request
Look for requests to these patterns:
- `**/auth/**` — authentication endpoints
- `**/login**` — login submission
- `**/token**` — token generation
- `**/session/**` — session management
- `**/api/**` — any API calls immediately after load

**For each request, note:**
- **Request Method**: GET, POST, PUT, DELETE?
- **URL/Endpoint**: What's the full path?
- **Headers**: Look for `Authorization`, `X-API-Key`, `Cookie`, or custom headers
- **Request Body** (POST): What data is sent? (username, password, API key, etc.)
- **Response Status**: 200 (success), 401 (unauthorized), 403 (forbidden)?
- **Response Body**: Does it contain a token, session ID, or other auth data?

### Step 1.3: Check Application Storage
In DevTools, click **Application** tab:

#### Session Storage
- Path: `Application` → `Storage` → `Session Storage` → `https://scheduler.walmart.com`
- Look for keys like:
  - `token` ← **THIS IS IMPORTANT**
  - `session_id`
  - `auth_token`
  - `access_token`
  - Any key with `"JWT"`, `"Bearer"`, or looks like base64

#### Local Storage
- Path: `Application` → `Storage` → `Local Storage` → `https://scheduler.walmart.com`
- Same keys to look for

#### Cookies
- Path: `Application` → `Cookies` → `https://scheduler.walmart.com`
- Look for cookies with names like:
  - `session`
  - `auth`
  - `token`
  - Any with `HttpOnly` flag (means backend-only, can't access from JS)

### Step 1.4: Document the Token Structure
When you find the token, check:
1. **Format**: 
   - JWT? (looks like `eyJ...`)
   - Plain text UUID? (looks like `550e8400-e29b-41d4-a716-446655440000`)
   - Long alphanumeric? (looks like `aB3dE9fGhIjKlMnOpQrStUvWxYz...`)

2. **Location**:
   - Session Storage?
   - Local Storage?
   - HTTP-only Cookie?
   - Response header?

3. **Expiration**:
   - Does it expire? Check for `expires_at`, `exp` (in JWT), or `ttl` fields
   - How long is the session valid? (minutes? hours?)

---

## Phase 2: Find the Login/Auth Endpoint

### Step 2.1: Capture the Login Request
1. **Clear** all network requests
2. Click the **login button** or **sign in** on scheduler.walmart.com
3. Look at the very **first POST request** that happens
4. Click on it → **Headers** tab

**Copy these details:**
```
Request URL: [PASTE THE FULL URL]
Request Method: [POST/PUT/GET]
Headers:
  - Authorization: [IF PRESENT]
  - Content-Type: [application/json, application/x-www-form-urlencoded, etc.]
  - [Any other custom headers]

Request Body (Preview tab):
{
  [PASTE THE JSON OR FORM DATA]
}

Response Status: [200, 401, etc.]
Response Body (Preview tab):
{
  [PASTE THE RESPONSE]
}
```

### Step 2.2: Identify Credentials/API Key
Does the request include:
- **Username/Password** in the body?
  - If YES: You'll need to store & use these credentials
  - If NO: Continue to next check
- **API Key** in headers or body?
  - If YES: You'll need to store this key (it can be static)
  - If NO: Continue to next check
- **OAuth flow** (redirect to login page)?
  - If YES: This is more complex, note the OAuth provider
- **Existing Session/Cookie** required?
  - If YES: The auth may be handled by browser cookies automatically

---

## Phase 3: Test Token Retrieval Manually

### Step 3.1: Get Your Current Token
Open **Console** tab in DevTools:
```javascript
// Check Session Storage
console.log(sessionStorage.getItem('token'));
console.log(sessionStorage.getItem('security_id'));

// Check Local Storage
console.log(localStorage.getItem('token'));
console.log(localStorage.getItem('auth_token'));

// Check All Session Storage
console.log(JSON.stringify(sessionStorage));

// Check All Local Storage
console.log(JSON.stringify(localStorage));
```

**Copy whatever you find.** This is the active token!

### Step 3.2: Test the Token Format (if JWT)
Paste the token here (don't use sensitive ones!):
https://jwt.io

Look for:
- **Payload** → `exp` field = expiration timestamp
- **Payload** → any user info (name, email, roles)

### Step 3.3: Try Making an API Call with the Token
In DevTools Console:
```javascript
// If token is in sessionStorage
const token = sessionStorage.getItem('token');

// Try a simple API call
fetch('https://scheduler.walmart.com/api/user', {
  headers: {
    'Authorization': `Bearer ${token}`,
    // OR
    // 'Authorization': `${token}`,
    // OR
    // 'X-Auth-Token': token,
    'Content-Type': 'application/json'
  }
})
.then(r => r.json())
.then(data => console.log('SUCCESS:', data))
.catch(err => console.log('ERROR:', err));
```

If you get a response, note the auth header format (Bearer, Basic, custom, etc.).

---

## Phase 4: Reverse-Engineer the Refresh Flow

### Step 4.1: Check Token Expiration
1. From the token or storage, note the expiration time
2. **Wait** for it to expire (or manually expire in DevTools)
3. Watch the Network tab for what happens next
4. Does the app:
   - **Automatically refresh** the token? (look for a refresh request)
   - **Log you out**?
   - **Show an error**?

### Step 4.2: Find the Refresh Endpoint
If it auto-refreshes, note:
- **Request URL**: What endpoint is hit?
- **Request Body**: What data is sent?
- **Response**: Does it return a new token?

Common refresh patterns:
- `POST /auth/refresh`
- `POST /token/refresh`
- `POST /session/refresh`

---

## Phase 5: Document Your Findings

Fill in the template below with everything you've discovered:

```
## Scheduler.walmart.com Authentication Summary

### Authentication Method
- [ ] Username/Password (stored in .env)
- [ ] Static API Key (stored in .env)
- [ ] OAuth/SSO (requires flow)
- [ ] Cookie-based (automatic)
- [ ] Other: _____________

### Login/Auth Endpoint
- **URL**: 
- **Method**: GET / POST / PUT
- **Required Headers**: 
- **Request Body**: 
- **Response Contains**: token / session_id / cookie
- **Response Format**: JSON / Form / Other

### Token Details
- **Storage Location**: Session Storage / Local Storage / HTTP-only Cookie / Response Header
- **Token Key Name**: 
- **Token Format**: JWT / UUID / Alphanumeric / Other
- **Token Expiration**: [Check JWT.io or look for 'exp' field]
- **Token Prefix**: Bearer / Basic / Custom / None

### Token Usage
- **Header Format**: 
  - `Authorization: Bearer {token}`
  - `Authorization: {token}`
  - `X-Auth-Token: {token}`
  - `X-API-Key: {token}`
  - Other: _____________

### Refresh Token
- **Has Refresh Token?**: Yes / No
- **Refresh Endpoint**: 
- **Refresh Method**: 
- **Auto-Refresh?**: Yes / No (if yes, interval?)

### Credentials Needed
- **Username**: (from .env? or hardcoded?)
- **Password**: (from .env? or hardcoded?)
- **API Key**: (from .env? or hardcoded?)
```

---

## Phase 6: Common Walmart Patterns

If scheduler.walmart.com uses standard Walmart auth, it likely follows one of these:

### Pattern A: Walmart SSO (OAuth)
```
1. Redirect to Walmart login page
2. User logs in with Walmart ID
3. Redirect back with auth code
4. Exchange auth code for token
5. Token stored in session/local storage
```
**What to look for**: Redirects to login.walmart.com or sso.walmart.com

### Pattern B: API Key (Simple)
```
1. API key stored in .env or config
2. Every request includes: Authorization: Bearer {api_key}
3. No login required
```
**What to look for**: Static token that never changes

### Pattern C: Login with Credentials (Forms)
```
1. POST /auth/login with { username, password }
2. Response contains { access_token, refresh_token, expires_in }
3. Token stored in session storage
4. Token refreshed automatically or on-demand
```
**What to look for**: Login form, credentials in request body

### Pattern D: Implicit Session (Cookie-based)
```
1. Browser automatically manages session via cookies
2. App just stores a session ID or nothing
3. All requests include credentials: include in fetch
```
**What to look for**: No explicit "token" - just cookies

---

## Next Steps

Once you've filled in the findings:
1. **Post your findings** to this file
2. **Share the Network requests** (sanitized of passwords) in a separate doc
3. I'll integrate it into the admin page with:
   - Auto-login functionality
   - Token refresh handling
   - Diagnostics & troubleshooting endpoints
   - Secure storage in .env

---

## Quick Reference: DevTools Shortcuts

| Task | Location |
|------|----------|
| View all network requests | F12 → Network tab |
| View session data | F12 → Application → Session Storage |
| View cookies | F12 → Application → Cookies |
| Run JS code | F12 → Console tab |
| Decode JWT token | https://jwt.io |
| Clear all storage | F12 → Application → Clear site data |

---

## Security Notes 

- **Never share** tokens, passwords, or API keys in chat
- **Sanitize** any captured requests before sharing
- Store sensitive data in **.env**, not in code
- Use **HTTP-only cookies** when possible (can't be stolen via JS)
- **Rotate API keys** regularly if using static keys
- **Log out** after testing to invalidate tokens

