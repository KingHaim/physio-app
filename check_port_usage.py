#!/usr/bin/env python3
"""
Script to check port usage and provide solutions for freeing up port 5000
"""

import os
import sys
import socket
import subprocess

def check_port_usage(port=5000):
    """Check if a port is in use and try to identify what's using it"""
    
    print(f"🔍 Checking port {port} usage...")
    
    # Try to connect to the port
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            print(f"❌ Port {port} is IN USE")
            
            # Try to identify what's using it on macOS
            try:
                result = subprocess.run(['lsof', '-i', f':{port}'], 
                                      capture_output=True, text=True)
                if result.stdout:
                    print(f"\n📊 Process using port {port}:")
                    print(result.stdout)
                else:
                    print(f"\n❓ Could not identify process using port {port}")
            except:
                print(f"\n❓ Could not check process using port {port}")
            
            return False
        else:
            print(f"✅ Port {port} is FREE")
            return True
    except Exception as e:
        print(f"❌ Error checking port {port}: {e}")
        return False

def find_free_ports(start_port=5001, count=5):
    """Find multiple free ports"""
    
    print(f"\n🔍 Finding {count} free ports starting from {start_port}...")
    free_ports = []
    
    for port in range(start_port, start_port + 100):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            
            if result != 0:  # Port is free
                free_ports.append(port)
                if len(free_ports) >= count:
                    break
        except:
            continue
    
    if free_ports:
        print(f"✅ Free ports found: {', '.join(map(str, free_ports))}")
    else:
        print("❌ No free ports found")
    
    return free_ports

def provide_solutions():
    """Provide solutions for port 5000 being in use"""
    
    print("\n🔧 SOLUTIONS FOR PORT 5000 IN USE:")
    print("=" * 50)
    
    print("\n1. 🍎 DISABLE AIRPLAY RECEIVER (macOS):")
    print("   - Open System Preferences/Settings")
    print("   - Go to Sharing")
    print("   - Uncheck 'AirPlay Receiver'")
    print("   - This will free up port 5000")
    
    print("\n2. 🔀 USE A DIFFERENT PORT:")
    print("   - Run: python3 local_server_test.py")
    print("   - The script will automatically find a free port")
    
    print("\n3. 🛑 KILL PROCESS USING PORT 5000:")
    print("   - Find the process: lsof -i :5000")
    print("   - Kill it: kill -9 <PID>")
    print("   - ⚠️  Be careful not to kill system processes")
    
    print("\n4. 📱 ALTERNATIVE COMMANDS:")
    print("   - Check what's using port 5000:")
    print("     sudo lsof -i :5000")
    print("   - Kill all processes on port 5000:")
    print("     sudo kill -9 $(lsof -t -i:5000)")

def main():
    """Main function"""
    
    print("🚀 PORT USAGE CHECKER")
    print("=" * 40)
    
    # Check port 5000
    port_5000_free = check_port_usage(5000)
    
    if not port_5000_free:
        # Find alternative ports
        free_ports = find_free_ports()
        
        # Provide solutions
        provide_solutions()
        
        if free_ports:
            print(f"\n🎯 RECOMMENDED ACTION:")
            print(f"   Use port {free_ports[0]} by running:")
            print(f"   python3 local_server_test.py")
            print(f"   (It will automatically use port {free_ports[0]})")
    else:
        print("\n🎉 Port 5000 is free! You can use it.")
    
    print("\n" + "=" * 40)
    print("🏃‍♂️ NEXT STEPS:")
    print("   Run: python3 local_server_test.py")
    print("   (It will automatically find and use a free port)")

if __name__ == "__main__":
    main() 