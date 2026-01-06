# Quick Reference Card 🚀

## Default Credentials
```
Email:    admin@g.com
Password: admin
```

## Essential Commands

### Start Application
```bash
python3 app.py
```
Access at: `http://localhost:8080/`

### Manage Users
```bash
python3 admin_user_manager.py
```

### Check Status
```bash
# View logs
tail -f logs/bloomberg_ingestion.log

# Check running processes
ps aux | grep python3
```

## File Locations

### Key Configuration
- `.env` - HANA credentials
- `app.py` - Main application
- `login.html` - Login page UI

### Authentication
- `utils/crypto_utils.py` - Password encryption
- `db/auth_service.py` - Authentication logic
- `db/hana_client.py` - Database connection

### Documentation
- `AUTH_README.md` - Full authentication docs
- `DEPLOYMENT_CHECKLIST.md` - Pre-presentation checklist
- `IMPLEMENTATION_SUMMARY.md` - Complete implementation details

## Database Tables

### USERS Table
```
BLOOMBERG_DATA.USERS
├── ID (Primary Key)
├── EMAIL (Unique)
├── PASSWORD_ENCRYPTED
├── FULL_NAME
├── ROLE
├── IS_ACTIVE
├── CREATED_AT
├── LAST_LOGIN
└── LOGIN_ATTEMPTS
```

### Financial Data
```
BLOOMBERG_DATA.FINANCIAL_RATIOS
BLOOMBERG_DATA.FINANCIAL_DATA_ADVANCED
```

## Testing Mode

### Enable CSV (if HANA unavailable)
Uncomment in `app.py` lines 143-150:
```python
try:
    basic_df = pd.read_csv('basic.csv')
    advance_df = pd.read_csv('advance.csv')
    csv_data = {'basic': basic_df, 'advance': advance_df}
except Exception as e:
    logger.error(f"Failed to load CSV files: {e}")
```

## Common Issues

### "Authentication service unavailable"
→ HANA not connected, check `.env`

### "User not found: admin@g.com"
→ Run `python3 admin_user_manager.py` to create user

### Dashboard shows no data
→ Check HANA connection or enable CSV mode

### Login page not working
→ Check logs, verify Flask server started correctly

## Admin Tool Menu

```
1. Create new user
2. View user (with decrypted password)
3. List all users
4. Test login
5. Encrypt text
6. Decrypt text
7. Exit
```

## URLs

```
/                    → Redirects to /login
/login               → Login page (GET) or authenticate (POST)
/logout              → Clear session and redirect to login
/dashboard/          → Main dashboard (requires login)
```

## Environment Variables Required

```env
HANA_ADDRESS=your-server.hanacloud.ondemand.com
HANA_PORT=443
HANA_USER=your-username
HANA_PASSWORD=your-password
HANA_SCHEMA=BLOOMBERG_DATA
```

## Demo Flow

1. ✅ Start: `python3 app.py`
2. ✅ Open: `http://localhost:8080/`
3. ✅ Login: admin@g.com / admin
4. ✅ Show: Dashboard features
5. ✅ Optional: Run admin tool to show encryption

## Security Features Checklist

- [x] Passwords encrypted in database
- [x] Session-based authentication
- [x] Login attempt tracking
- [x] Different error messages (security)
- [x] Logout functionality
- [x] Admin tool with decrypt capability

## Production Checklist

- [ ] Change SECRET_PHRASE in crypto_utils.py
- [ ] Configure real HANA credentials
- [ ] Test login with admin user
- [ ] Verify dashboard loads data
- [ ] Test logout functionality
- [ ] Review error messages

## Support Files

All documentation:
- AUTH_README.md - Authentication system
- DEPLOYMENT_CHECKLIST.md - Presentation prep
- IMPLEMENTATION_SUMMARY.md - Technical details
- QUICK_REFERENCE.md - This file

---

**Ready for presentation! Good luck! 🎉**
