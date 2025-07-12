#!/usr/bin/env python3
"""
Debug script to check all registered routes in the Flask app
"""

import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def debug_routes():
    """Debug all registered routes"""
    
    # Set environment to development
    os.environ['FLASK_ENV'] = 'development'
    
    try:
        from app import create_app
        
        app = create_app()
        
        with app.app_context():
            print("🔧 Flask Application Routes Debug")
            print("=" * 60)
            
            # Get all registered routes
            routes = []
            for rule in app.url_map.iter_rules():
                methods = ', '.join(rule.methods - {'HEAD', 'OPTIONS'})
                routes.append((rule.endpoint, methods, rule.rule))
            
            # Sort routes by endpoint
            routes.sort()
            
            print(f"📊 Total routes found: {len(routes)}")
            print("\n📋 All registered routes:")
            print("-" * 60)
            
            auth_routes = []
            other_routes = []
            
            for endpoint, methods, rule in routes:
                if endpoint.startswith('auth.'):
                    auth_routes.append((endpoint, methods, rule))
                else:
                    other_routes.append((endpoint, methods, rule))
                    
            print("\n🔐 AUTH ROUTES:")
            print("-" * 30)
            for endpoint, methods, rule in auth_routes:
                print(f"  {endpoint:<30} {methods:<15} {rule}")
            
            print(f"\n📱 OTHER ROUTES ({len(other_routes)} total):")
            print("-" * 30)
            for endpoint, methods, rule in other_routes[:20]:  # Show first 20
                print(f"  {endpoint:<30} {methods:<15} {rule}")
            
            if len(other_routes) > 20:
                print(f"  ... and {len(other_routes) - 20} more routes")
            
            # Check specifically for the verify_email route
            print("\n🔍 VERIFICATION ROUTE CHECK:")
            print("-" * 30)
            verify_route = next((r for r in auth_routes if 'verify_email' in r[0]), None)
            if verify_route:
                print(f"✅ Found verify_email route: {verify_route[2]}")
            else:
                print("❌ verify_email route NOT FOUND!")
            
            # Check blueprint registrations
            print("\n🔧 BLUEPRINT REGISTRATIONS:")
            print("-" * 30)
            for name, blueprint in app.blueprints.items():
                print(f"  {name}: {blueprint.url_prefix or '/'}")
            
            # Test route generation
            print("\n🌐 URL GENERATION TEST:")
            print("-" * 30)
            try:
                from flask import url_for
                auth_login_url = url_for('auth.login')
                print(f"✅ auth.login URL: {auth_login_url}")
                
                # Try to generate verify_email URL
                try:
                    verify_url = url_for('auth.verify_email', token='test-token')
                    print(f"✅ auth.verify_email URL: {verify_url}")
                except Exception as e:
                    print(f"❌ auth.verify_email URL generation failed: {e}")
                    
            except Exception as e:
                print(f"❌ URL generation error: {e}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_routes() 