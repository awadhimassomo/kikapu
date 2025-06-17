"""
Authentication Debug Middleware for KIKAPU

This middleware logs authentication headers for API requests to help debug 401 Unauthorized issues.
"""

import logging
from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions

class AuthDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger(__name__)
        
    def __call__(self, request):
        # Check if it's an API request
        if request.path.startswith('/api/'):
            # Check if using Bearer instead of Token and correct it silently
            auth_header = request.META.get('HTTP_AUTHORIZATION', 'None')
            if auth_header != 'None' and auth_header.startswith('Bearer '):
                # Silently correct the Bearer prefix to Token
                corrected_header = auth_header.replace('Bearer ', 'Token ', 1)
                request.META['HTTP_AUTHORIZATION'] = corrected_header
        
        # Get response as normal
        response = self.get_response(request)
        return response
