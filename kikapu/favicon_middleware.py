import re
from django.conf import settings

class FaviconMiddleware:
    """
    Middleware to ensure the favicon is consistently injected in all HTML responses.
    This helps maintain consistent favicon across different URLs and rendering engines.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Compile the regex pattern once at initialization for better performance
        self.head_pattern = re.compile(r'</head>', re.IGNORECASE)
        
        # Create the favicon link tags
        static_url = getattr(settings, 'STATIC_URL', '/static/')
        favicon_path = f"{static_url.rstrip('/')}images/kikapuu.png"
        
        self.favicon_links = f"""
    <link rel="shortcut icon" href="{favicon_path}" type="image/png">
    <link rel="icon" type="image/png" sizes="32x32" href="{favicon_path}">
    <link rel="icon" type="image/png" sizes="16x16" href="{favicon_path}">
    <link rel="mask-icon" href="{favicon_path}" color="#395144">
"""

    def __call__(self, request):
        response = self.get_response(request)
        
        # Only process HTML responses
        if self._is_html_response(response):
            content = response.content.decode('utf-8')
            
            # Check if content has a head tag and doesn't already have the favicon
            if '</head>' in content and 'rel="shortcut icon"' not in content:
                # Insert favicon links before the </head> closing tag
                content = self.head_pattern.sub(f"{self.favicon_links}</head>", content)
                response.content = content.encode('utf-8')
                
                # Update content-length header if it exists
                if 'Content-Length' in response:
                    response['Content-Length'] = len(response.content)
        
        return response
    
    def _is_html_response(self, response):
        """Check if the response is HTML."""
        content_type = response.get('Content-Type', '')
        return (content_type.startswith('text/html') and
                hasattr(response, 'content') and
                getattr(response, 'streaming', False) is False)
