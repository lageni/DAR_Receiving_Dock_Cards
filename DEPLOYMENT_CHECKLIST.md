# CodePuppyDAR - Deployment Checklist

## Pre-Deployment (Admin)

### Server Machine Selection
- [ ] Machine runs Windows 10/11 or Server 2016+
- [ ] Machine has at least 4GB RAM, 100GB disk space
- [ ] Machine can run 24/7 or as needed
- [ ] Machine has network access to MDM API
- [ ] Machine hostname is known (e.g., `MDM-SERVER`)
- [ ] Machine IP address is known (e.g., `192.168.1.50`)

### Software Installation
- [ ] Python 3.10+ installed globally
- [ ] Python verified: `python --version`
- [ ] Python in PATH (can run from any folder)
- [ ] Git (optional, for version control)

### Files Prepared
- [ ] Entire CodePuppyDAR folder copied to server
- [ ] `main.py` present
- [ ] `README.md` present
- [ ] `NETWORK_SETUP_GUIDE.md` present
- [ ] `START_SERVER.bat` present
- [ ] `SETUP.bat` present
- [ ] `QUICK_REFERENCE.txt` present
- [ ] `read_rates.csv` present (6.4 MB)
- [ ] `.env` file created with credentials

### Credentials & Secrets
- [ ] MDM_API_KEY obtained from Walmart contact
- [ ] MDM_API_KEY added to `.env` file
- [ ] MDM_FACILITY_NUM confirmed (usually 6068)
- [ ] MDM_FACILITY_COUNTRY_CODE set (usually US)
- [ ] `.env` file permissions set (restricted to admins only)
- [ ] `.env` file backed up in secure location

### Network Configuration
- [ ] Port 8000 available (not used by other apps)
- [ ] Windows Firewall rule added for port 8000
- [ ] Corporate firewall rule added (if applicable)
- [ ] MDM API endpoint reachable from server
- [ ] Test: `ping uwms-item.prod.us.walmart.net`

---

## Initial Setup (Admin)

### Run Setup Script
- [ ] Navigate to CodePuppyDAR folder
- [ ] Run: `SETUP.bat`
- [ ] Script completes without errors
- [ ] Dependencies installed successfully
- [ ] All 5 checks pass (Python, dependencies, .env, CSV, connectivity)

### Verify Files
- [ ] `read_rates.csv` exists and is readable
- [ ] File size ~6.4 MB (verify with: `dir read_rates.csv`)
- [ ] `.env` contains valid MDM_API_KEY
- [ ] No special characters or extra spaces in credentials

---

## Server Startup & Testing (Admin)

### First Boot
- [ ] Navigate to CodePuppyDAR folder
- [ ] Double-click: `START_SERVER.bat`
- [ ] Command window opens
- [ ] Message shows: "Uvicorn running on http://0.0.0.0:8000"
- [ ] Message shows server IP and network access URLs
- [ ] Browser auto-opens to `http://localhost:8000`

### Functional Testing - Same Machine
- [ ] Search page loads
- [ ] Example item: `659608850` (Tadin Merchandise)
- [ ] Click Example button (pre-fills item ID)
- [ ] Click Search button
- [ ] Product details display
- [ ] Image displays
- [ ] Item ID and GTIN shown
- [ ] ACL Performance chart appears (if data exists)
- [ ] Click "Download PDF"
- [ ] PDF downloads without errors

### Network Testing - Different Machine
- [ ] On another machine, open browser
- [ ] Navigate to: `http://SERVERNAME:8000`
- [ ] Search page loads
- [ ] Same search and download tests work
- [ ] Note response time (should be <2 seconds per search)

### API Connectivity Test
- [ ] Search for valid item ID
- [ ] "Developer Info" section shows API response
- [ ] Response contains valid JSON
- [ ] "merchandiseFamilyID" field present
- [ ] "productDefinition" with product name shown

### Error Scenarios (Test Recovery)
- [ ] Stop server (Ctrl+C), verify error handling
- [ ] Restart server, verify recovery
- [ ] Search for invalid item (test 404 handling)
- [ ] Try incomplete search (test validation)

---

## User Deployment

### Communication
- [ ] IT/Admin sends URL to all users
- [ ] Send QUICK_REFERENCE.txt to users
- [ ] Provide contact info for support
- [ ] Share NETWORK_SETUP_GUIDE.md for reference

### User Training (Optional)
- [ ] Demo: How to search by Item ID
- [ ] Demo: How to view ACL Performance
- [ ] Demo: How to download PDF
- [ ] Demo: How to expand Developer Info
- [ ] Q&A session

### User Access Verification
- [ ] 1-2 test users report successful connection
- [ ] Users can search items
- [ ] PDFs download without issues
- [ ] No connectivity problems reported

---

## Post-Deployment (Ongoing)

### Daily Monitoring
- [ ] Server uptime verified
- [ ] No error messages in command window
- [ ] Performance acceptable (API responses <2s)
- [ ] Users report no issues

### Weekly Maintenance
- [ ] Check server error logs
- [ ] Verify `read_rates.csv` is current
- [ ] Backup `.env` file
- [ ] Test one search from each user group

### Monthly Tasks
- [ ] Update `read_rates.csv` if new data available
- [ ] Review Python version (update if patches)
- [ ] Backup application folder
- [ ] Document any issues/resolutions

### Quarterly Review
- [ ] Test disaster recovery (restore from backup)
- [ ] Verify API key hasn't expired
- [ ] Review user feedback/issues
- [ ] Plan any upgrades or improvements

---

## Troubleshooting During Deployment

### Server Won't Start
**Error: "Python is not installed"**
- Verify: `python --version` in command prompt
- Reinstall Python, ensure PATH is set
- Restart computer after installation

**Error: "Address already in use"**
- Port 8000 is used by another application
- Find what's using port: `netstat -ano | findstr :8000`
- Change port in `main.py` line with `port=8000`
- Update firewall rule for new port

**Error: "ModuleNotFoundError"**
- Run SETUP.bat again
- Manually run: `pip install httpx fastapi uvicorn python-dotenv fpdf2`
- Verify dependencies installed: `pip list`

### Client Connection Issues
**"Cannot reach server"**
- Test from server machine first: `http://localhost:8000`
- Check Windows Firewall rule exists
- Verify correct server name/IP address
- Check corporate firewall allows port 8000
- Ping server: `ping SERVERNAME`

**"API Key Error (401/400)"**
- Verify `.env` has valid MDM_API_KEY
- Check for extra spaces in key
- Contact Walmart to verify key is active
- Verify facility number (should be 6068)

**"No ACL data available"**
- This is normal if item not in `read_rates.csv`
- Verify CSV file exists: `dir read_rates.csv`
- Try another known item
- Check CSV not corrupted: open in Excel/text editor

### Performance Issues
**Server is slow (>5 second responses)**
- Check server CPU/RAM usage
- Close unnecessary applications
- Check network bandwidth
- Consider moving to better hardware

**Many users getting timeouts**
- Server may be overloaded
- Reduce concurrent user limit or add more servers
- Implement load balancing for multiple instances
- Consider production deployment with Gunicorn

---

## Rollback Plan

### If Deployment Fails
1. Stop server (Ctrl+C)
2. Restore `.env` from backup
3. Restore `read_rates.csv` from backup
4. Restart server
5. Test basic functionality
6. If still failing, revert to previous version (if using git)

### Backup Locations
- `.env` - Store in secure vault (never in code repo)
- `read_rates.csv` - Store in network backup
- `main.py` - Use git for version history
- Entire folder - Archive weekly

---

## Sign-Off

- [ ] **Admin Name**: _________________ **Date**: _______
- [ ] **IT Manager**: _________________ **Date**: _______
- [ ] **Operations**: _________________ **Date**: _______

**Deployment Status**: 
- [ ] Ready for Production
- [ ] Testing Phase
- [ ] Pilot Phase
- [ ] On Hold

**Notes**:
_____________________________________________________________________________
_____________________________________________________________________________

---

## Document Version

- Version: 1.0
- Last Updated: June 2026
- Next Review: August 2026
