"""
API utilities for Kikapu frontend applications.
These functions make it easy to interact with the Kikapu API from frontend code.
"""

import json
import requests
from django.conf import settings
import api_config  # Changed from relative to absolute import

class KikapuAPI:
    """
    Utility class for interacting with Kikapu API endpoints.
    Handles authentication, error management, and environment switching.
    """
    
    def __init__(self, token=None, environment=None):
        """
        Initialize the API client.
        
        Args:
            token (str, optional): Authentication token
            environment (str, optional): 'LOCAL' or 'PRODUCTION'
        """
        self.token = token
        
        # Set environment if provided
        if environment:
            api_config.set_environment(environment)
    
    def get_headers(self):
        """Get headers with authentication token if available"""
        return api_config.get_auth_headers(self.token)
    
    # Credits API methods
    def register_nfc_card(self, uid):
        """Register a new blank NFC card"""
        url = api_config.CREDITS_API['nfc_cards']
        data = {'uid': uid}
        
        response = requests.post(url, json=data, headers=self.get_headers())
        return self._handle_response(response)
    
    def assign_card_to_customer(self, card_id, name, phoneNumber, pin, card_type='PREPAID'):
        """Assign an NFC card to a customer"""
        url = f"{api_config.CREDITS_API['nfc_cards']}{card_id}/assign/"
        data = {
            'name': name,
            'phoneNumber': phoneNumber,
            'pin': pin,
            'card_type': card_type
        }
        
        response = requests.post(url, json=data, headers=self.get_headers())
        return self._handle_response(response)
    
    def process_transaction(self, customer_id, amount, transaction_type, nfc_uid, pin, agent_id=None):
        """Process a payment transaction with NFC card"""
        url = f"{api_config.CREDITS_API['transactions']}authorize_payment/"
        data = {
            'customer': customer_id,
            'amount': amount,
            'transaction_type': transaction_type,
            'nfc_uid': nfc_uid,
            'pin': pin
        }
        
        if agent_id:
            data['agent'] = agent_id
            
        response = requests.post(url, json=data, headers=self.get_headers())
        return self._handle_response(response)
    
    def apply_for_postpaid(self, reason, agent_recommendation=False):
        """Apply for a postpaid card upgrade"""
        url = f"{api_config.CREDITS_API['postpaid_applications']}apply/"
        data = {
            'reason': reason,
            'agent_recommendation': agent_recommendation
        }
        
        response = requests.post(url, json=data, headers=self.get_headers())
        return self._handle_response(response)
    
    def agent_recommend_customer(self, customer_id, notes=None):
        """Create an agent recommendation for a customer"""
        url = f"{api_config.CREDITS_API['agent_recommendations']}recommend/"
        data = {
            'customer_id': customer_id
        }
        
        if notes:
            data['notes'] = notes
            
        response = requests.post(url, json=data, headers=self.get_headers())
        return self._handle_response(response)
    
    # Registration API methods
    def login(self, phoneNumber, password):
        """Login a user and get authentication token"""
        url = api_config.REGISTRATION_API['login']
        data = {
            'phoneNumber': phoneNumber,
            'password': password
        }
        
        response = requests.post(url, json=data, headers=api_config.DEFAULT_HEADERS)
        return self._handle_response(response)
    
    def register_customer(self, firstName, lastName, phoneNumber, email, password):
        """Register a new customer"""
        url = api_config.REGISTRATION_API['register']
        data = {
            'firstName': firstName,
            'lastName': lastName,
            'phoneNumber': phoneNumber,
            'email': email,
            'password': password
        }
        
        response = requests.post(url, json=data, headers=api_config.DEFAULT_HEADERS)
        return self._handle_response(response)
    
    def get_user_profile(self):
        """Get current user's profile"""
        url = api_config.REGISTRATION_API['profile']
        response = requests.get(url, headers=self.get_headers())
        return self._handle_response(response)
    
    def update_pin(self, pin):
        """Update PIN for user's NFC card"""
        url = api_config.REGISTRATION_API['update_pin']
        data = {'pin': pin}
        
        response = requests.post(url, json=data, headers=self.get_headers())
        return self._handle_response(response)
    
    def _handle_response(self, response):
        """Handle API response, parsing JSON and handling errors"""
        try:
            # Parse JSON response
            data = response.json()
            
            # Check if the request was successful
            if response.status_code >= 200 and response.status_code < 300:
                return {'success': True, 'data': data}
            else:
                return {'success': False, 'error': data, 'status': response.status_code}
                
        except json.JSONDecodeError:
            # Handle non-JSON responses
            return {
                'success': False, 
                'error': {'detail': response.text or 'No response content'}, 
                'status': response.status_code
            }
        except requests.RequestException as e:
            # Handle network errors
            return {'success': False, 'error': {'detail': str(e)}, 'status': 0}

# Create a default API client instance
api_client = KikapuAPI()

# Function to get a configured API client
def get_api_client(token=None, environment=None):
    """Get a configured API client instance"""
    return KikapuAPI(token=token, environment=environment)

# API Root View
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse

@api_view(['GET'])
def api_root(request, format=None):
    """
    API Root endpoint that provides links to all main API endpoints
    """
    return Response({
        'credits': {
            'nfc_cards': reverse('credits:nfc-card-list', request=request, format=format),
            'transactions': reverse('credits:transaction-list', request=request, format=format),
            'applications': reverse('credits:application-list', request=request, format=format),
        },
        'marketplace': {
            'products': reverse('marketplace:product-list', request=request, format=format),
            'categories': reverse('marketplace:category-list', request=request, format=format),
        },
        'registration': {
            'users': reverse('registration:user-list', request=request, format=format),
        },
        'market_research': {
            'surveys': reverse('market_research:survey-list', request=request, format=format),
        },
    })