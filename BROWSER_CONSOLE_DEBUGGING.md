# Browser Developer Tools Debugging Guide for CodePuppy DAR

## Opening Developer Tools

**Windows/Linux:**
- `F12` (fastest)
- `Ctrl + Shift + I`
- Right-click anywhere → Inspect

**Mac:**
- `Cmd + Option + I`
- Right-click anywhere → Inspect

---

## The Console Tab

Click the **Console** tab to see logs and test JavaScript without touching the server.

### 1. View API Responses in Real-Time

When you search for an item, the MDM API response is logged to console. Look for:

```
[EXTRACT] MDM response keys: [list of keys]
[EXTRACT] dcProperties keys: [list of keys]  
[EXTRACT] supplyItem keys: [list of keys]
```

This tells you what data the server is actually receiving from the MDM API.

**Example:** If you search for item `673605563`, you'll see in console:
```
[EXTRACT] Item 673605563: catalog_gtin='08903062184041'
[EXTRACT] MDM response keys: ['number', 'description', 'dcProperties', ...]
```

---

### 2. Check Network Requests (Network Tab)

Click the **Network** tab BEFORE searching. Then search for an item.

You'll see:
- `/search/{item_id}` - Your search request
- API calls to `uwms-item.prod.us.walmart.net` - The MDM API

**Click each request** to see:
- **Response** tab - The raw JSON from MDM
- **Headers** tab - Auth keys, tokens, facility info

**Pro tip:** If API returns 401 or 403, check the Authorization headers - likely a bad API key.

---

### 3. Test JavaScript in Console

You can execute JavaScript directly in the console without reloading:

```javascript
// Fetch test - verify API connectivity
fetch('/search/659608850')
  .then(r => r.text())
  .then(html => console.log(html.substring(0, 500)))
```

```javascript
// Check if dimensions are being passed
console.log(document.querySelector('[data-vnpk-length]'))
```

---

### 4. Set Breakpoints (Debugger Tab)

Click **Sources** tab, then navigate to find `main.py` (if you're running with JavaScript).

Set breakpoints by clicking line numbers. The page will pause execution, letting you:
- Hover over variables to see their values
- Step through code line-by-line (`F10`)
- View the Call Stack to see function execution order

---

### 5. Monitor Database/File Paths

In the Console, paste this to check the database path your app loaded:

```javascript
// Make a request and check response headers
fetch('/admin')
  .then(r => r.text())
  .then(html => {
    // Extract database path from admin page
    const matches = html.match(/read_rates\.db|DATABASE_PATH/g);
    console.log('Database references:', matches);
  })
```

---

### 6. Common Console Messages You'll See

| Message | Meaning | Fix |
|---------|---------|-----|
| `[EXTRACT] Item 673605563: catalog_gtin='...'` | Catalog GTIN extracted successfully |  Working |
| `[EXTRACT] Item 673605563: catalog_gtin=''` | Catalog GTIN not found in response | Check MDM response structure |
| `[PDF] Item 598256978: catalog_gtin='000500005042299'` | PDF generated with GTIN |  Working |
| `[ERROR] Loading read_rates.db: ...` | Database file not found or corrupt | Check `DATABASE_PATH` in `.env` |

---

### 7. Check Server Logs Without SSH

If you're running locally (not remote), the console shows server output.

Look for:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
[INFO] Loaded 5000 items from read_rates.db
```

---

### 8. Inspect Elements on Page

Right-click any element (card, button, chart) → **Inspect**.

You can:
- See HTML structure
- Check CSS classes applied
- Modify styles live to test changes: double-click properties in the Styles panel

**Example:** Change card width:
```css
max-width: 400px;  /* Change this to test responsive behavior */
```

---

### 9. Storage Tab - Check Cookies, LocalStorage

Click **Application** (or **Storage** on Firefox).

If we add authentication tokens to browser storage, you can inspect them here:
```javascript
localStorage.getItem('mdm_api_key')
```

---

### 10. Performance Tab - Check Load Times

Click **Performance** tab, then click **Record** (red circle).

Click "Search" for an item, then **Stop** recording.

You'll see:
- How long API calls take
- When the page paints (renders)
- Bottlenecks (if any)

---

## Quick Debugging Checklist

When something doesn't work:

1. Open Console (F12)
2. Search for the item
3. **Look for errors** (red text) - these are the real problems
4. **Check the Network tab** - is the API request succeeding?
5. **Check the Response tab** - does MDM return the data you expect?
6. **Look for `[EXTRACT]` logs** - did the server parse it correctly?

---

## Informix Connection Testing

Go to **Admin** → **Informix Connection Test** to see if the database is reachable.

If it shows **Failed**, check:
1. Is `dsinfmx` listed in system `sqlhosts`?
2. Are credentials in `.env` correct?
3. Is the network port `23301` reachable?

The console will show the exact ODBC error.

---

## Tips & Tricks

**Collapse all messages:**
```javascript
console.clear()  // Clear all logs
```

**Filter logs:**
```
Filter box (top-left of console) → type "[EXTRACT]" to see only extraction logs
```

**Copy any logged object:**
```
Right-click object in console → Copy object
```

---

**That's it!** You now have superpowers to debug without touching server logs.
