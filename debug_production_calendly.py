#!/usr/bin/env python3
"""
Script de diagnóstico para verificar Calendly en production
Ejecutar en PythonAnywhere: python debug_production_calendly.py
"""

from app import create_app
from app.models import *
from app.utils import auto_sync_appointments
from datetime import datetime, timedelta
from sqlalchemy import func

def main():
    app = create_app()
    with app.app_context():
        print("=== DIAGNÓSTICO CALENDLY PRODUCTION ===\n")
        
        # 1. Verificar configuración de Calendly
        print("1. VERIFICANDO CONFIGURACIÓN DE CALENDLY...")
        calendly_users = User.query.filter(
            User.calendly_api_token_encrypted.isnot(None),
            User.calendly_user_uri.isnot(None)
        ).all()
        
        if not calendly_users:
            print("❌ PROBLEMA: Ningún usuario tiene Calendly configurado en production")
            print("   SOLUCIÓN: Configurar Calendly API en Settings → API Integrations")
            return
        
        user = calendly_users[0]
        print(f"✅ Usuario con Calendly: {user.email} (ID: {user.id})")
        
        # 2. Verificar si hay datos de Calendly
        print(f"\n2. VERIFICANDO DATOS EXISTENTES...")
        treatments_with_calendly = Treatment.query.filter(
            Treatment.calendly_invitee_uri.isnot(None)
        ).join(Patient).filter(Patient.user_id == user.id).count()
        
        unmatched_bookings = UnmatchedCalendlyBooking.query.filter_by(
            user_id=user.id
        ).count()
        
        print(f"   Treatments con Calendly: {treatments_with_calendly}")
        print(f"   UnmatchedCalendlyBookings: {unmatched_bookings}")
        
        if treatments_with_calendly == 0 and unmatched_bookings == 0:
            print("⚠️ NO HAY DATOS DE CALENDLY en production")
            print("   Esto indica que la sincronización nunca se ha ejecutado")
        
        # 3. Verificar upcoming appointments
        print(f"\n3. VERIFICANDO UPCOMING APPOINTMENTS...")
        today = datetime.utcnow().date()
        accessible_patients = user.get_accessible_patients()
        accessible_patient_ids = [p.id for p in accessible_patients]
        
        upcoming_treatments = Treatment.query.filter(
            Treatment.patient_id.in_(accessible_patient_ids),
            Treatment.status == 'Scheduled',
            func.date(Treatment.created_at) >= today
        ).order_by(Treatment.created_at.asc()).limit(10).all()
        
        upcoming_calendly = [t for t in upcoming_treatments if t.calendly_invitee_uri]
        
        print(f"   Total upcoming treatments: {len(upcoming_treatments)}")
        print(f"   Upcoming Calendly treatments: {len(upcoming_calendly)}")
        
        # 4. Probar auto_sync_appointments
        print(f"\n4. PROBANDO AUTO_SYNC_APPOINTMENTS...")
        try:
            user_id = None if user.is_admin else user.id
            sync_result = auto_sync_appointments(user_id)
            print(f"✅ AUTO_SYNC EXITOSO:")
            print(f"   created_treatments: {sync_result.get('created_treatments', 0)}")
            print(f"   calendly_treatments: {sync_result.get('calendly_treatments', 0)}")
            print(f"   calendly_bookings: {sync_result.get('calendly_bookings', 0)}")
        except Exception as e:
            print(f"❌ AUTO_SYNC FALLÓ: {str(e)}")
            print("   CAUSA: Posible problema con API de Calendly o configuración")
        
        # 5. Verificar después del sync
        print(f"\n5. VERIFICANDO DESPUÉS DEL SYNC...")
        treatments_after = Treatment.query.filter(
            Treatment.calendly_invitee_uri.isnot(None)
        ).join(Patient).filter(Patient.user_id == user.id).count()
        
        upcoming_after = Treatment.query.filter(
            Treatment.patient_id.in_(accessible_patient_ids),
            Treatment.status == 'Scheduled',
            func.date(Treatment.created_at) >= today
        ).order_by(Treatment.created_at.asc()).limit(10).all()
        
        upcoming_calendly_after = [t for t in upcoming_after if t.calendly_invitee_uri]
        
        print(f"   Treatments con Calendly (después): {treatments_after}")
        print(f"   Upcoming Calendly (después): {len(upcoming_calendly_after)}")
        
        if len(upcoming_calendly_after) > 0:
            print(f"\n📅 CITAS DE CALENDLY ENCONTRADAS:")
            for t in upcoming_calendly_after[:5]:  # Solo mostrar 5
                print(f"   - {t.patient.name}: {t.created_at} ({t.treatment_type})")
            print(f"\n✅ SOLUCIÓN: Las citas están ahí - verificar en el dashboard")
        else:
            print(f"\n❌ PROBLEMA PERSISTE: No hay citas de Calendly en upcoming")
            print(f"   POSIBLES CAUSAS:")
            print(f"   1. API de Calendly no configurada correctamente")
            print(f"   2. No hay eventos futuros en Calendly")
            print(f"   3. Emails no coinciden con pacientes existentes")
        
        print(f"\n✅ DIAGNÓSTICO COMPLETADO!")

if __name__ == "__main__":
    main() 