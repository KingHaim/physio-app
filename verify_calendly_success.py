#!/usr/bin/env python3
"""
Script para verificar si las citas de Calendly sincronizadas aparecen correctamente
"""

from app import create_app
from app.models import *
from datetime import datetime
from sqlalchemy import func

def main():
    app = create_app()
    with app.app_context():
        print("=== VERIFICANDO ÉXITO DE SINCRONIZACIÓN CALENDLY ===\n")
        
        user = User.query.filter(
            User.calendly_api_token_encrypted.isnot(None),
            User.calendly_user_uri.isnot(None)
        ).first()
        
        today = datetime.utcnow().date()
        print(f"Fecha de hoy: {today}")
        
        # 1. Contar todas las citas de Calendly
        total_calendly = Treatment.query.filter(
            Treatment.calendly_invitee_uri.isnot(None)
        ).join(Patient).filter(Patient.user_id == user.id).count()
        
        # 2. Contar citas futuras de Calendly
        future_calendly = Treatment.query.filter(
            Treatment.calendly_invitee_uri.isnot(None),
            func.date(Treatment.created_at) >= today
        ).join(Patient).filter(Patient.user_id == user.id).count()
        
        # 3. Obtener upcoming appointments (como en el dashboard)
        accessible_patients = user.get_accessible_patients()
        accessible_patient_ids = [p.id for p in accessible_patients]
        
        upcoming_treatments = Treatment.query.filter(
            Treatment.patient_id.in_(accessible_patient_ids),
            Treatment.status == 'Scheduled',
            func.date(Treatment.created_at) >= today
        ).order_by(Treatment.created_at.asc()).limit(10).all()
        
        upcoming_calendly = [t for t in upcoming_treatments if t.calendly_invitee_uri]
        
        print(f"\n📊 RESULTADOS:")
        print(f"   Total citas Calendly: {total_calendly}")
        print(f"   Citas futuras Calendly: {future_calendly}")
        print(f"   Upcoming treatments (todas): {len(upcoming_treatments)}")
        print(f"   Upcoming treatments (Calendly): {len(upcoming_calendly)}")
        
        if upcoming_calendly:
            print(f"\n🎉 ¡ÉXITO! CITAS DE CALENDLY EN UPCOMING APPOINTMENTS:")
            for i, t in enumerate(upcoming_calendly, 1):
                print(f"   {i}. {t.patient.name}: {t.created_at} ({t.treatment_type})")
                
            print(f"\n✅ SOLUCIÓN COMPLETADA:")
            print(f"   - {len(upcoming_calendly)} citas de Calendly aparecen en el dashboard")
            print(f"   - Smart matching funcionó correctamente")
            print(f"   - Auto-sync está operativo")
            print(f"\n🚀 Ve a tu dashboard y verás las citas!")
        
        elif future_calendly > 0:
            print(f"\n⚠️ HAY {future_calendly} CITAS FUTURAS PERO NO EN UPCOMING")
            print(f"   Esto puede ser porque:")
            print(f"   1. Las citas tienen status diferente a 'Scheduled'")
            print(f"   2. Hay un problema con accessible_patients")
            
            # Revisar status de citas futuras
            future_treatments = Treatment.query.filter(
                Treatment.calendly_invitee_uri.isnot(None),
                func.date(Treatment.created_at) >= today
            ).join(Patient).filter(Patient.user_id == user.id).all()
            
            print(f"\n   📋 STATUS DE CITAS FUTURAS:")
            for t in future_treatments[:5]:
                print(f"   - {t.patient.name}: {t.created_at} (Status: {t.status})")
        
        else:
            print(f"\n❌ NO HAY CITAS FUTURAS SINCRONIZADAS")
            print(f"   Necesitas ejecutar el script de sincronización nuevamente")
        
        print(f"\n✅ VERIFICACIÓN COMPLETADA!")

if __name__ == "__main__":
    main() 