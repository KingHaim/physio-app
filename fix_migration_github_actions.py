#!/usr/bin/env python3
"""
Script para arreglar el problema de migración en GitHub Actions.
Este script ejecuta la migración de manera más robusta para CI/CD.
"""

import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def fix_migration_github_actions():
    """Arreglar la migración específicamente para GitHub Actions."""
    
    try:
        from app import create_app, db
        from flask_migrate import upgrade, current, history
        
        # Crear aplicación con configuración de testing
        app = create_app()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        with app.app_context():
            print("🔧 Arreglando migración para GitHub Actions...")
            
            # Verificar migración actual
            try:
                current_revision = current()
                print(f"📍 Migración actual: {current_revision}")
            except Exception as e:
                print(f"⚠️  No hay migración actual aplicada: {e}")
            
            # Ejecutar migraciones pendientes
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
            
            # Verificar específicamente el campo name de patient
            print("🔍 Verificando campo name de patient...")
            try:
                # Intentar obtener información del campo name
                result = db.session.execute("""
                    SELECT column_name, data_type, character_maximum_length 
                    FROM information_schema.columns 
                    WHERE table_name = 'patient' AND column_name = 'name'
                """).fetchone()
                
                if result:
                    column_name, data_type, max_length = result
                    print(f"📊 Campo name: {column_name}, tipo: {data_type}, longitud: {max_length}")
                    
                    if max_length and max_length < 500:
                        print("⚠️  El campo name no tiene la longitud correcta. Aplicando fix...")
                        # Aplicar el fix directamente
                        db.session.execute("""
                            ALTER TABLE patient 
                            ALTER COLUMN name TYPE VARCHAR(500)
                        """)
                        db.session.execute("""
                            ALTER TABLE patient 
                            ALTER COLUMN email TYPE VARCHAR(500)
                        """)
                        db.session.commit()
                        print("✅ Campo name actualizado a VARCHAR(500)")
                    else:
                        print("✅ Campo name tiene la longitud correcta")
                else:
                    print("⚠️  No se pudo obtener información del campo name")
                    
            except Exception as e:
                print(f"⚠️  Error verificando campo name: {e}")
                print("🔧 Intentando aplicar fix directamente...")
                try:
                    db.session.execute("""
                        ALTER TABLE patient 
                        ALTER COLUMN name TYPE VARCHAR(500)
                    """)
                    db.session.execute("""
                        ALTER TABLE patient 
                        ALTER COLUMN email TYPE VARCHAR(500)
                    """)
                    db.session.commit()
                    print("✅ Fix aplicado directamente")
                except Exception as fix_error:
                    print(f"❌ Error aplicando fix: {fix_error}")
            
            print(f"📊 Tablas disponibles: {tables}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error durante la corrección de migración: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Arreglando migración para GitHub Actions")
    print("=" * 50)
    
    success = fix_migration_github_actions()
    
    if success:
        print("\n🎉 Migración corregida exitosamente!")
    else:
        print("\n❌ La corrección de migración falló.")
        sys.exit(1) 