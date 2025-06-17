#!/usr/bin/env python
"""
KIKAPU Authentication Test Script

This script tests authentication with the KIKAPU API by:
1. Logging in to get an auth token
2. Making authenticated requests with the token
3. Providing detailed debugging output

Usage:
    python auth_test.py
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
                print(f"{Colors.GREEN}✓ Login successful! Token received.{Colors.END}")
                return token
        
        print(f"{Colors.RED}✗ Login failed. No token received.{Colors.END}")
        return None
    except Exception as e:
        print(f"{Colors.RED}✗ Exception during login: {str(e)}{Colors.END}")
        return None

def test_token_auth(token):
    """Test token authentication with various header formats"""
    print_step("Testing Token Authentication")
    
    # Target endpoint requiring authentication
    url = f"{API_BASE_URL}/market_research/markets/"
    
    # Test different header formats
    auth_headers = [
        {"Authorization": f"Token {token}"},
        {"Authorization": f"Bearer {token}"},
        {"Authorization": token},
        {"Token": token},
        {"Authentication": f"Token {token}"}
    ]
    
    header_results = []
    
    for i, headers in enumerate(auth_headers, 1):
        headers["Content-Type"] = "application/json"
        
        print(f"\n{Colors.YELLOW}Test {i}:{Colors.END}")
        print_request("GET", url, headers)
        
        try:
            response = requests.get(url, headers=headers)
            print_response(response)
            
            success = response.status_code < 400
            result = {
                "headers": headers,
                "success": success,
                "status_code": response.status_code
            }
            header_results.append(result)
            
            status_str = f"{Colors.GREEN}✓ Success" if success else f"{Colors.RED}✗ Failed"
            print(f"{status_str} (Status: {response.status_code}){Colors.END}")
            
        except Exception as e:
            print(f"{Colors.RED}✗ Exception: {str(e)}{Colors.END}")
    
    # Find which header format worked
    working_formats = [r for r in header_results if r["success"]]
    if working_formats:
        print(f"\n{Colors.GREEN}{Colors.BOLD}Working Authentication Format(s):{Colors.END}")
        for fmt in working_formats:
            print(f"  Status {fmt['status_code']}: {fmt['headers']['Authorization']}")
        
        # Return the first working format
        return working_formats[0]["headers"]
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}No authentication format worked.{Colors.END}")
        return None

def submit_market_price(auth_headers):
    """Test submitting market price data"""
    print_step("Submitting Market Price Data")
    
    url = f"{API_BASE_URL}/market_research/price/submit/"
    payload = {
        "market": 1,  # Replace with valid market ID
        "commodity": 1,  # Replace with valid commodity ID
        "price": 500.0,
        "quantity": 1.0,
        "latitude": -6.7924,
        "longitude": 39.2083,
    }
    
    print_request("POST", url, auth_headers, payload)
    
    try:
        response = requests.post(url, headers=auth_headers, json=payload)
        print_response(response)
        
        if response.status_code < 400:
            print(f"{Colors.GREEN}✓ Market price submitted successfully!{Colors.END}")
            return True
        else:
            print(f"{Colors.RED}✗ Market price submission failed.{Colors.END}")
            return False
    except Exception as e:
        print(f"{Colors.RED}✗ Exception during submission: {str(e)}{Colors.END}")
        return False

def main():
    """Run the authentication test sequence"""
    print(f"{Colors.BOLD}KIKAPU API Authentication Test{Colors.END}")
    print("=" * 60)
    
    # Step 1: Login
    token = login()
    if not token:
        print(f"{Colors.RED}Cannot proceed without authentication token.{Colors.END}")
        sys.exit(1)
    
    # Step 2: Test different auth header formats
    working_headers = test_token_auth(token)
    if not working_headers:
        print(f"{Colors.RED}Failed to authenticate with any header format. Check server logs.{Colors.END}")
        sys.exit(1)
    
    # Step 3: Try to submit market price data
    success = submit_market_price(working_headers)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"{Colors.BOLD}Test Summary:{Colors.END}")
    print(f"Login: {'✓' if token else '✗'}")
    print(f"Authentication: {'✓' if working_headers else '✗'}")
    print(f"Market Price Submission: {'✓' if success else '✗'}")
    
    if success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed! The correct header format is:{Colors.END}")
        print(f"  {working_headers['Authorization']}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}Some tests failed.{Colors.END}")
        print("Check the server logs for more information.")

if __name__ == "__main__":
    main()
