#!/usr/bin/env python3
"""
Script para crear la tabla patient_ai_conversations en PythonAnywhere
Ejecutar este script en la consola de PythonAnywhere
"""

from app import create_app
from app.models import db, PatientAIConversation

def create_ai_conversation_table():
    """Crear la tabla patient_ai_conversations"""
    app = create_app()
    
    with app.app_context():
        print("🔧 Creando tabla patient_ai_conversations en PythonAnywhere...")
        
        try:
            # Create all tables (incluyendo la nueva)
            db.create_all()
            
            # Verify the table was created
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'patient_ai_conversations' in tables:
                print("✅ Tabla patient_ai_conversations creada exitosamente!")
                
                # Show table structure
                columns = inspector.get_columns('patient_ai_conversations')
                print("📋 Estructura de la tabla:")
                for col in columns:
                    print(f"  - {col['name']}: {col['type']}")
                    
                # Test table access
                count = PatientAIConversation.query.count()
                print(f"✅ Tabla accesible. Conversaciones existentes: {count}")
                
            else:
                print("❌ Error: No se pudo crear la tabla")
                print(f"Tablas existentes: {tables}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    create_ai_conversation_table()
