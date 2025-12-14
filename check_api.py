#!/usr/bin/env python3
"""
Quick API checker to verify Google Maps APIs are working
Run this AFTER enabling APIs in Google Cloud Console
"""

import os
import sys
import requests
from dotenv import load_dotenv

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    # Fallback without colors
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = ""
    class Style:
        BRIGHT = ""

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def print_header(text):
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'='*60}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}{text}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}{'='*60}\n")

def check_api_key():
    """Check if API key is set"""
    print(f"{Fore.CYAN}Checking API Key...")
    
    if not GOOGLE_API_KEY:
        print(f"{Fore.RED}❌ GOOGLE_API_KEY not found in .env file")
        print(f"{Fore.YELLOW}\nCreate a .env file with:")
        print(f"{Fore.YELLOW}GOOGLE_API_KEY=your_key_here\n")
        return False
    
    if GOOGLE_API_KEY == "your_api_key_here" or len(GOOGLE_API_KEY) < 20:
        print(f"{Fore.RED}❌ API key looks invalid or is placeholder")
        return False
    
    print(f"{Fore.GREEN}✅ API key found: {GOOGLE_API_KEY[:12]}...{GOOGLE_API_KEY[-4:]}")
    return True

def test_geocoding_api():
    """Test Geocoding API"""
    print(f"\n{Fore.CYAN}Testing Geocoding API...")
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": "Times Square, New York", "key": GOOGLE_API_KEY}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        status = data.get("status")
        
        if status == "OK":
            print(f"{Fore.GREEN}✅ Geocoding API is WORKING!")
            location = data["results"][0]["geometry"]["location"]
            print(f"   Test: Times Square → {location['lat']:.6f}, {location['lng']:.6f}")
            return True
        elif status == "REQUEST_DENIED":
            print(f"{Fore.RED}❌ Geocoding API: REQUEST_DENIED")
            error_msg = data.get("error_message", "")
            print(f"{Fore.YELLOW}   {error_msg}")
            print(f"{Fore.YELLOW}\n   ➜ Action: Enable 'Geocoding API' at:")
            print(f"{Fore.CYAN}   https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com\n")
            return False
        else:
            print(f"{Fore.RED}❌ Status: {status}")
            if "error_message" in data:
                print(f"   {data['error_message']}")
            return False
    except Exception as e:
        print(f"{Fore.RED}❌ Exception: {str(e)}")
        return False

def test_directions_api():
    """Test Directions API"""
    print(f"\n{Fore.CYAN}Testing Directions API...")
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": "Times Square, New York",
        "destination": "Central Park, New York",
        "key": GOOGLE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        status = data.get("status")
        
        if status == "OK":
            print(f"{Fore.GREEN}✅ Directions API is WORKING!")
            distance = data["routes"][0]["legs"][0]["distance"]["text"]
            duration = data["routes"][0]["legs"][0]["duration"]["text"]
            print(f"   Test route: {distance} ({duration})")
            return True
        elif status == "REQUEST_DENIED":
            print(f"{Fore.RED}❌ Directions API: REQUEST_DENIED")
            error_msg = data.get("error_message", "")
            print(f"{Fore.YELLOW}   {error_msg}")
            print(f"{Fore.YELLOW}\n   ➜ Action: Enable 'Directions API' at:")
            print(f"{Fore.CYAN}   https://console.cloud.google.com/apis/library/directions-backend.googleapis.com\n")
            return False
        else:
            print(f"{Fore.RED}❌ Status: {status}")
            if "error_message" in data:
                print(f"   {data['error_message']}")
            return False
    except Exception as e:
        print(f"{Fore.RED}❌ Exception: {str(e)}")
        return False

def test_streetview_api():
    """Test Street View Static API"""
    print(f"\n{Fore.CYAN}Testing Street View Static API...")
    
    # Test metadata first
    url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    params = {"location": "Times Square, New York", "key": GOOGLE_API_KEY}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        status = data.get("status")
        
        if status == "OK":
            print(f"{Fore.GREEN}✅ Street View Static API is WORKING!")
            pano_id = data.get("pano_id", "N/A")
            print(f"   Panorama ID: {pano_id[:20]}...")
            return True
        elif status == "REQUEST_DENIED":
            print(f"{Fore.RED}❌ Street View Static API: REQUEST_DENIED")
            print(f"{Fore.YELLOW}\n   ➜ Action: Enable 'Street View Static API' at:")
            print(f"{Fore.CYAN}   https://console.cloud.google.com/apis/library/street-view-image-backend.googleapis.com\n")
            return False
        elif status == "ZERO_RESULTS":
            print(f"{Fore.YELLOW}⚠️  No Street View at test location (this is OK)")
            print(f"{Fore.GREEN}   But API is working!")
            return True
        else:
            print(f"{Fore.YELLOW}⚠️  Status: {status}")
            # Try actual image fetch
            img_url = "https://maps.googleapis.com/maps/api/streetview"
            img_resp = requests.get(img_url, params=params, timeout=10)
            if img_resp.status_code == 200:
                print(f"{Fore.GREEN}✅ Street View image fetch works!")
                return True
            return False
    except Exception as e:
        print(f"{Fore.RED}❌ Exception: {str(e)}")
        return False

def main():
    print_header("🔍 Google Maps API Checker")
    
    # Check API key first
    if not check_api_key():
        sys.exit(1)
    
    # Test all APIs
    results = [
        ("Geocoding API", test_geocoding_api()),
        ("Directions API", test_directions_api()),
        ("Street View Static API", test_streetview_api())
    ]
    
    # Summary
    print_header("📊 Results Summary")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for api_name, success in results:
        icon = f"{Fore.GREEN}✅" if success else f"{Fore.RED}❌"
        print(f"  {icon} {api_name}")
    
    print(f"\n{Fore.CYAN}Result: {passed}/{total} APIs working")
    
    if passed == total:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}🎉 SUCCESS! All APIs are enabled!")
        print(f"{Fore.GREEN}You can now run: {Fore.CYAN}streamlit run app.py\n")
        return 0
    else:
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}⚠️  Please enable the failing APIs above")
        print(f"{Fore.YELLOW}Follow the links to enable each one in Google Cloud Console")
        print(f"{Fore.YELLOW}Then run this script again to verify.\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())

