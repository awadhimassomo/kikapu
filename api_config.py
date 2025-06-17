"""
API configuration utility for Swagger documentation in the Kikapu project.
This file contains decorators and utilities to improve the API documentation.
"""
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

# Common response schemas
token_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'access': openapi.Schema(type=openapi.TYPE_STRING, description='JWT access token'),
        'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='JWT refresh token'),
        'user': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'name': openapi.Schema(type=openapi.TYPE_STRING),
                'phoneNumber': openapi.Schema(type=openapi.TYPE_STRING),
                'user_type': openapi.Schema(type=openapi.TYPE_STRING),
            }
        )
    }
)

error_response = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'error': openapi.Schema(type=openapi.TYPE_STRING),
        'status': openapi.Schema(type=openapi.TYPE_INTEGER),
        'details': openapi.Schema(type=openapi.TYPE_OBJECT),
    }
)

# Common request/response examples
def get_token_example():
    return {
        'access': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
        'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
        'user': {
            'id': 123,
            'name': 'John Doe',
            'phoneNumber': '+255123456789',
            'user_type': 'AGENT'
        }
    }

def get_error_example():
    return {
        'error': 'Invalid credentials',
        'status': 400,
        'details': {
            'password': ['This field is required']
        }
    }

# Common response decorators for view functions
def swagger_login_response():
    """Decorator for login API views to show proper response in Swagger"""
    return swagger_auto_schema(
        operation_description="Login with phone number and password to get JWT token",
        responses={
            200: openapi.Response('Successful login', schema=token_response, examples={
                'application/json': get_token_example()
            }),
            400: openapi.Response('Invalid credentials', schema=error_response, examples={
                'application/json': get_error_example()
            }),
        }
    )

# API Endpoint Configuration
# Environment settings (default to local for development)
ENVIRONMENT = 'LOCAL'  # Can be 'LOCAL' or 'PRODUCTION'

# Base URLs
BASE_URLS = {
    'LOCAL': 'http://127.0.0.1:8000/api/',
    'PRODUCTION': 'https://kikapu.co.tz/api/'
}

# API endpoint paths
CREDITS_API = {
    'nfc_cards': '',  # Will be populated dynamically
    'transactions': '',
    'postpaid_applications': '',
    'agent_recommendations': ''
}

REGISTRATION_API = {
    'login': '',  # Will be populated dynamically 
    'register': '',
    'profile': '',
    'update_pin': ''
}

MARKETPLACE_API = {
    'products': '',  # Will be populated dynamically
    'categories': ''
}

# Headers
DEFAULT_HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

def set_environment(env):
    """Set the API environment (LOCAL or PRODUCTION)"""
    global ENVIRONMENT
    if env in ['LOCAL', 'PRODUCTION']:
        ENVIRONMENT = env
        # Refresh endpoint URLs with new environment
        update_endpoint_urls()
        return True
    return False

def get_base_url():
    """Get the base URL for the current environment"""
    return BASE_URLS.get(ENVIRONMENT, BASE_URLS['LOCAL'])

def update_endpoint_urls():
    """Update all API endpoints with the current base URL"""
    base = get_base_url()
    
    # Update Credits API endpoints
    CREDITS_API['nfc_cards'] = f"{base}credits/nfc-cards/"
    CREDITS_API['transactions'] = f"{base}credits/transactions/"
    CREDITS_API['postpaid_applications'] = f"{base}credits/applications/"
    CREDITS_API['agent_recommendations'] = f"{base}credits/recommendations/"
    
    # Update Registration API endpoints
    REGISTRATION_API['login'] = f"{base}auth/login/"
    REGISTRATION_API['register'] = f"{base}auth/register/"
    REGISTRATION_API['profile'] = f"{base}auth/profile/"
    REGISTRATION_API['update_pin'] = f"{base}auth/update-pin/"
    
    # Update Marketplace API endpoints
    MARKETPLACE_API['products'] = f"{base}marketplace/products/"
    MARKETPLACE_API['categories'] = f"{base}marketplace/categories/"
    
def get_auth_headers(token=None):
    """Get headers with authentication token if available"""
    headers = DEFAULT_HEADERS.copy()
    
    if token:
        headers['Authorization'] = f"Bearer {token}"
        
    return headers

# Initialize API endpoints with default environment
update_endpoint_urls()