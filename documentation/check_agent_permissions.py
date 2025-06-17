#!/usr/bin/env python
"""
KIKAPU Agent Permissions Debug Script

This script tests both authentication and authorization for agent-specific endpoints.
It will help diagnose why an authenticated request might still get 403 Forbidden.
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
                print(f"{Colors.GREEN}✅ Login successful! Token received.{Colors.END}")
                return token
        
        print(f"{Colors.RED}✗ Login failed. No token received.{Colors.END}")
        return None
    except Exception as e:
        print(f"{Colors.RED}✗ Exception during login: {str(e)}{Colors.END}")
        return None

def check_user_info(token):
    """Check user profile to see if user is marked as an agent"""
    print_step("Checking User Profile")
    
    # We'll try to access the user profile to check agent status
    profile_url = f"{API_BASE_URL}/agent/profile/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {token}"
    }
    
    print_request("GET", profile_url, headers)
    
    try:
        response = requests.get(profile_url, headers=headers)
        print_response(response)
        
        if response.status_code == 200:
            print(f"{Colors.GREEN}✅ Successfully retrieved user profile.{Colors.END}")
            
            # Check if the response indicates the user is an agent
            data = response.json()
            if data.get('user_type') == 'AGENT' or data.get('is_agent') == True:
                print(f"{Colors.GREEN}✅ User is correctly marked as an agent in the system.{Colors.END}")
            else:
                print(f"{Colors.RED}✗ User is NOT marked as an agent in the system. This is likely why you're getting 403 errors.{Colors.END}")
                
            return data
        else:
            print(f"{Colors.RED}✗ Failed to retrieve user profile. Status code: {response.status_code}{Colors.END}")
            return None
    except Exception as e:
        print(f"{Colors.RED}✗ Exception while checking profile: {str(e)}{Colors.END}")
        return None

def test_market_price_submission(token):
    """Test submitting market price data"""
    print_step("Testing Market Price Submission")
    
    url = f"{API_BASE_URL}/market_research/price/submit/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {token}"
    }
    
    payload = {
        "source_type": "market",
        "source_name": "Test Market",
        "product_name": "Test Product",
        "price": 1000,
        "quantity": 1,
        "unit": "kg",
        "region": "Test Region"
    }
    
    print_request("POST", url, headers, payload)
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print_response(response)
        
        if response.status_code < 400:
            print(f"{Colors.GREEN}✅ Market price submission successful!{Colors.END}")
        elif response.status_code == 403:
            print(f"{Colors.RED}✗ Forbidden (403) error. The server understood who you are (authentication worked), "
                 f"but you don't have permission to submit market prices.{Colors.END}")
            
            # Try to parse the error message
            try:
                error_msg = response.json().get('error', 'No error message provided')
                print(f"{Colors.YELLOW}⚠️ Server error message: {error_msg}{Colors.END}")
                
                if "Only authorized agents" in error_msg:
                    print(f"{Colors.YELLOW}⚠️ The system doesn't recognize you as an agent. This is an authorization issue, not an authentication issue.{Colors.END}")
            except:
                pass
        elif response.status_code == 401:
            print(f"{Colors.RED}✗ Unauthorized (401) error. Your authentication token was rejected.{Colors.END}")
        else:
            print(f"{Colors.RED}✗ Request failed with status code {response.status_code}.{Colors.END}")
        
        return response.status_code < 400
    except Exception as e:
        print(f"{Colors.RED}✗ Exception during market price submission: {str(e)}{Colors.END}")
        return False

def main():
    """Main function to run the tests"""
    print(f"{Colors.BOLD}KIKAPU Agent Permissions Debug{Colors.END}")
    print("This script will check if your authentication and agent permissions are working correctly")
    
    # Step 1: Login to get token
    token = login()
    if not token:
        print(f"{Colors.RED}Failed to get authentication token. Please check your credentials.{Colors.END}")
        sys.exit(1)
    
    # Step 2: Check user profile for agent status
    user_data = check_user_info(token)
    
    # Step 3: Test market price submission
    submission_result = test_market_price_submission(token)
    
    # Summary
    print_step("Summary")
    print(f"1. Login authentication: {'✅ Success' if token else '❌ Failed'}")
    print(f"2. User profile check: {'✅ Success' if user_data else '❌ Failed'}")
    print(f"3. Market price submission: {'✅ Success' if submission_result else '❌ Failed'}")
    
    if not submission_result:
        print(f"\n{Colors.YELLOW}Likely issue:{Colors.END}")
        if not token:
            print("- Authentication is failing during login. Check credentials.")
        elif not user_data:
            print("- User profile couldn't be retrieved. Your token might not be valid.")
        else:
            print("- Your user account is authenticated but not properly set up as an agent.")
            print("- Check that your user has a proper agent profile and the 'is_agent' attribute.")
            print("- Contact your administrator to verify your agent account is properly configured.")

if __name__ == "__main__":
    main()
