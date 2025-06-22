#!/usr/bin/env python3
"""
Script simple para ejecutar migraciones de la base de datos.
"""

import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def run_migrations():
    """Ejecutar todas las migraciones pendientes."""
    
    try:
        from app import create_app, db
        from flask_migrate import upgrade, current, history
        
        # Crear aplicación
        app = create_app()
        
        with app.app_context():
            print("🔍 Verificando estado actual de migraciones...")
            
            # Verificar migración actual
            try:
                current_revision = current()
                print(f"📍 Migración actual: {current_revision}")
            except Exception as e:
                print(f"⚠️  No hay migración actual aplicada: {e}")
            
            # Mostrar historial de migraciones
            try:
                print("📋 Migraciones disponibles:")
                for revision in history():
                    print(f"   - {revision.revision}: {revision.doc}")
            except Exception as e:
                print(f"⚠️  Error al obtener historial: {e}")
            
            # Ejecutar todas las migraciones pendientes
            print("🚀 Ejecutando migraciones...")
            upgrade()
            print("✅ Migraciones ejecutadas exitosamente")
            
            # Verificar que las tablas se crearon
            print("🔍 Verificando tablas creadas...")
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            required_tables = ['user', 'patient', 'treatment', 'plans', 'user_subscriptions']
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                print(f"❌ Tablas faltantes: {missing_tables}")
                print("🔧 Intentando crear tablas manualmente...")
                db.create_all()
                print("✅ Tablas creadas manualmente")
            else:
                print("✅ Todas las tablas requeridas están presentes")
            
            print(f"📊 Tablas disponibles: {tables}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error durante la ejecución de migraciones: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Ejecutando migraciones de la base de datos")
    print("=" * 50)
    
    success = run_migrations()
    
    if success:
        print("\n🎉 Migraciones completadas exitosamente!")
    else:
        print("\n❌ Las migraciones fallaron. Revisa los errores arriba.")
        sys.exit(1) 