# KIKAPU Agent Authorization Fix

## Problem Identified

We identified an issue where mobile app agents were able to successfully authenticate (receiving a valid token) but were receiving **403 Forbidden** errors when trying to use API endpoints that require agent permissions, particularly the `/api/market_research/price/submit/` endpoint.

## Root Cause Analysis

After debugging with our auth middleware and test scripts, we discovered that:

1. The authentication was working correctly (token was valid)
2. The authorization was failing because of a permission check in `market_research/views.py` which looks for an `is_agent` property:

```python
if not hasattr(request.user, 'is_agent') or not request.user.is_agent:
    return Response(
        {"error": "Only authorized agents can submit market price data"}, 
        status=status.HTTP_403_FORBIDDEN
    )
```

3. This property did not exist on the User model, even for users with a valid DeliveryAgent instance

## Fix Implemented

We made two changes to fix this issue:

### 1. Added an `is_agent` property to the User model

```python
@property
def is_agent(self):
    """
    Check if this user is registered as a delivery agent.
    Used in market_research/views.py to authorize market price submission.
    """
    return self.user_type == 'AGENT' and hasattr(self, 'delivery_agent')
```

This property checks that:
- The user's type is set to 'AGENT'
- The user has an associated delivery_agent record

### 2. Ensure user_type is correctly set on login

Modified the `agent_api_login` function to update the user's type to 'AGENT' if it wasn't already set:

```python
# Ensure the user_type is set to 'AGENT'
if user.user_type != 'AGENT':
    user.user_type = 'AGENT'
    user.save(update_fields=['user_type'])
    logger.info(f"Updated user_type to AGENT for phoneNumber: {phoneNumber}")
```

## How to Verify the Fix

1. Have an agent log in through the mobile app
2. Try submitting market price data
3. Check the server logs to verify:
   - The token authentication succeeds
   - The `is_agent` property returns true
   - The request is authorized

## Why This Works

This fix ensures that:
1. Every user who successfully logs in through the agent login endpoint has their user_type set to 'AGENT'
2. The User model now has an `is_agent` property that returns true if the user has the proper permissions
3. The market_research price submission endpoint can correctly verify agent permissions

## Future Improvements

1. Consider standardizing agent verification logic across the application
2. Add more comprehensive agent permission checks
3. Improve error messages to make debugging easier in the future