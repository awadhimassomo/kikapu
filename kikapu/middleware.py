class SecurityHeadersMiddleware:
    """
    Middleware to add security headers to responses to prevent Cross-Origin-Opener-Policy warnings
    and enhance the security of the application.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Only add strict security headers in production
        from django.conf import settings
        if not settings.DEBUG:
            response['Cross-Origin-Opener-Policy'] = 'same-origin'
            response['Cross-Origin-Embedder-Policy'] = 'require-corp'
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response