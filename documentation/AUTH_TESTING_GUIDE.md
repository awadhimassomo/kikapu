# Authentication Testing Guide

This guide explains how to test and diagnose authentication issues with the KIKAPU API.

## Testing Authentication Header Formats

We've created a script that tests different authentication header formats to determine exactly which one works with our API.

### Running the Test Script

1. Open a terminal in the project root directory
2. Run the test script:

```bash
python documentation/test_auth_formats.py
```

3. The script will:
   - Log in to get a token
   - Test different authentication header formats:
     - No authentication header
     - `Authorization: Bearer <token>` (commonly used but incorrect for our API)
     - `Authorization: Token <token>` (correct for Django REST Framework TokenAuthentication)
     - `Token: <token>` (incorrect format)
     - `Auth: <token>` (incorrect format)
     - `Authorization: <token>` (incorrect format, missing prefix)
   - Show which format works and which ones fail

### Expected Results

You should see a clear summary output like:

```
=== Test Results Summary ===
❌ FAILS: No authentication header
❌ FAILS: Authorization: Bearer <token>
✅ WORKS: Authorization: Token <token>
❌ FAILS: Token: <token>
❌ FAILS: Auth: <token>
❌ FAILS: Authorization: <token>

Use this format in your mobile app:
Authorization: Token <token>
```

## Understanding the Authentication Logs

When you make API requests, our debug middleware logs detailed information about authentication:

- The exact header received from the client
- Whether the authentication succeeded or failed
- What format is expected
- If common mistakes were detected (like using "Bearer" instead of "Token")
- Details about the user if authentication succeeded
- All request headers for context

These logs can be found in the application log file.

## Common Mobile App Authentication Issues

1. **Missing token storage**: Not saving the token after login
2. **Wrong authentication prefix**: Using `Bearer` instead of `Token`
3. **Incorrect header name**: Using something other than `Authorization`
4. **Missing Content-Type**: Not setting `Content-Type: application/json`
5. **Token expiration**: Using an expired token

## How to Fix in Your Mobile App

Follow the examples in `MOBILE_APP_AUTH_GUIDE.md` to correctly implement token-based authentication in your app.

The critical part is sending the correct header with every API request:

```dart
headers['Authorization'] = 'Token $token';
```

Not:
```dart
// These are incorrect:
headers['Authorization'] = 'Bearer $token';
headers['Token'] = token;
headers['Auth'] = token;
```

For Flutter-specific implementations, see the example files in the documentation folder.
