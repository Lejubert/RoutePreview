#!/usr/bin/env python3
"""
Advanced API debugger - shows detailed error information
"""

import os
import sys
import requests
from dotenv import load_dotenv

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = ""
    class Style:
        BRIGHT = ""

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*70}")
print(f"{Fore.CYAN}{Style.BRIGHT}🔍 ADVANCED API DEBUGGER")
print(f"{Fore.CYAN}{Style.BRIGHT}{'='*70}\n")

# Check API key
print(f"{Fore.YELLOW}1. API Key Check:")
print(f"   Key: {GOOGLE_API_KEY[:20]}...{GOOGLE_API_KEY[-8:]}")
print(f"   Length: {len(GOOGLE_API_KEY)} characters")

# Test with maximum detail
print(f"\n{Fore.YELLOW}2. Testing Geocoding API with full error details...")

url = "https://maps.googleapis.com/maps/api/geocode/json"
params = {
    "address": "Times Square, New York",
    "key": GOOGLE_API_KEY
}

print(f"\n{Fore.CYAN}Request URL:")
print(f"   {url}")
print(f"\n{Fore.CYAN}Request Parameters:")
print(f"   address: {params['address']}")
print(f"   key: {GOOGLE_API_KEY[:12]}...{GOOGLE_API_KEY[-4:]}")

try:
    response = requests.get(url, params=params, timeout=10)
    
    print(f"\n{Fore.CYAN}Response Status Code: {response.status_code}")
    print(f"{Fore.CYAN}Response Headers:")
    for key, value in response.headers.items():
        if 'content' in key.lower() or 'type' in key.lower():
            print(f"   {key}: {value}")
    
    data = response.json()
    
    print(f"\n{Fore.CYAN}Full API Response:")
    print(f"{Fore.WHITE}{'-'*70}")
    import json
    print(json.dumps(data, indent=2))
    print(f"{Fore.WHITE}{'-'*70}")
    
    status = data.get("status")
    
    if status == "REQUEST_DENIED":
        print(f"\n{Fore.RED}{Style.BRIGHT}❌ REQUEST_DENIED - Here's why:\n")
        
        error_message = data.get("error_message", "")
        print(f"{Fore.YELLOW}Error Message:")
        print(f"   {error_message}\n")
        
        print(f"{Fore.YELLOW}{Style.BRIGHT}Common Causes & Fixes:\n")
        
        if "not authorized" in error_message.lower():
            print(f"{Fore.CYAN}1. ⚠️  API Not Enabled for This Project")
            print(f"   Solution:")
            print(f"   a) Go to: https://console.cloud.google.com/apis/dashboard")
            print(f"   b) Make sure you're in the CORRECT project (check top dropdown)")
            print(f"   c) Enable: Geocoding API, Directions API, Street View Static API")
            print(f"   d) Wait 2-3 minutes after enabling\n")
        
        if "api key" in error_message.lower():
            print(f"{Fore.CYAN}2. ⚠️  API Key Issues")
            print(f"   Solution:")
            print(f"   a) Go to: https://console.cloud.google.com/apis/credentials")
            print(f"   b) Click on your API key")
            print(f"   c) Check 'API restrictions' section:")
            print(f"      - If restricted, make sure Geocoding/Directions/Street View are selected")
            print(f"      - OR set to 'Don't restrict key' (less secure but good for testing)")
            print(f"   d) Check 'Application restrictions':")
            print(f"      - For testing, set to 'None'")
            print(f"      - Later you can restrict to specific IPs/domains")
            print(f"   e) Save and wait 2-3 minutes\n")
        
        print(f"{Fore.CYAN}3. ⚠️  Billing Not Linked to Project")
        print(f"   Solution:")
        print(f"   a) Go to: https://console.cloud.google.com/billing")
        print(f"   b) Click 'Link a billing account'")
        print(f"   c) Select your billing account")
        print(f"   d) Make sure it's linked to YOUR project\n")
        
        print(f"{Fore.CYAN}4. ⚠️  Wrong Project Selected")
        print(f"   Solution:")
        print(f"   a) Your API key belongs to a specific project")
        print(f"   b) Check which project your key is from:")
        print(f"      https://console.cloud.google.com/apis/credentials")
        print(f"   c) Make sure APIs are enabled in THAT SAME project\n")
        
    elif status == "OK":
        print(f"\n{Fore.GREEN}{Style.BRIGHT}✅ SUCCESS! API is working!")
        location = data["results"][0]["geometry"]["location"]
        print(f"   Coordinates: {location['lat']}, {location['lng']}")
        
    else:
        print(f"\n{Fore.RED}Status: {status}")
        print(f"Message: {data.get('error_message', 'No message')}")

except requests.exceptions.Timeout:
    print(f"\n{Fore.RED}❌ Request timed out")
except requests.exceptions.RequestException as e:
    print(f"\n{Fore.RED}❌ Request failed: {str(e)}")
except Exception as e:
    print(f"\n{Fore.RED}❌ Unexpected error: {str(e)}")

print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'='*70}")
print(f"{Fore.MAGENTA}{Style.BRIGHT}Next Steps:")
print(f"{Fore.MAGENTA}{Style.BRIGHT}{'='*70}\n")

print(f"{Fore.CYAN}If still failing after checking above:\n")
print(f"{Fore.YELLOW}1. Try creating a NEW API key:")
print(f"   https://console.cloud.google.com/apis/credentials")
print(f"   Click 'Create Credentials' → 'API Key'")
print(f"   Copy new key to .env file\n")

print(f"{Fore.YELLOW}2. Double-check project:")
print(f"   Look at the project dropdown in Google Cloud Console")
print(f"   Make sure APIs are enabled in the SAME project as your key\n")

print(f"{Fore.YELLOW}3. Wait 5 minutes:")
print(f"   Changes can take a few minutes to propagate\n")

print(f"{Fore.YELLOW}4. Check API key restrictions:")
print(f"   Go to your key in credentials")
print(f"   Set 'Application restrictions' to 'None'")
print(f"   Set 'API restrictions' to 'Don't restrict key' (for testing)\n")

