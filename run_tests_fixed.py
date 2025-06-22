#!/usr/bin/env python3
"""
Script final para ejecutar tests con todas las correcciones aplicadas.
Este script:
1. Configura la base de datos correctamente
2. Aplica las migraciones necesarias
3. Ejecuta los tests con la configuración de testing
"""

import os
import sys
import subprocess
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def setup_test_environment():
    """Configurar el entorno de testing."""
    print("🔧 Configurando entorno de testing...")
    
    # Configurar variables de entorno para testing
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['TESTING'] = 'True'
    
    # Si no hay DATABASE_URL configurada, usar SQLite
    if not os.getenv('DATABASE_URL'):
        os.environ['DATABASE_URL'] = 'sqlite:///instance/test_physio.db'
    
    # Si no hay TEST_DATABASE_URL configurada, usar la misma que DATABASE_URL
    if not os.getenv('TEST_DATABASE_URL'):
        os.environ['TEST_DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///instance/test_physio.db')
    
    print("✅ Entorno de testing configurado")

def run_migrations():
    """Ejecutar migraciones."""
    print("🔧 Ejecutando migraciones...")
    try:
        result = subprocess.run([sys.executable, "fix_migration_github_actions.py"], 
                              capture_output=True, text=True, check=True)
        print("✅ Migraciones ejecutadas exitosamente")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando migraciones: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False

def run_tests():
    """Ejecutar los tests."""
    print("🧪 Ejecutando tests...")
    
    # Comandos de pytest con opciones optimizadas
    pytest_cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--maxfail=10",  # Stop after 10 failures
        "--disable-warnings",  # Disable warnings
        "--no-header",  # No header
        "--no-summary"  # No summary at the end
    ]
    
    try:
        result = subprocess.run(pytest_cmd, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error ejecutando tests: {e}")
        return False

def main():
    """Función principal."""
    print("🚀 Iniciando ejecución de tests con correcciones")
    print("=" * 60)
    
    # Paso 1: Configurar entorno
    setup_test_environment()
    
    # Paso 2: Ejecutar migraciones
    if not run_migrations():
        print("❌ Falló la ejecución de migraciones")
        sys.exit(1)
    
    # Paso 3: Ejecutar tests
    print("\n" + "=" * 60)
    success = run_tests()
    
    if success:
        print("\n🎉 ¡Todos los tests pasaron exitosamente!")
    else:
        print("\n❌ Algunos tests fallaron.")
        sys.exit(1)

if __name__ == "__main__":
    main() 