# OTP (One-Time Password) API Endpoints

This document describes the API endpoints available for OTP verification in the Kikapu platform.

## Table of Contents
1. [Verify OTP](#verify-otp)
2. [Resend OTP](#resend-otp)
3. [Agent Login](#agent-login)

## Verify OTP

Verifies a one-time password (OTP) sent to a user's phone number for authentication.

**Endpoint:** `/auth/api/verify-otp/`

**Method:** `POST`

**Request Body:**

```json
{
  "phoneNumber": "+255712345678",
  "otp": "12345",
  "business_id": 123  // Optional
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| phoneNumber | string | Yes | User's phone number with country code |
| otp | string | Yes | 5-digit One-Time Password |
| business_id | integer | No | Optional business ID for business accounts |

**Success Response:**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 123,
    "name": "John Doe",
    "phoneNumber": "+255712345678",
    "email": "john@example.com",
    "user_type": "BUSINESS"
  }
}
```

For business accounts, additional business information is included:

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "business": {
    "id": 45,
    "name": "My Store",
    "type": "retailer",
    "is_verified": true
  },
  "user": {
    "id": 123,
    "name": "John Doe",
    "phoneNumber": "+255712345678",
    "email": "john@example.com"
  }
}
```

**Error Responses:**

- `400 Bad Request` - Invalid input data
- `401 Unauthorized` - OTP expired or invalid
- `404 Not Found` - User not found

## Resend OTP

Resends a one-time password (OTP) to a user's phone number.

**Endpoint:** `/auth/api/resend-otp/`

**Method:** `POST`

**Request Body:**

```json
{
  "phoneNumber": "+255712345678"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| phoneNumber | string | Yes | User's phone number with country code |

**Success Response:**

```json
{
  "message": "OTP resent successfully"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid input or OTP resent too soon (must wait 60 seconds between resend requests)
- `404 Not Found` - User not found
- `500 Internal Server Error` - Failed to send SMS

## Agent Login

API endpoint for delivery agents to log in via mobile app.

**Endpoint:** `/auth/api/agent/login/`

**Method:** `POST`

**Request Body:**

```json
{
  "phoneNumber": "+255712345678",
  "password": "securepassword"
}
```

Alternative for Flutter apps:
```json
{
  "username": "+255712345678",
  "password": "securepassword"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| phoneNumber | string | Yes* | Agent's phone number |
| username | string | Yes* | Alternative to phoneNumber for Flutter apps |
| password | string | Yes | Agent's password |

\* Either phoneNumber or username is required

**Success Response:**

```json
{
  "success": true,
  "message": "Login successful",
  "user": {
    "id": 123,
    "name": "John Agent",
    "phoneNumber": "+255712345678",
    "email": "agent@example.com",
    "agent_id": "AG12345",
    "assigned_area": "Central District"
  },
  "token": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  }
}
```

**Error Responses:**

- `400 Bad Request` - Phone number and password are required
- `403 Forbidden` - Agent account is inactive
- `404 Not Found` - Agent not found or invalid credentials
