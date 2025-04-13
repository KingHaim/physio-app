#!/usr/bin/env python3
import os
import requests
import json
import sys
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

def get_api_key():
    """Get the DeepSeek API key from various sources."""
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
    
    return api_key

def test_api_key(api_key):
    """Test if a DeepSeek API key is valid and return the working endpoint."""
    # Define possible API endpoints to try
    api_endpoints = [
        "https://api.deepseek.com/v1/chat/completions",  # Primary endpoint
        "https://api.deepseek.ai/v1/chat/completions",   # Alternative domain
        "https://api.deepseek.com/v1/completions",       # Alternative endpoint
        "https://api.deepseek.chat/v1/chat/completions"  # Another possible domain
    ]
    
    test_prompt = "Hello, respond with a very short greeting."
    
    for endpoint in api_endpoints:
        print(f"Testing endpoint: {endpoint}")
        
        try:
            # Construct the payload
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": test_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 20
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
            
            print(f"Status code: {response.status_code}")
            
            # Check if the request was successful
            if response.status_code == 200:
                result = response.json()
                message = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                print(f"API responded: {message}")
                return True, endpoint
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Exception: {str(e)}")
    
    return False, None

def update_env_file(api_key, working_endpoint):
    """Update the .env file with the API key and working endpoint."""
    try:
        # Make a backup of the current .env file
        try:
            with open('.env', 'r') as src:
                with open(f'.env.backup-{int(datetime.now().timestamp())}', 'w') as dst:
                    dst.write(src.read())
        except FileNotFoundError:
            pass
        
        # Check if .env file exists
        try:
            with open('.env', 'r') as file:
                env_contents = file.read()
        except FileNotFoundError:
            env_contents = ""
        
        # Update DEEPSEEK_API_KEY if present, otherwise add it
        if 'DEEPSEEK_API_KEY=' in env_contents:
            lines = env_contents.splitlines()
            for i, line in enumerate(lines):
                if line.startswith('DEEPSEEK_API_KEY='):
                    lines[i] = f'DEEPSEEK_API_KEY={api_key}'
                    break
            env_contents = '\n'.join(lines)
        else:
            env_contents += f'\nDEEPSEEK_API_KEY={api_key}'
        
        # Add DEEPSEEK_API_ENDPOINT if not present
        if 'DEEPSEEK_API_ENDPOINT=' not in env_contents:
            env_contents += f'\nDEEPSEEK_API_ENDPOINT={working_endpoint}'
        else:
            lines = env_contents.splitlines()
            for i, line in enumerate(lines):
                if line.startswith('DEEPSEEK_API_ENDPOINT='):
                    lines[i] = f'DEEPSEEK_API_ENDPOINT={working_endpoint}'
                    break
            env_contents = '\n'.join(lines)
        
        # Write updated content back to .env file
        with open('.env', 'w') as file:
            file.write(env_contents)
        
        print(f"✅ Updated .env file with API key and endpoint ({working_endpoint})")
        return True
    except Exception as e:
        print(f"❌ Error updating .env file: {str(e)}")
        return False

def main():
    """Main function to update the DeepSeek API integration."""
    print("DeepSeek API Integration Update Tool")
    print("===================================")
    
    # Get the API key
    api_key = get_api_key()
    if not api_key:
        print("❌ No API key found. Please provide a valid DeepSeek API key.")
        new_key = input("Enter your DeepSeek API key (starts with 'sk-'): ")
        if new_key.startswith('sk-'):
            api_key = new_key
        else:
            print("❌ Invalid API key format. API key should start with 'sk-'.")
            return
    
    # Test the API key
    print(f"\nTesting API key: {api_key[:8]}...")
    success, working_endpoint = test_api_key(api_key)
    
    if success:
        print(f"\n✅ API key is valid! Working endpoint: {working_endpoint}")
        
        # Update the .env file
        if update_env_file(api_key, working_endpoint):
            print("\n✅ DeepSeek API integration updated successfully!")
            print("\nNext steps:")
            print("1. Restart your Flask application to apply the changes")
            print("2. Try generating a report to test the integration")
            
            # Create a helper script to export and run
            with open('run_with_api_key.sh', 'w') as file:
                file.write(f"""#!/bin/bash
export DEEPSEEK_API_KEY="{api_key}"
export DEEPSEEK_API_ENDPOINT="{working_endpoint}"
echo "Exported environment variables. You can now run your Flask application."
echo "Example: flask run"
""")
            os.chmod('run_with_api_key.sh', 0o755)
            print("\nA helper script 'run_with_api_key.sh' has been created.")
            print("You can run it with 'source run_with_api_key.sh' to export the environment variables.")
    else:
        print("\n❌ API key validation failed.")
        print("\nPossible solutions:")
        print("1. Make sure you're using a valid DeepSeek API key")
        print("2. Check if your API key has been rotated or expired")
        print("3. Ensure you have sufficient credits in your DeepSeek account")
        print("4. Try generating a new API key from the DeepSeek dashboard")

if __name__ == "__main__":
    main() 