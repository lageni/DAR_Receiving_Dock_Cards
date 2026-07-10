# Scheduler.walmart.com Integration Guide

## Overview
This guide walks you through integrating scheduler.walmart.com authentication into CodePuppyDAR's admin panel. You'll learn how to:
1. Extract your session token from the browser
2. Configure CodePuppyDAR to use it
3. Test the integration

---

## Step 1: Get Your Scheduler Token from Browser

### Option A: Extract from Session Storage (Easiest)

1. **Login to scheduler.walmart.com** in your browser
2. **Open DevTools** (Press F12)
3. Go to **Application** tab
4. In left sidebar, click **Storage** -> **Session Storage** -> **https://scheduler.walmart.com**
5. Look for the key **"token"** in the table
6. **Copy the full value** (it will look like: `eyJhbGciOi...` or a long UUID)

### Option B: Extract from Console

1. Open scheduler.walmart.com + DevTools (F12)
2. Click **Console** tab
3. Paste this and press Enter:
   ```javascript
   console.log(sessionStorage.getItem('token'))
   ```
4. Copy the output value

### Option C: Decode & Inspect Token

If the token is a JWT (starts with `eyJ`):
1. Go to https://jwt.io
2. Paste your token in the "Encoded" box
3. View the decoded payload to confirm it's valid
4. Check the `exp` field to see expiration time

---

## Step 2: Add Token to .env File

### Method 1: Simple Token (Recommended)
Add this to your `.env` file in the CodePuppyDAR directory:

```env
# Scheduler.walmart.com Authentication
SCHEDULER_TOKEN=<paste-your-token-here>
```

**Example:**
```env
SCHEDULER_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

### Method 2: API Key
If scheduler uses API keys instead:

```env
SCHEDULER_API_KEY=<your-api-key>
```

### Method 3: Credentials
If you need to login with username/password:

```env
SCHEDULER_USERNAME=your_username
SCHEDULER_PASSWORD=your_password
```

### Important: Save and Reload
- **Save the .env file**
- **Restart your FastAPI server** (Ctrl+C, then run `RUN.bat` again)

---

## Step 3: Test the Integration

### Using the Admin Page

1. **Restart the server** and go to `http://localhost:8000/admin`
2. Scroll down to **"Scheduler.walmart.com Session/Token"** section
3. You should see:
   - SCHEDULER_TOKEN: **+Present** (green checkbox)
   - Configuration Status showing your token format (JWT, API Key, etc.)

### Click "Test Scheduler Auth"

1. Click the **"Test Scheduler Auth"** butt. A diagnostics panel will appear showing:
   - Token format (JWT, API Key, etc.)
   - Token preview
   - Links to decode (if JWT)

### Verify in Browser Storage

1. Go to scheduler.walmart.com in a new tab
2. Open DevTools -> Application -> Session Storage
3. Verify the `token` key still exists and hasn't changed
4. If you see it's been updated, copy the new value to .env

---

## Troubleshooting Steps

### Issue: Token Not Found in .env

**Symptoms:**
- Admin page shows "SCHEDULER_TOKEN: MISSING"
- Test button is disabled

**Fix:**
1. Check that `.env` file exists in the CodePuppyDAR directory
2. Verify you saved the file after adding the token
3. Restart the FastAPI server
4. Check for typos: exactly `SCHEDULER_TOKEN=` (no spaces)

### Issue: Token Format Unclear

**Symptoms:**
- Not sure if it's JWT, API key, or something else

**Solution:**
Run this in the browser console (on scheduler.walmart.com):
```javascript
// Check all session storage
console.table(sessionStorage);

// Check local storage
console.table(localStorage);

// Check cookies
document.cookie
```

Then look for keys that look like tokens (not regular values like `countryCode` or `lang_code`).

### Issue: Token Expired

**Symptoms:**
- Token was working, then API calls start failing
- Browser console shows "401 Unauthorized"

**Solution:**
1. Go back to scheduler.walmart.com
2. You may need to re-login
3. Extract the new token (it will be different)
4. Update `.env` with the new token
5. Restart the server

### Issue: Don't Know the Auth Method

**Solution:**
Use the detailed **SCHEDULER_AUTH_TROUBLESHOOTING.md** guide:
1. Open that file in the repo
2. Follow Phase 1-5 to systematically inspect the auth flow
3. Document your findings in a text file
4. Come back here and update .env based on findings

---

## Environment Variables Reference

| Variable | Type | Required | Example |
|----------|------|----------|---------|
| `SCHEDULER_TOKEN` | String | If using token auth | `eyJhbGciOi...` |
| `SCHEDULER_API_KEY` | String | If using API key | `sk_live_abcd1234...` |
| `SCHEDULER_USERNAME` | String | If using login | `john.doe@walmart.com` |
| `SCHEDULER_PASSWORD` | String | If using login | `MySecurePass123` |

Note: You only need **ONE** of these, depending on the auth method.

---

## Admin Page Features

### Scheduler Diagnostics Section

The admin page (`/admin`) now includes a "Scheduler.walmart.com Session/Token" section with:

1. **Configuration Status Table**
   - Shows which auth variables are set
   - Green checkmarks for configured items
   - Orange warnings for missing items

2. **Browser Inspection Guide**
   - Step-by-step instructions to extract token from browser
   - Links to DevTools documentation

3. **Token Info Display**
   - Shows token format (JWT vs API Key)
   - Token preview (first 50 characters)
   - Link to jwt.io for JWT decoding

4. **Test API Button**
   - Click to verify token is valid
   - Tests against scheduler.walmart.com API
   - Shows success/failure with HTTP status

---

## Common Auth Methods

### JWT Token (Most Common)
```env
SCHEDULER_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```
- Looks like: `eyJ...` followed by 2 more dots
- Use with header: `Authorization: Bearer {token}`
- Usually expires in hours/days

### API Key
```env
SCHEDULER_API_KEY=sk_live_abcdef123456
```
- Looks like: Simple alphanumeric or `sk_live_` prefix
- Use with header: `X-API-Key: {key}`
- Usually doesn't expire

### Basic Auth (Username/Password)
```env
SCHEDULER_USERNAME=user@walmart.com
SCHEDULER_PASSWORD=password123
```
- Encode as Base64: `base64(username:password)`
- Use with header: `Authorization: Basic {base64}`
- App will generate token on startup

---

## Next Steps

1. **Extract your token** using Step 1
2. **Add to .env** using Step 2
3. **Test with admin page** using Step 3
4. **If issues arise**, use SCHEDULER_AUTH_TROUBLESHOOTING.md for deep inspection

---

## Files in This Integration

- **SCHEDULER_AUTH_TROUBLESHOOTING.md** - Detailed browser inspection guide
- **SCHEDULER_INTEGRATION_GUIDE.md** - This file (quick start)
- **main.py** - `@app.get("/diagnostics/scheduler")` + `/api/scheduler/test` endpoints
- **.env** - Your configuration (token, API key, or credentials)

---

## Security Notes

- **Never commit .env to Git** (it's already in .gitignore)
- **Don't share tokens in chat or email**
- **Rotate tokens regularly** if they're exposed
- **Use environment variables** for all secrets, never hardcode
- **Set tokens as "secret"** in your IDE if possible

---

## Questions or Issues?

1. Check **SCHEDULER_AUTH_TROUBLESHOOTING.md** for browser inspection steps
2. Review the **Troubleshooting** section above
3. Verify **.env file** is saved and server is restarted
4. Check **DevTools Console** for JavaScript errors
5. Look at **Network tab** to see actual API requests/responses

