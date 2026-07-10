# Scheduler.walmart.com - ACTUAL AUTH FLOW CAPTURED

## Key Finding: SAML20 + JWT Token

Based on the HAR file analysis, here's the exact flow:

---

## Auth Flow Steps

### Step 1: Initial Request
```
GET https://scheduler.walmart.com/
```
Redirects to PingFederate SAML SSO:
```
https://pfedprod.wal-mart.com/idp/K60tJv2J9E/resumeSAML20/idp/startSSO.ping
```

### Step 2: User Logs In (Manual)
- Browser shows login form at pfedprod.wal-mart.com
- User enters credentials
- PingFederate authenticates

### Step 3: Redirect Back with JWT Token
After successful authentication, user is redirected to:
```
https://scheduler.walmart.com/ILP2/scheduler-core-ui/?uat=...&securityID=...&userId=...
```

**Key Parameters:**
```
uat: eyJhbGciOiJIUzI1NiJ9.eyJ3bXRfc2NoX2NvdW50cnkiOiJVUyIsIm9yZ05hbWUiOiJXYWxtYXJ0IFN0b3JlcyBJbmMuIiwiY2FwYWJpbGl0aWVzIjoiNiwxOSwyOSwzMCwzNSwzNiw1NSw1OCw1OSw2MCw2MSw2Miw2Myw2NCw2NSw5NywxMzIsMTQwLDE0NSwiLCJ1c2VyVHlwZSI6IkNvbXBhbnkiLCJleXAiOjE3ODM4MDIyODIsInNlY3VyaXR5X2lkIjoiZDBoMHBmN0BBRExvY2FsIn0.72aCHxnXeMOZ5hgS2GeDKMGWWySdURxcFFhSbwXexmU

securityID: d0h0pf7@ADLocal
userId: d0h0pf7@ADLocal
userFirstName: Dylan
userLastName: Hoang
userType: Company
loginId: d0h0pf7@ADLocal
langCode: 101
countryCode: US
```

---

## JWT Token Details

The `uat` parameter is a JWT token:

**Header:**
```json
{
  "alg": "HS256"
}
```

**Payload (decoded):**
```json
{
  "wmt_sch_country": "US",
  "orgName": "Walmart Stores Inc.",
  "capabilities": "6,19,29,30,35,36,55,58,59,60,61,62,63,64,65,97,132,140,145,",
  "userType": "Company",
  "exp": 1783802282,
  "security_id": "d0h0pf7@ADLocal"
}
```

**Key Points:**
- Expires: 1783802282 (UNIX timestamp)
- Algorithm: HS256 (HMAC SHA256)
- Type: Session token (not OAuth, not SAML - simple JWT)

---

## How to Automate This

### Challenge
PingFederate login requires HUMAN interaction (form + credentials). Can't fully automate without credentials.

### Solution: Use the JWT Token from .env

Instead of automating the SSO login (which requires browser):

1. **Manual Step (One-time):** Log in to scheduler.walmart.com normally
2. **Extract the JWT token** from the `uat` URL parameter
3. **Store in .env as:** `SCHEDULER_JWT_TOKEN=eyJhbGciOi...`
4. **Server uses this token** for all API calls

---

## Setup Instructions

### Step 1: Get the JWT Token (One-time)

1. Go to scheduler.walmart.com in browser
2. Log in normally (PingFederate will handle it)
3. After login, look at the URL
4. Find the `uat=` parameter
5. Copy everything from `uat=` to the next `&` (or end of URL)
6. Extract just the token value (after `uat=`)

**Example:**
```
URL: https://scheduler.walmart.com/ILP2/scheduler-core-ui/?uat=eyJhbGciOiJIUzI1NiJ9.eyJ3bXRfc2NoX2NvdW50cnkiOiJVUyIsIm9yZ05hbWUiOiJXYWxtYXJ0IFN0b3JlcyBJbmMuIiwiY2FwYWJpbGl0aWVzIjoiNiwxOSwyOSwzMCwzNSwzNiw1NSw1OCw1OSw2MCw2MSw2Miw2Myw2NCw2NSw5NywxMzIsMTQwLDE0NSwiLCJ1c2VyVHlwZSI6IkNvbXBhbnkiLCJleHAiOjE3ODM4MDIyODIsInNlY3VyaXR5X2lkIjoiZDBoMHBmN0BBRExvY2FsIn0.72aCHxnXeMOZ5hgS2GeDKMGWWySdURxcFFhSbwXexmU&securityID=...

Token to extract:
eyJhbGciOiJIUzI1NiJ9.eyJ3bXRfc2NoX2NvdW50cnkiOiJVUyIsIm9yZ05hbWUiOiJXYWxtYXJ0IFN0b3JlcyBJbmMuIiwiY2FwYWJpbGl0aWVzIjoiNiwxOSwyOSwzMCwzNSwzNiw1NSw1OCw1OSw2MCw2MSw2Miw2Myw2NCw2NSw5NywxMzIsMTQwLDE0NSwiLCJ1c2VyVHlwZSI6IkNvbXBhbnkiLCJleHAiOjE3ODM4MDIyODIsInNlY3VyaXR5X2lkIjoiZDBoMHBmN0BBRExvY2FsIn0.72aCHxnXeMOZ5hgS2GeDKMGWWySdURxcFFhSbwXexmU
```

### Step 2: Add to .env

```env
# Scheduler JWT Token (from URL parameter after login)
SCHEDULER_JWT_TOKEN=eyJhbGciOiJIUzI1NiJ9.eyJ3bXRfc2NoX2NvdW50cnkiOiJVUyIsIm9yZ05hbWUiOiJXYWxtYXJ0IFN0b3JlcyBJbmMuIiwiY2FwYWJpbGl0aWVzIjoiNiwxOSwyOSwzMCwzNSwzNiw1NSw1OCw1OSw2MCw2MSw2Miw2Myw2NCw2NSw5NywxMzIsMTQwLDE0NSwiLCJ1c2VyVHlwZSI6IkNvbXBhbnkiLCJleXAiOjE3ODM4MDIyODIsInNlY3VyaXR5X2lkIjoiZDBoMHBmN0BBRExvY2FsIn0.72aCHxnXeMOZ5hgS2GeDKMGWWySdURxcFFhSbwXexmU
```

### Step 3: Update Code

Use a simple JWT token client:

```python
import os
import httpx
from datetime import datetime

class SchedulerJWTClient:
    def __init__(self):
        self.token = os.getenv("SCHEDULER_JWT_TOKEN", "").strip()
        self.base_url = "https://scheduler.walmart.com"
    
    async def api_call(self, endpoint: str, method: str = "GET", **kwargs):
        """Make API call with JWT token."""
        if not self.token:
            raise Exception("SCHEDULER_JWT_TOKEN not configured")
        
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient(verify=False) as client:
            return await client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )
```

### Step 4: Use in Your Code

```python
from scheduler_jwt_client import SchedulerJWTClient

async def get_schedules():
    client = SchedulerJWTClient()
    response = await client.api_call("/api/schedules", method="GET")
    return response.json()
```

---

## Token Expiration

The token has an `exp` claim (expiration):
```
"exp": 1783802282  # UNIX timestamp
```

This is a one-time token that expires. When it expires:

**Option A: Re-login manually**
1. Go to scheduler.walmart.com
2. Log in again (automatic, might not need to re-enter password if session valid)
3. Extract new token
4. Update .env

**Option B: Refresh mechanism (if available)**
Check if PingFederate or scheduler have a refresh endpoint.

---

## Important Details

### Authentication Method
- **Type**: SAML20 + JWT Token
- **Provider**: PingFederate (pfedprod.wal-mart.com)
- **Flow**: User logs in → PingFederate → Redirect with JWT + user info
- **Token Type**: JWT (JSON Web Token)
- **Algorithm**: HS256 (HMAC SHA256)

### API Usage
Once you have the JWT token, use it in requests:
```
Authorization: Bearer {uat_token_value}
```

Or potentially:
```
X-Auth-Token: {uat_token_value}
```

### No Client Secret Needed
Unlike OAuth2, this flow doesn't use:
- Client ID
- Client Secret  
- Authorization Code exchange
- Token Endpoint

It's simpler: User logs in → Gets JWT → Uses JWT for API calls.

---

## Temporary Workaround

Until you automate the PingFederate login (which requires username/password form automation), you can:

1. **Manual login:** Use browser to log in normally
2. **Extract token:** Copy JWT from URL
3. **Store token:** Add to .env
4. **Use token:** Server uses it automatically

---

## Next Steps for Dylan

1. **Log in to scheduler.walmart.com** in your browser
2. **Look at the URL** - find the `uat=...` parameter
3. **Copy the JWT token value** (the long string starting with `eyJ`)
4. **Add to .env:**
   ```env
   SCHEDULER_JWT_TOKEN=<paste-token-here>
   ```
5. **I'll update the code** to use this token automatically

---

## Decoded Token Example

```json
{
  "alg": "HS256"
}.
{
  "wmt_sch_country": "US",
  "orgName": "Walmart Stores Inc.",
  "capabilities": "6,19,29,30,35,36,55,58,59,60,61,62,63,64,65,97,132,140,145,",
  "userType": "Company",
  "exp": 1783802282,
  "security_id": "d0h0pf7@ADLocal"
}.
{signature}
```

---

## Files to Create/Update

I need to update:
1. Remove old SSO client code
2. Add simple JWT client
3. Update admin page
4. Update .env template

Ready when you extract your JWT token!

