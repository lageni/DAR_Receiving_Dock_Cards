# Extract JWT Token from Scheduler.walmart.com (2-Step)

## What You Need to Do

### Step 1: Log In and Copy Token (2 minutes)

1. **Go to scheduler.walmart.com** in your browser
2. **Log in** with your Walmart credentials (PingFederate will handle this)
3. **After login**, you'll be on the home page
4. **Look at the URL** in your browser address bar
5. **Find the `uat=` parameter** in the URL

**URL Example:**
```
https://scheduler.walmart.com/ILP2/scheduler-core-ui/?uat=eyJhbGciOiJIUzI1NiJ9...&securityID=...
```

6. **Copy everything after `uat=`** up to the next `&` symbol
   - This is your JWT token (will be a long string starting with `eyJ`)

**Token Example:**
```
eyJhbGciOiJIUzI1NiJ9.eyJ3bXRfc2NoX2NvdW50cnkiOiJVUyIsIm9yZ05hbWUiOiJXYWxtYXJ0IFN0b3JlcyBJbmMuIiwiY2FwYWJpbGl0aWVzIjoiNiwxOSwyOSwzMCwzNSwzNiw1NSw1OCw1OSw2MCw2MSw2Miw2Myw2NCw2NSw5NywxMzIsMTQwLDE0NSwiLCJ1c2VyVHlwZSI6IkNvbXBhbnkiLCJleHAiOjE3ODM4MDIyODIsInNlY3VyaXR5X2lkIjoiZDBoMHBmN0BBRExvY2FsIn0.72aCHxnXeMOZ5hgS2GeDKMGWWySdURxcFFhSbwXexmU
```

### Step 2: Add to .env (1 minute)

1. **Open `CodePuppyDAR/.env`** in a text editor
2. **Add this line:**
   ```env
   SCHEDULER_JWT_TOKEN=<paste-your-token-here>
   ```

3. **Example:**
   ```env
   SCHEDULER_JWT_TOKEN=eyJhbGciOiJIUzI1NiJ9.eyJ3bXRfc2NoX2NvdW50cnkiOiJVUyIsIm9yZ05hbWUiOiJXYWxtYXJ0IFN0b3JlcyBJbmMuIiwiY2FwYWJpbGl0aWVzIjoiNiwxOSwyOSwzMCwzNSwzNiw1NSw1OCw1OSw2MCw2MSw2Miw2Myw2NCw2NSw5NywxMzIsMTQwLDE0NSwiLCJ1c2VyVHlwZSI6IkNvbXBhbnkiLCJleHAiOjE3ODM4MDIyODIsInNlY3VyaXR5X2lkIjoiZDBoMHBmN0BBRExvY2FsIn0.72aCHxnXeMOZ5hgS2GeDKMGWWySdURxcFFhSbwXexmU
   ```

4. **Save the file**
5. **Restart the server** (Ctrl+C, then `RUN.bat`)
6. **Go to /admin** → "Scheduler.walmart.com - JWT Token" section
7. **See green success message** = Done!

---

## Visual Guide: Finding the Token

### URL in Browser
```
https://scheduler.walmart.com/ILP2/scheduler-core-ui/?uat=COPY_THIS_PART&securityID=...
                                                     ^^^^^^^^^^^^^^^^^^^^
                                                     Your JWT token goes here
```

### Copy Until Next `&`
```
uat=eyJhbGciOiJIUzI1NiJ9.eyJ3bXRfc2NoX2NvdW50cnkiOi...&securityID=...
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    COPY THIS ENTIRE STRING
```

---

## Token Info

- **What it is**: JWT (JSON Web Token)
- **Algorithm**: HS256
- **Expiration**: Usually 24 hours
- **When to replace**: When you get 401 errors (token expired)

---

## Troubleshooting

### "I can't find the token"
- Make sure you're logged in (not on login page)
- Check if the URL has `uat=` parameter
- If not, wait a moment for page to fully load

### "Token won't work"
- Make sure you copied the ENTIRE token (from `eyJ` to before the `&`)
- Check for extra spaces or characters
- Verify you restarted the server after updating .env

### "401 Unauthorized errors"
- Token has expired
- Log in again to scheduler.walmart.com
- Extract a new token
- Update .env with new token

---

## Done!

Once you've added the JWT token to .env and restarted, your server can automatically use scheduler.walmart.com API.

