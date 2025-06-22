#!/usr/bin/env python3
"""
Script para ejecutar migraciones y luego correr los tests.
"""

import os
import sys
import subprocess
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def run_migrations():
    """Ejecutar migraciones antes de los tests."""
    print("🔧 Ejecutando migraciones...")
    try:
        result = subprocess.run([sys.executable, "run_migrations.py"], 
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
    try:
        # Usar configuración de testing más conservadora
        env = os.environ.copy()
        env['TESTING'] = 'True'
        
        # Ejecutar pytest con configuración optimizada
        cmd = [
            sys.executable, "-m", "pytest",
            "-v",  # Verbose output
            "--tb=short",  # Shorter traceback
            "--maxfail=5",  # Stop after 5 failures
            "--durations=10",  # Show 10 slowest tests
        ]
        
        result = subprocess.run(cmd, env=env, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error ejecutando tests: {e}")
        return False

def main():
    """Función principal."""
    print("🚀 Iniciando proceso de testing")
    print("=" * 50)
    
    # Ejecutar migraciones primero
    if not run_migrations():
        print("❌ Falló la ejecución de migraciones. Abortando tests.")
        sys.exit(1)
    
    # Ejecutar tests
    success = run_tests()
    
    if success:
        print("\n🎉 Todos los tests pasaron exitosamente!")
    else:
        print("\n❌ Algunos tests fallaron.")
        sys.exit(1)

if __name__ == "__main__":
    main() 