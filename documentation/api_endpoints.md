# Kikapu API Endpoints Documentation

This document provides a comprehensive list of all API endpoints available in the Kikapu project, organized by functionality.

## Authentication Endpoints

- **POST `/auth/api/agent/login/`**: Agent login (returns JWT token)
- **POST `/auth/api/verify-otp/`**: Verify OTP code for user registration or authentication
- **POST `/auth/api/resend-otp/`**: Resend OTP code to user's phone number

See full details in: [OTP API Documentation](./otp_api_endpoints.md)

## Card Management

- **POST `/card/register/`**: Register new blank NFC card (Super Agents only)
- **POST `/card/assign/`**: Assign card to a Customer
- **POST `/card/scan/`**: Scan card, fetch customer info

## Customer Management

- **POST `/customer/register/`**: Register customer + select Prepaid/Postpaid

## Payment Processing

- **POST `/payment/authorize/`**: Make a payment after NFC tap

## Postpaid System

- **POST `/postpaid/apply/`**: Customer applies for Postpaid access
- **POST `/agent/recommend/`**: Agent recommends Customer for Postpaid approval
- **GET `/admin/postpaid-applications/`**: Admin views Postpaid Applications
- **POST `/admin/postpaid-application/<id>/approve/`**: Admin approves Application and sets Credit Limit
- **POST `/admin/postpaid-application/<id>/reject/`**: Admin rejects Postpaid Application

## Transactions

- **GET `/transactions/`**: View transactions (filter by agent, customer, date)

## API Data Formats

### Authentication Response Format
```json
{
    "access": "JWT_ACCESS_TOKEN",
    "refresh": "JWT_REFRESH_TOKEN",
    "user": {
        "id": 123,
        "name": "User Full Name",
        "phoneNumber": "+255123456789",
        "user_type": "AGENT"
    }
}
```

### Customer Profile Response Format
```json
{
    "id": 123,
    "name": "Customer Full Name",
    "phoneNumber": "+255123456789",
    "email": "customer@example.com",
    "card_type": "PREPAID|POSTPAID",
    "credit_limit": 1000,
    "balance": 500,
    "joined_date": "2023-01-01"
}
```

### Card Information Response Format
```json
{
    "id": "ABC12345",
    "card_number": "1234567890123456",
    "status": "ACTIVE|INACTIVE|LOCKED",
    "customer_id": 123,
    "customer_name": "Customer Full Name",
    "card_type": "PREPAID|POSTPAID",
    "balance": 500,
    "credit_limit": 1000,
    "issue_date": "2023-01-01"
}
```

### Transaction Response Format
```json
{
    "id": 456,
    "transaction_type": "PAYMENT|TOPUP|REFUND",
    "amount": 100.50,
    "customer_id": 123,
    "customer_name": "Customer Full Name",
    "agent_id": 789,
    "agent_name": "Agent Full Name",
    "card_number": "1234567890123456",
    "timestamp": "2023-01-01T12:30:45Z",
    "status": "COMPLETED|PENDING|FAILED",
    "reference_number": "TX123456789"
}
```

## Authentication

All API endpoints require authentication using JWT (JSON Web Tokens) except for the login endpoint. To authenticate:

1. Obtain a token by sending credentials to `/agent/login/`
2. Include the token in subsequent requests in the Authorization header:
   ```
   Authorization: Bearer <access_token>
   ```

## Error Response Format

```json
{
    "error": "Description of the error",
    "status": 400,
    "details": {
        "field_name": ["Error details for specific field"]
    }
}
```

## HTTP Status Codes

The API uses standard HTTP status codes:
- **200 OK**: The request was successful
- **201 Created**: A new resource was successfully created
- **400 Bad Request**: The request was invalid or cannot be served
- **401 Unauthorized**: Authentication failed or user lacks necessary permissions
- **403 Forbidden**: The server understood the request but refuses to authorize it
- **404 Not Found**: The requested resource could not be found

## Rate Limiting

API endpoints are subject to rate limiting to prevent abuse:
- 100 requests per minute for authenticated users
- 20 requests per minute for unauthenticated users

## Pagination

List endpoints return paginated results with the following format:
```json
{
    "count": 100,
    "next": "http://example.com/transactions/?page=2",
    "previous": null,
    "results": []
}
```

## Filtering and Searching

Many list endpoints support filtering and searching through query parameters:
- `?search=term` - Search across relevant fields
- `?ordering=field_name` - Order results by specified field
- `?field_name=value` - Filter by exact field value

For example, to filter transactions:
- `/transactions/?customer_id=123` - Transactions for a specific customer
- `/transactions/?agent_id=789` - Transactions processed by a specific agent
- `/transactions/?date_from=2023-01-01&date_to=2023-01-31` - Transactions within a date range