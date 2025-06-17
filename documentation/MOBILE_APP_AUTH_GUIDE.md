# KIKAPU Mobile App Authentication Guide

## Authentication Issues (401/403 Errors)

We've identified that the mobile app is successfully logging in but receiving errors when submitting market price data. This could be due to two reasons:

1. **Authentication Issue (401 Unauthorized)**: The token is not being properly sent with API requests
2. **Authorization Issue (403 Forbidden)**: The token is valid, but the user doesn't have the correct agent permissions

## What the Server Expects vs. What the App Sends

### Server Expectation
The server expects the authentication token to be included in the HTTP headers in this format:

```
Authorization: Token <your-token-value>
```

### Common Issues in the Mobile App
1. **Missing Authorization header**: The app isn't sending any token at all
2. **Wrong prefix**: Using `Bearer` instead of `Token`
3. **Wrong header name**: Using a header name other than `Authorization`

## IMPORTANT UPDATE: Authorization Fix

We've identified and fixed an issue causing 403 Forbidden responses even with correct authentication:

1. We identified a server-side issue where the User model was missing the `is_agent` property that the API was checking for
2. We've fixed this issue by adding the property and ensuring that users logging in through the agent endpoint have their user_type set to 'AGENT'
3. This fix has been deployed to the server

If you were getting 403 Forbidden errors even with the correct authentication header, this fix should resolve those issues. Please update to the latest app version which includes these fixes. For more details on the fix, see `FIXING_AUTH_ISSUES.md`.

## How to Correctly Implement Authentication in the Mobile App

### 1. Store the Token After Login

When the login response is received:

```dart
// After successful login
Future<void> storeToken(String token) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString('auth_token', token);
  print('Token stored successfully');
}

// In your login method
final response = await http.post(
  Uri.parse('https://api.kikapu.com/api/agent/login/'),
  headers: {'Content-Type': 'application/json'},
  body: jsonEncode({
    'phoneNumber': phoneNumber,
    'password': password,
  }),
);

final data = jsonDecode(response.body);

if (data['success'] == true) {
  // Store the token
  await storeToken(data['token']);
}
```

### 2. Send the Token with Every API Request

For every request to an authenticated endpoint:

```dart
Future<Map<String, String>> getAuthHeaders() async {
  final prefs = await SharedPreferences.getInstance();
  final token = prefs.getString('auth_token');
  
  final headers = {'Content-Type': 'application/json'};
  
  if (token != null) {
    // IMPORTANT: Must use 'Token' prefix, not 'Bearer'
    headers['Authorization'] = 'Token $token';
  }
  
  return headers;
}

Future<void> submitMarketPrice(Map<String, dynamic> priceData) async {
  final headers = await getAuthHeaders();
  
  final response = await http.post(
    Uri.parse('https://api.kikapu.com/api/market_research/price/submit/'),
    headers: headers,
    body: jsonEncode(priceData),
  );
  
  // Handle response...
}
```

## Debug Checklist

If you're still experiencing 401 errors:

1. **Print the token after login**:
   ```dart
   print('Token received: ${data['token']}');
   ```

2. **Print the headers when making API requests**:
   ```dart
   print('Using headers: $headers');
   ```

3. **Check the network logs** in browser developer tools or using a tool like Charles Proxy to verify what headers are actually sent

4. **Add log statements** on the server to verify what's being received

## Testing Your Fix

We've added debug middleware on the server to log the headers received, so you can use the `auth_test.py` script in the documentation folder to test your authentication implementation:

```bash
python documentation/auth_test.py
```

This will test both the login and market price submission endpoints, showing exactly what headers work vs. what fails.

## Complete Flutter Example

For a complete implementation, refer to the Flutter examples in the documentation folder:

- `auth_quickfix.dart`: A minimal authentication implementation
- `market_price_submission_fix.dart`: A complete market price submission screen
- `flutter_auth_implementation.dart`: A comprehensive API service implementation
