#!/usr/bin/env python3
"""
Script para configurar la base de datos de testing y ejecutar migraciones.
Este script:
1. Configura una base de datos de testing separada
2. Ejecuta todas las migraciones necesarias
3. Crea las tablas faltantes
4. Opcionalmente ejecuta el seed de planes
"""

import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def setup_test_database():
    """Configurar base de datos de testing y ejecutar migraciones."""
    
    # Configurar base de datos de testing
    test_db_url = os.getenv("TEST_DATABASE_URL")
    if not test_db_url:
        # Si no hay TEST_DATABASE_URL configurada, usar una base de datos SQLite temporal
        test_db_path = os.path.join(os.path.dirname(__file__), 'instance', 'test_physio.db')
        test_db_url = f"sqlite:///{test_db_path}"
        print(f"⚠️  No se encontró TEST_DATABASE_URL. Usando base de datos temporal: {test_db_path}")
    
    # Establecer la variable de entorno para testing
    os.environ['TEST_DATABASE_URL'] = test_db_url
    print(f"🔧 Configurando base de datos de testing: {test_db_url}")
    
    try:
        from app import create_app, db
        from flask_migrate import upgrade, current, history
        
        # Crear aplicación con configuración de testing
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = test_db_url
        app.config['WTF_CSRF_ENABLED'] = False
        
        with app.app_context():
            print("📊 Verificando estado actual de migraciones...")
            
            # Verificar migración actual
            try:
                current_revision = current()
                print(f"📍 Migración actual: {current_revision}")
            except Exception as e:
                print(f"⚠️  No hay migración actual aplicada: {e}")
            
            # Mostrar historial de migraciones
            try:
                print("📋 Historial de migraciones disponibles:")
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
            
            # Opcional: ejecutar seed de planes
            run_seed = input("\n🌱 ¿Ejecutar seed de planes? (y/n): ").lower().strip()
            if run_seed == 'y':
                print("🌱 Ejecutando seed de planes...")
                try:
                    from seed_plans import seed_plans
                    seed_plans()
                    print("✅ Seed de planes ejecutado exitosamente")
                except Exception as e:
                    print(f"❌ Error al ejecutar seed de planes: {e}")
            
            print("\n🎉 Configuración de base de datos de testing completada!")
            print(f"📁 Base de datos: {test_db_url}")
            
    except Exception as e:
        print(f"❌ Error durante la configuración: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def create_env_file():
    """Crear archivo .env con configuración de testing si no existe."""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    if os.path.exists(env_path):
        print(f"📄 Archivo .env ya existe: {env_path}")
        return
    
    print("📄 Creando archivo .env...")
    
    # Obtener configuración actual
    current_db_url = os.getenv("DATABASE_URL")
    if not current_db_url:
        current_db_url = "sqlite:///instance/physio.db"
    
    # Crear contenido del archivo .env
    env_content = f"""# Configuración de base de datos
DATABASE_URL={current_db_url}
TEST_DATABASE_URL=sqlite:///instance/test_physio.db

# Configuración de seguridad
SECRET_KEY=your-secret-key-here
FERNET_SECRET_KEY=your-fernet-key-here

# Configuración de Stripe (opcional)
STRIPE_SECRET_KEY=your-stripe-secret-key
STRIPE_PUBLISHABLE_KEY=your-stripe-publishable-key
STRIPE_WEBHOOK_SECRET=your-stripe-webhook-secret

# Configuración de Calendly (opcional)
CALENDLY_API_TOKEN=your-calendly-api-token

# Configuración de Sentry (opcional)
SENTRY_DSN=your-sentry-dsn
"""
    
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print(f"✅ Archivo .env creado: {env_path}")
    print("⚠️  Por favor, actualiza las claves secretas en el archivo .env")

if __name__ == "__main__":
    print("🔧 Configurando base de datos de testing para PhysioTracker")
    print("=" * 60)
    
    # Crear archivo .env si no existe
    create_env_file()
    
    # Configurar base de datos
    success = setup_test_database()
    
    if success:
        print("\n🎯 Próximos pasos:")
        print("1. Actualiza las claves secretas en el archivo .env")
        print("2. Ejecuta los tests: python -m pytest tests/")
        print("3. Si usas PostgreSQL, asegúrate de que la base de datos de testing existe")
    else:
        print("\n❌ La configuración falló. Revisa los errores arriba.")
        sys.exit(1) 