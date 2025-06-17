#!/usr/bin/env python
"""
KIKAPU Authentication Format Test Script

This script tests different authentication header formats with the KIKAPU API to identify
exactly which format works and which one doesn't. It will try:

1. No auth header
2. Authorization: Bearer <token>
3. Authorization: Token <token>
4. Token: <token>
5. Auth: <token>

Usage:
    python test_auth_formats.py
"""

import requests
import json
import sys

# Configuration - UPDATE THESE VALUES
API_BASE_URL = "http://localhost:8000/api"  # Update with your API URL
PHONE_NUMBER = "+255742178726"  # Replace with a valid agent phone number
PASSWORD = "agent-password"  # Replace with the agent's password

# ANSI color codes for output formatting
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_step(step):
    """Print a step heading"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}=== {step} ==={Colors.END}")

def print_request(method, url, headers=None, data=None):
    """Print request details"""
    print(f"{Colors.BOLD}Request:{Colors.END} {method} {url}")
    
    if headers:
        print(f"{Colors.BOLD}Headers:{Colors.END}")
        for key, value in headers.items():
            # Hide most of the token value for security
            if key.lower() == 'authorization' and len(value) > 15:
                print(f"  {key}: {value[:10]}...{value[-5:]}")
            else:
                print(f"  {key}: {value}")
    
    if data:
        print(f"{Colors.BOLD}Data:{Colors.END}")
        print(f"  {json.dumps(data, indent=2)}")

def print_response(response):
    """Print response details"""
    try:
        json_response = response.json()
        response_text = json.dumps(json_response, indent=2)
    except:
        response_text = response.text if response.text else "[No response body]"
    
    status_color = Colors.GREEN if response.status_code < 400 else Colors.RED
    
    print(f"{Colors.BOLD}Response:{Colors.END} [{status_color}{response.status_code}{Colors.END}] {response.reason}")
    print(f"{Colors.BOLD}Response Body:{Colors.END}")
    print(f"{response_text}")

def print_result(success, message):
    """Print test result"""
    if success:
        print(f"\n{Colors.GREEN}✅ {message}{Colors.END}")
    else:
        print(f"\n{Colors.RED}❌ {message}{Colors.END}")

def login():
    """Log in and get auth token"""
    print_step("Agent Login")
    
    login_url = f"{API_BASE_URL}/agent/login/"
    headers = {"Content-Type": "application/json"}
    payload = {
        "phoneNumber": PHONE_NUMBER,
        "password": PASSWORD
    }
    
    print_request("POST", login_url, headers, payload)
    
    try:
        response = requests.post(login_url, headers=headers, json=payload)
        print_response(response)
        
        if response.status_code == 200 and response.json().get('success') == True:
            token = response.json().get('token')
            if token:
                print(f"{Colors.GREEN}✅ Login successful! Token received.{Colors.END}")
                return token
        
        print(f"{Colors.RED}✗ Login failed. No token received.{Colors.END}")
        return None
    except Exception as e:
        print(f"{Colors.RED}✗ Exception during login: {str(e)}{Colors.END}")
        return None

def test_auth_format(token, auth_header, description):
    """Test a specific authentication header format"""
    print_step(f"Testing {description}")
    
    # Test endpoint for authenticated requests
    test_url = f"{API_BASE_URL}/market_research/price/submit/"
    
    # Set up headers
    headers = {"Content-Type": "application/json"}
    if auth_header:
        headers.update(auth_header)
    
    # Sample price data for testing
    payload = {
        "source_type": "market",
        "source_name": "Test Market",
        "product_name": "Test Product",
        "price": 1000,
        "quantity": 1,
        "unit": "kg",
        "region": "Test Region"
    }
    
    print_request("POST", test_url, headers, payload)
    
    # Make the request
    try:
        response = requests.post(test_url, headers=headers, json=payload)
        print_response(response)
        
        success = response.status_code < 400
        message = f"{description}: {'Success!' if success else 'Failed'}"
        print_result(success, message)
        
        return success
        
    except Exception as e:
        print(f"{Colors.RED}✗ Exception during request: {str(e)}{Colors.END}")
        print_result(False, description)
        return False

def main():
    """Main function to run tests"""
    print(f"{Colors.BOLD}KIKAPU Authentication Format Test{Colors.END}")
    print("This script will test different authentication header formats")
    print("to identify which one works with the KIKAPU API.\n")
    
    # Login to get token
    token = login()
    if not token:
        print("Cannot proceed with tests without a valid token. Please check your credentials.")
        sys.exit(1)
    
    print(f"\n{Colors.YELLOW}Token received: {token[:5]}...{token[-5:]}{Colors.END}")
    print(f"{Colors.YELLOW}Now testing different authentication header formats...{Colors.END}")
    
    # Test various auth header formats
    results = []
    
    # Test 1: No auth header
    results.append((
        "No authentication header",
        test_auth_format(token, None, "No authentication header")
    ))
    
    # Test 2: Bearer token (common but incorrect for DRF TokenAuthentication)
    results.append((
        "Authorization: Bearer <token>",
        test_auth_format(token, {"Authorization": f"Bearer {token}"}, "Bearer token")
    ))
    
    # Test 3: Token token (correct for DRF TokenAuthentication)
    results.append((
        "Authorization: Token <token>",
        test_auth_format(token, {"Authorization": f"Token {token}"}, "Token token")
    ))
    
    # Test 4: Token header (incorrect)
    results.append((
        "Token: <token>",
        test_auth_format(token, {"Token": token}, "Token header")
    ))
    
    # Test 5: Auth header (incorrect)
    results.append((
        "Auth: <token>",
        test_auth_format(token, {"Auth": token}, "Auth header")
    ))
    
    # Test 6: Raw token (incorrect)
    results.append((
        "Authorization: <token>",
        test_auth_format(token, {"Authorization": token}, "Raw token")
    ))
    
    # Summary
    print_step("Test Results Summary")
    
    for description, success in results:
        if success:
            print(f"{Colors.GREEN}✅ WORKS: {description}{Colors.END}")
        else:
            print(f"{Colors.RED}❌ FAILS: {description}{Colors.END}")
    
    print("\nBased on these results, use the working format in your mobile app.")
    
    # Find the working format(s)
    working_formats = [desc for desc, success in results if success]
    if working_formats:
        print(f"\n{Colors.GREEN}Use this format in your mobile app:{Colors.END}")
        for format in working_formats:
            print(f"{Colors.BOLD}{format}{Colors.END}")
    else:
        print(f"\n{Colors.RED}No authentication format worked. Please check your server configuration.{Colors.END}")

if __name__ == "__main__":
    main()
