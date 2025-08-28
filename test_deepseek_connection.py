#!/usr/bin/env python3
"""
Script para diagnosticar problemas de conexión con DeepSeek API
"""

import requests
import time
import os
from app import create_app

def test_deepseek_endpoints():
    """Test múltiples endpoints de DeepSeek"""
    
    app = create_app()
    
    with app.app_context():
        # Get API key
        api_key = app.config.get('DEEPSEEK_API_KEY')
        if not api_key:
            print("❌ DEEPSEEK_API_KEY no configurada")
            return
        
        print(f"🔑 API Key encontrada: {api_key[:10]}...{api_key[-4:]}")
        
        # Test endpoints
        endpoints = [
            "https://api.deepseek.com/v1/chat/completions",
            "https://api.deepseek.ai/v1/chat/completions",
            "https://api.deepseek.com/chat/completions"
        ]
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'user', 'content': 'Test message'}
            ],
            'max_tokens': 50
        }
        
        print("\n🧪 Probando endpoints de DeepSeek:")
        print("=" * 60)
        
        for i, endpoint in enumerate(endpoints, 1):
            print(f"\n{i}. Probando: {endpoint}")
            
            try:
                start_time = time.time()
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                elapsed = time.time() - start_time
                
                print(f"   ⏱️  Tiempo: {elapsed:.2f}s")
                print(f"   📡 Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"   ✅ SUCCESS - Endpoint funciona correctamente")
                    
                    # Save working endpoint
                    try:
                        with open('.deepseek_working_endpoint', 'w') as f:
                            f.write(endpoint)
                        print(f"   💾 Endpoint guardado como funcional")
                    except Exception as e:
                        print(f"   ⚠️  No se pudo guardar endpoint: {e}")
                        
                    return endpoint
                    
                else:
                    print(f"   ❌ FAILED - {response.text[:200]}")
                    
            except requests.exceptions.Timeout:
                print(f"   ⏰ TIMEOUT - El endpoint tardó más de 30 segundos")
            except requests.exceptions.ConnectionError as e:
                print(f"   🔌 CONNECTION ERROR - {str(e)}")
            except requests.exceptions.RequestException as e:
                print(f"   🚫 REQUEST ERROR - {str(e)}")
            except Exception as e:
                print(f"   💥 UNEXPECTED ERROR - {str(e)}")
        
        print("\n❌ Ningún endpoint funcionó correctamente")
        return None

def diagnose_network():
    """Diagnóstico básico de red"""
    print("\n🌐 Diagnóstico de red:")
    print("=" * 30)
    
    test_urls = [
        "https://google.com",
        "https://api.deepseek.com",
        "https://api.deepseek.ai"
    ]
    
    for url in test_urls:
        try:
            response = requests.get(url, timeout=10)
            print(f"✅ {url} - Accesible (Status: {response.status_code})")
        except Exception as e:
            print(f"❌ {url} - Error: {str(e)}")

if __name__ == "__main__":
    print("🔍 DIAGNÓSTICO DE DEEPSEEK API")
    print("=" * 50)
    
    working_endpoint = test_deepseek_endpoints()
    diagnose_network()
    
    print("\n📋 RESUMEN:")
    print("=" * 20)
    
    if working_endpoint:
        print(f"✅ Endpoint funcional encontrado: {working_endpoint}")
        print("💡 El chat AI debería funcionar ahora")
    else:
        print("❌ No se encontró ningún endpoint funcional")
        print("💡 Soluciones posibles:")
        print("   1. Verificar la API key de DeepSeek")
        print("   2. Verificar conexión a internet")
        print("   3. Intentar más tarde (problemas del servidor DeepSeek)")
        print("   4. Contactar soporte de DeepSeek")
