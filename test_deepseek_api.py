#!/usr/bin/env python3
import os
import requests
import json
import sys
from dotenv import load_dotenv

def test_api_key(api_key, verbose=True):
    """Test if a DeepSeek API key is valid by making a simple request."""
    
    # Define possible API endpoints to try
    api_endpoints = [
        "https://api.deepseek.com/v1/chat/completions",  # Primary endpoint
        "https://api.deepseek.ai/v1/chat/completions",   # Alternative domain
        "https://api.deepseek.com/v1/completions",       # Alternative endpoint
        "https://api.deepseek.chat/v1/chat/completions"  # Another possible domain
    ]
    
    # A simple prompt for testing
    test_prompt = "Hello, can you respond with a short greeting to confirm the API is working?"
    
    for endpoint in api_endpoints:
        if verbose:
            print(f"\nTesting endpoint: {endpoint}")
            print(f"Using API key: {api_key[:8]}..." if api_key else "No API key provided")
        
        try:
            # Construct the payload
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": test_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 50
            }
            
            # Make the request
            response = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )
            
            if verbose:
                print(f"Status code: {response.status_code}")
            
            # Check if the request was successful
            if response.status_code == 200:
                result = response.json()
                message = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                if verbose:
                    print(f"API responded: {message}")
                print(f"\n✅ SUCCESS with endpoint {endpoint}")
                return True, endpoint
            else:
                if verbose:
                    print(f"Error: {response.text}")
        except Exception as e:
            if verbose:
                print(f"Exception: {str(e)}")
    
    print("\n❌ All endpoints failed")
    return False, None

def main():
    """Main function to test the DeepSeek API key."""
    # Load environment variables
    load_dotenv()
    
    # Try to get API key from environment first
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    
    # If not in environment, try to read from .env file
    if not api_key:
        try:
            with open('.env', 'r') as file:
                for line in file:
                    if line.startswith('DEEPSEEK_API_KEY='):
                        api_key = line.strip().split('=', 1)[1]
                        # Remove quotes if present
                        api_key = api_key.strip('"\'')
                        break
        except FileNotFoundError:
            pass
    
    # If still no API key, check for a .env.new file
    if not api_key:
        try:
            with open('.env.new', 'r') as file:
                for line in file:
                    if line.startswith('DEEPSEEK_API_KEY='):
                        api_key = line.strip().split('=', 1)[1]
                        # Remove quotes if present
                        api_key = api_key.strip('"\'')
                        break
        except FileNotFoundError:
            pass
    
    # Allow passing API key as command line argument
    if len(sys.argv) > 1 and sys.argv[1].startswith('sk-'):
        api_key = sys.argv[1]
    
    if not api_key:
        print("❌ No API key found. Please provide an API key as an argument or set the DEEPSEEK_API_KEY environment variable.")
        return
    
    print(f"Testing DeepSeek API connection with key: {api_key[:8]}...")
    success, endpoint = test_api_key(api_key)
    
    if success:
        print(f"\nAPI key is valid! Use this endpoint: {endpoint}")
        # Store the working endpoint in a file for future reference
        with open('working_endpoint.txt', 'w') as file:
            file.write(endpoint)
    else:
        print("\nAPI key validation failed. Please check if your key is correct and try again.")
        print("\nTips to resolve API key issues:")
        print("1. Ensure there are no extra spaces or newlines in your API key")
        print("2. Check if your API key has been rotated or expired")
        print("3. Verify you're using the correct API endpoint for your account")
        print("4. Try generating a new API key from your DeepSeek account")

if __name__ == "__main__":
    main() 