# CodePuppyDAR - Network Deployment Guide

**Version 1.0** | Last Updated: June 2026

---

## Overview

CodePuppyDAR is a web-based MDM Inventory Search application that runs on a central server and is accessible to all users on your network via a web browser. No installation needed for end users.

---

## Table of Contents

1. [Server Setup](#server-setup)
2. [Client Access](#client-access)
3. [Firewall Configuration](#firewall-configuration)
4. [Troubleshooting](#troubleshooting)
5. [Technical Details](#technical-details)

---

## Server Setup

### Prerequisites

- **Windows Server or Desktop Machine** (Windows 10/11 or Server 2016+)
- **Python 3.10+** installed globally
- **Network connectivity** to Walmart MDM API endpoint
- **Read/Write access** to the `read_rates.csv` file

### Step 1: Prepare the Server Machine

Choose a dedicated machine to run CodePuppyDAR. This machine should:
- Be stable and run 24/7 (or during business hours)
- Have network access to MDM API (`uwms-item.prod.us.walmart.net`)
- Have the `read_rates.csv` file in the application folder
- Have at least 4GB RAM and 100GB disk space (for CSV file)

### Step 2: Install Python

1. Download Python 3.10+ from: https://www.python.org/downloads/
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH"
4. Verify installation:
   ```bash
   python --version
   ```

### Step 3: Copy Application Files

1. Copy the entire `CodePuppyDAR` folder to the server machine
2. Ensure these files are present:
   - `main.py`
   - `.env` (with API credentials)
   - `read_rates.csv` (6.4 MB)
   - `START_SERVER.bat`
   - `README.md`

### Step 4: Configure .env File

Edit `.env` with your Walmart MDM credentials:

```env
# MDM Item API Credentials
MDM_API_KEY=<your-api-key-here>
MDM_FACILITY_NUM=6068
MDM_FACILITY_COUNTRY_CODE=US
MDM_WMT_USERID=mdm-ui

# Informix Database (optional, for future use)
INFORMIX_HOST=dsinfmxro.s06068.us
INFORMIX_SERVER=dsinfmx
INFORMIX_PORT=23301
INFORMIX_USER=star
INFORMIX_PASSWORD=<your-password>
INFORMIX_DATABASE=dc_sys_common
```

**SECURITY NOTE**: The `.env` file contains sensitive credentials. Keep it secure and never share it.

### Step 5: Start the Server

**Option A: Double-click batch file (Easiest)**
1. On the server machine, navigate to the `CodePuppyDAR` folder
2. Double-click **`START_SERVER.bat`**
3. A command window will open showing the server status
4. You should see:
   ```
   Local Access:        http://localhost:8000
   Network Access:      http://SERVERNAME:8000
   Server IP:           http://192.168.x.x:8000
   ```

**Option B: Command line (Manual)**
```bash
cd C:\path\to\CodePuppyDAR
python main.py
```

The server will display:
```
Uvicorn running on http://0.0.0.0:8000
```

---

## Client Access

### For End Users

Once the server is running, any user on your network can access CodePuppyDAR:

1. **Open a web browser** (Chrome, Edge, Firefox, Safari)
2. **Navigate to one of these URLs:**
   - `http://SERVERNAME:8000` (e.g., `http://MDM-SERVER:8000`)
   - `http://192.168.x.x:8000` (e.g., `http://192.168.1.50:8000`)
   - `http://localhost:8000` (only on the server machine)

3. **You should see the CodePuppyDAR search page**

### Using the Application

1. Enter an **Item ID** (e.g., `659608850`)
2. Click **Search**
3. View product details:
   - Product image
   - Item number and GTIN
   - Catalog GTIN (if available)
   - ACL Performance trends
4. Click **Download PDF** to get a print card
5. Use **Developer Info** (expandable) to see API response details

---

## Firewall Configuration

### Windows Defender Firewall Setup

#### Option 1: Using GUI (Easiest)

1. Open **Windows Defender Firewall with Advanced Security**
   - Search for "Windows Defender Firewall" in Start menu
2. Click **Inbound Rules** (left side)
3. Click **New Rule** (right side)
4. Select:
   - Rule type: **Port**
   - Protocol: **TCP**
   - Port: **8000**
   - Action: **Allow**
   - Name: `CodePuppyDAR`
5. Click **Finish**

#### Option 2: Using Command Prompt (Admin)

Run as Administrator:
```bash
netsh advfirewall firewall add rule name="CodePuppyDAR" dir=in action=allow protocol=tcp localport=8000
```

To remove the rule later:
```bash
netsh advfirewall firewall delete rule name="CodePuppyDAR"
```

### Network Firewall

If your network has a corporate firewall:
- Open port **8000** on the server machine
- Ensure traffic to `uwms-item.prod.us.walmart.net` is allowed (API calls)
- No special VPN configuration needed if on company network

---

## Troubleshooting

### Server Won't Start

**Error: "Python is not installed or not in PATH"**
- Solution: Install Python and add to PATH
- Check: Open Command Prompt and run `python --version`

**Error: "ModuleNotFoundError: No module named 'httpx'"**
- Solution: Run `uv sync` in the CodePuppyDAR folder
- Or run `START_SERVER.bat` again

**Error: "Address already in use"**
- Another app is using port 8000
- Solution: Change port in `main.py` (line with `uvicorn.run`)
- Or stop the other application

### Clients Can't Connect

**"Connection refused" or "Unable to reach server"**
- Verify server is running (check the command window)
- Check firewall rules (see Firewall Configuration above)
- Verify using server's hostname or IP address
- Test from server machine first: `http://localhost:8000`

**API Key Error ("invalid api-key")**
- Check `.env` file has correct MDM_API_KEY
- Verify no extra spaces in the key
- Ensure the key hasn't expired

**"No ACL data available"**
- The item number exists in MDM but not in `read_rates.csv`
- This is normal - the CSV only contains items with ACL performance data
- Product details will still display

### Performance Issues

If the app is slow:
1. Check server machine CPU/RAM usage
2. Close unnecessary applications
3. Check network bandwidth (CSV file is 6.4 MB)
4. Consider upgrading to a better server machine

---

## Technical Details

### Architecture

```
Client Machine                Server Machine
================             ================
  Web Browser    <---HTTP--->   FastAPI App
  (Chrome/Edge)                   |
                                  +-- Calls MDM API
                                  |
                                  +-- Reads read_rates.csv
                                  |
                                  +-- Generates PDFs
```

### Data Flow

1. User searches for Item ID
2. Server calls MDM API (`uwms-item.prod.us.walmart.net`)
3. Server reads `read_rates.csv` using Item ID as key (MDS_FAM_ID column)
4. Server generates HTML response + optional PDF
5. Client displays in browser

### Key Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI application (3,400 lines) |
| `.env` | API credentials (server-side only) |
| `read_rates.csv` | ACL performance data (27,360 unique items) |
| `START_SERVER.bat` | Startup script for Windows |
| `README.md` | Application documentation |

### Important Notes

- **MDS_FAM_ID in read_rates.csv = Item Number**
  - When searching for item 659608850, the app looks up "659608850" in the MDS_FAM_ID column
  - This is NOT the merchandise family ID from the API - it's the actual item number

- **PDF Generation**
  - PDFs are generated server-side (no plugin needed on client)
  - Client receives a ready-to-download file
  - No special software required

- **Session Management**
  - No user accounts or login needed
  - Each search is independent
  - No data stored between sessions

### Port and URL Customization

To change from port 8000 to a different port (e.g., 8080):

1. Open `main.py`
2. Find the last line: `uvicorn.run(app, host="0.0.0.0", port=8000)`
3. Change to: `uvicorn.run(app, host="0.0.0.0", port=8080)`
4. Update firewall rules for the new port
5. Restart server

---

## Maintenance

### Regular Tasks

**Daily/Weekly:**
- Monitor server uptime
- Check error logs in command window
- Verify clients can connect

**Monthly:**
- Update `read_rates.csv` with latest ACL data
- Back up `.env` file (store securely)
- Review application logs

**Quarterly:**
- Test disaster recovery (rebuild from backup)
- Review API key expiration
- Update Python if major patches released

### Backup Strategy

Back up these files regularly:
- `.env` (credentials) - store securely in vault
- `read_rates.csv` (data) - 6.4 MB
- `main.py` (code) - use version control

---

## Support and Questions

### Common Questions

**Q: How many users can connect at once?**
- A: Tested with 10+ concurrent users. For 20+, consider load balancing.

**Q: Does CodePuppyDAR store user data?**
- A: No. All data is read-only from MDM API and read_rates.csv. No searches are logged.

**Q: Can we run multiple instances?**
- A: Yes, on different ports. Use load balancer for production setup.

**Q: What if the CSV file gets corrupted?**
- A: The app will fail gracefully. Restore from backup or regenerate the CSV.

### Getting Help

1. Check the **Troubleshooting** section above
2. Review **README.md** for quick reference
3. Check Windows Event Viewer for system errors
4. Verify `.env` credentials with your Walmart contact

---

## Checklist: Server Ready?

Before announcing to users, verify:

- [ ] Server machine has Python 3.10+ installed
- [ ] CodePuppyDAR folder copied to server
- [ ] `.env` file configured with valid API key
- [ ] `read_rates.csv` file present (6.4 MB)
- [ ] Server can reach `uwms-item.prod.us.walmart.net`
- [ ] START_SERVER.bat starts without errors
- [ ] Port 8000 is open in Windows Firewall
- [ ] Test from another machine: `http://SERVERNAME:8000`
- [ ] Search for a test item works
- [ ] Download PDF works
- [ ] Share URL with team

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jun 2026 | Initial network deployment guide |

---

**Last Updated: June 2026**
