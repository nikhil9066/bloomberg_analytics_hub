# Authentication System Documentation

## Overview

The Bloomberg Analytics Hub now includes a secure authentication system with encrypted password storage in SAP HANA database.

## Features

- **Encrypted Password Storage**: All passwords are encrypted using Fernet symmetric encryption
- **Database-backed Authentication**: User credentials stored in HANA `USERS` table
- **Session Management**: Flask sessions for maintaining logged-in state
- **Admin Management Tool**: Command-line utility for managing users

## Default Credentials

```
Email: admin@g.com
Password: admin
```

## User Management

### Using the Admin Tool

Run the admin user management script:

```bash
python3 admin_user_manager.py
```

This provides an interactive menu to:
1. Create new users
2. View user details (with decrypted passwords)
3. List all users
4. Test login credentials
5. Encrypt/decrypt arbitrary text

### Database Schema

The `USERS` table structure:

```sql
CREATE TABLE "BLOOMBERG_DATA"."USERS" (
    "ID" INTEGER PRIMARY KEY,
    "EMAIL" NVARCHAR(255) UNIQUE NOT NULL,
    "PASSWORD_ENCRYPTED" NVARCHAR(500) NOT NULL,
    "FULL_NAME" NVARCHAR(255),
    "ROLE" NVARCHAR(50) DEFAULT 'USER',
    "IS_ACTIVE" BOOLEAN DEFAULT TRUE,
    "CREATED_AT" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "LAST_LOGIN" TIMESTAMP,
    "LOGIN_ATTEMPTS" INTEGER DEFAULT 0
)
```

## Security Features

### Password Encryption

Passwords are encrypted using the Fernet symmetric encryption algorithm:

```python
from utils.crypto_utils import encrypt_password, decrypt_password

# Encrypt
encrypted = encrypt_password("my_password")

# Decrypt (for admin viewing only)
decrypted = decrypt_password(encrypted)
```

### Login Flow

1. User submits email and password via login form
2. Backend validates credentials against HANA database
3. Password is decrypted and compared
4. On success:
   - User session is created
   - Last login time is updated
   - Login attempts counter is reset
5. On failure:
   - Login attempts counter is incremented
   - Error message returned (different for non-existent vs wrong password)

### Error Messages

- **User doesn't exist**: `"User account not found. If you believe this is an error, please contact the administrator. Attempted email: {email}"`
- **Wrong password**: `"Invalid credentials. Please check your password."`

## Files

### New Files Created

1. **`utils/crypto_utils.py`**: Encryption/decryption utilities
2. **`db/auth_service.py`**: Authentication service class
3. **`admin_user_manager.py`**: Admin CLI tool for user management

### Modified Files

1. **`db/hana_client.py`**: Added USERS table schema
2. **`app.py`**:
   - Added authentication routes
   - Integrated session management
   - Switched to HANA database (CSV commented out for testing)
3. **`login.html`**: Updated to use AJAX authentication

## Production vs Testing

### Production Mode (HANA Database)

The application is now configured for production with HANA database:

```python
# app.py - Production configuration
data_service = FinancialDataService(config)
if data_service.connect():
    logger.info("Data service initialized and connected to HANA")
```

### Testing Mode (CSV Files)

To use CSV files for testing, uncomment these lines in `app.py`:

```python
# Load CSV data for local testing (commented out for production, uncomment if needed)
csv_data = None
# Uncomment below lines for local testing without HANA
# try:
#     basic_df = pd.read_csv('basic.csv')
#     advance_df = pd.read_csv('advance.csv')
#     logger.info(f"Loaded CSV data: {len(basic_df)} basic records, {len(advance_df)} advance records")
#     csv_data = {'basic': basic_df, 'advance': advance_df}
# except Exception as e:
#     logger.error(f"Failed to load CSV files: {e}")
#     csv_data = None
```

## Environment Configuration

Ensure your `.env` file contains HANA credentials:

```env
HANA_ADDRESS=your-hana-address
HANA_PORT=443
HANA_USER=your-username
HANA_PASSWORD=your-password
HANA_SCHEMA=BLOOMBERG_DATA
```

## Initial Setup

1. Ensure HANA database is accessible
2. Run the admin tool to initialize database:
   ```bash
   python3 admin_user_manager.py
   ```
3. The default admin user will be created automatically
4. Start the application:
   ```bash
   python3 app.py
   ```
5. Access login page at `http://localhost:8080/`

## API Endpoints

### POST /login
Authenticate user

**Request:**
```json
{
  "email": "admin@g.com",
  "password": "admin"
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Login successful",
  "redirect": "/dashboard/"
}
```

**Response (Failure):**
```json
{
  "success": false,
  "message": "Invalid credentials. Please check your password."
}
```

### GET /logout
Clear session and redirect to login

## Security Notes

⚠️ **Important Security Considerations:**

1. The encryption key is derived from `SECRET_PHRASE` in `utils/crypto_utils.py`
2. Change the `SECRET_PHRASE` before production deployment
3. Keep the `.env` file secure and never commit it to version control
4. The admin tool shows decrypted passwords - use with caution
5. Consider implementing rate limiting for login attempts
6. Session secret key is generated randomly on each server start

## Troubleshooting

### Cannot connect to HANA
- Check `.env` configuration
- Verify network connectivity
- Ensure HANA credentials are correct

### Login fails with existing credentials
- Use admin tool to verify user exists
- Check password encryption/decryption
- Review application logs

### Session not persisting
- Ensure `server.secret_key` is set
- Check browser cookie settings
- Verify Flask session configuration
