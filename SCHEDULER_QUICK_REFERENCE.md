# Scheduler.walmart.com Auth - Quick Process Card

## 5-Minute Setup

### Phase 1: Get Token from Browser (2 min)
```
1. Open https://scheduler.walmart.com
2. F12 -> Application -> Session Storage -> https://scheduler.walmart.com
3. Look for "token" key
4. Copy the full value (save to notepad)
```

### Phase 2: Add to .env (1 min)
```
Open: CodePuppyDAR/.env

Add this line:
  SCHEDULER_TOKEN=<paste-your-token-here>

Save file
```

### Phase 3: Restart & Test (2 min)
```
1. Restart FastAPI server (Ctrl+C in terminal, run RUN.bat again)
2. Go to http://localhost:8000/admin
3. Scroll to "Scheduler.walmart.com Session/Token"
4. Click "Test Scheduler Auth"
```

---

## Troubleshooting Decision Tree

```
Is .env file missing SCHEDULER_TOKEN?
├─ YES: Go back to Phase 1, extract token
└─ NO: Continue...

Is token showing as "MISSING" in admin page?
├─ YES: Server not restarted. Restart: Ctrl+C + RUN.bat
└─ NO: Continue...

Does "Test Scheduler Auth" show green success?
├─ YES: Done! Token is working
└─ NO: Token may be expired. Re-extract from browser
```

---

## Key Files

| File | Purpose |
|------|---------|
| SCHEDULER_AUTH_TROUBLESHOOTING.md | Deep dive into browser inspection (when confused) |
| SCHEDULER_INTEGRATION_GUIDE.md | Detailed setup instructions |
| .env | YOUR TOKEN (secret, don't share) |
| main.py | `/diagnostics/scheduler` endpoint (added) |

---

## Common Token Formats

### JWT (Walmart uses this)
- Looks like: `eyJhbGciOi...eyJodHRwOi...`
- 3 parts separated by dots (.)
- Paste at https://jwt.io to decode
- Example: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.TJVA95OrM7E2cBab30RMHrHDcEfxjoYZgeFONFh7HgQ`

### UUID (Sometimes used)
- Looks like: `550e8400-e29b-41d4-a716-446655440000`
- All lowercase with dashes
- Usually 36 characters

### API Key (If using that)
- Looks like: `sk_live_abc123def456` or long alphanumeric
- Set in .env as: `SCHEDULER_API_KEY=your_key_here`

---

## Validation Checklist

- [ ] Token extracted from browser
- [ ] Token added to .env file
- [ ] .env file saved
- [ ] Server restarted (Ctrl+C + RUN.bat)
- [ ] Admin page shows "SCHEDULER_TOKEN: +Present"
- [ ] "Test Scheduler Auth" button shows green success

---

## If Token Expires

Tokens usually expire in 1-24 hours. When it happens:

```
1. Go back to scheduler.walmart.com
2. You may be logged out or need to refresh
3. Open DevTools -> Session Storage again
4. Get the NEW token value
5. Update .env with new token
6. Restart server
7. Test again
```

---

## Admin Page Testing

After restart, visit: `http://localhost:8000/admin`

You'll see two new sections:

### Section 1: Configuration Status
Shows: SCHEDULER_TOKEN, SCHEDULER_API_KEY, SCHEDULER_USERNAME, SCHEDULER_PASSWORD
- Green = Configured
- Orange = Missing

### Section 2: Token Inspector
Shows token format (JWT vs API Key) and preview

### Section 3: Test Button
Click "Try API Request" to verify token works against scheduler.walmart.com

---

## Network Inspection (If Stuck)

If you're not sure what format the token is:

```javascript
// In browser console on scheduler.walmart.com:
console.log(sessionStorage.getItem('token'))
console.log(localStorage.getItem('token'))
console.log(JSON.stringify(sessionStorage))
```

Copy the output and check:
- Starts with `eyJ` = JWT
- Has dashes and numbers = UUID
- Just alphanumeric = API Key

---

## Files Created for This Feature

1. **SCHEDULER_AUTH_TROUBLESHOOTING.md** - Full inspection guide (5-phase process)
2. **SCHEDULER_INTEGRATION_GUIDE.md** - Detailed setup + troubleshooting
3. **SCHEDULER_QUICK_REFERENCE.md** - This file (decision trees + checklists)
4. **main.py updated**
   - New endpoint: `/diagnostics/scheduler` (visible in admin)
   - New endpoint: `/api/scheduler/test` (tests your token)

---

## Still Stuck?

Follow this order:

1. **Read**: SCHEDULER_AUTH_TROUBLESHOOTING.md Phase 1-3 (understand the auth)
2. **Extract**: Follow Phase 1 to get token from browser
3. **Configure**: Add to .env, restart server
4. **Test**: Use admin page diagnostics
5. **Debug**: Check browser console for errors (F12 -> Console)
6. **Network**: Monitor Network tab (F12 -> Network) to see actual API calls

