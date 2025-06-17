"""
Authentication Debug Views for Market Research API
Used to help diagnose authentication issues in the mobile app
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def auth_test_endpoint(request):
    """
    Test endpoint that requires authentication.
    Returns information about the authentication state.
    This helps mobile developers debug their authentication implementation.
    """
    # Log detailed information about the request
    logger.info(f"Auth test request from user: {request.user}")
    logger.info(f"Auth header: {request.META.get('HTTP_AUTHORIZATION', 'None')}")
    
    # Extract useful debugging information
    auth_header = request.META.get('HTTP_AUTHORIZATION', 'None')
    auth_working = request.user.is_authenticated
    
    # Determine if bearer token was used incorrectly
    using_bearer = False
    if auth_header != 'None' and auth_header.startswith('Bearer '):
        using_bearer = True
    
    # Get all HTTP headers
    headers = {k.replace('HTTP_', ''): v for k, v in request.META.items() 
               if k.startswith('HTTP_')}
    
    # Provide helpful response for debugging
    return Response({
        'auth_working': auth_working,
        'user': request.user.phoneNumber if hasattr(request.user, 'phoneNumber') else str(request.user),
        'auth_header_received': auth_header,
        'correct_format': auth_header.startswith('Token ') if auth_header != 'None' else False,
        'using_bearer_incorrectly': using_bearer,
        'all_request_headers': headers,
        'helpful_tips': [
            "Header name should be 'Authorization'",
            "Header value should start with 'Token ' (not 'Bearer')",
            "The full header should be: 'Authorization: Token <your-token-value>'",
            "The token should match what you received from the login endpoint"
        ],
        'status': 'success' if auth_working else 'failed',
        'message': "Authentication successful! Your token is correctly formatted." if auth_working 
                  else "Authentication failed. See the details above for what went wrong."
    })
