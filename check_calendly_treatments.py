#!/usr/bin/env python3
"""
Script para verificar qué treatments de Calendly se crearon y sus IDs reales
"""

from app import create_app
from app.models import *
from datetime import datetime
from sqlalchemy import func, desc

def main():
    app = create_app()
    with app.app_context():
        print("=== VERIFICANDO TREATMENTS DE CALENDLY CREADOS ===\n")
        
        # 1. Buscar todos los treatments con calendly_invitee_uri
        calendly_treatments = Treatment.query.filter(
            Treatment.calendly_invitee_uri.isnot(None)
        ).order_by(desc(Treatment.id)).limit(20).all()
        
        print(f"📊 ÚLTIMOS 20 TREATMENTS DE CALENDLY:")
        for t in calendly_treatments:
            print(f"   ID: {t.id} | Patient: {t.patient.name} | Date: {t.created_at} | Status: {t.status}")
        
        # 2. Buscar treatments con IDs alrededor de 120
        treatments_around_120 = Treatment.query.filter(
            Treatment.id >= 115,
            Treatment.id <= 125
        ).order_by(Treatment.id).all()
        
        print(f"\n🔍 TREATMENTS CON IDs 115-125:")
        if treatments_around_120:
            for t in treatments_around_120:
                calendly_marker = "📅" if t.calendly_invitee_uri else "🏥"
                print(f"   {calendly_marker} ID: {t.id} | Patient: {t.patient.name} | Date: {t.created_at}")
        else:
            print("   ❌ No hay treatments en ese rango")
        
        # 3. Obtener el ID más alto
        max_id = Treatment.query.order_by(desc(Treatment.id)).first()
        print(f"\n📈 TREATMENT CON ID MÁS ALTO: {max_id.id if max_id else 'None'}")
        
        # 4. Contar treatments creados hoy
        today = datetime.utcnow().date()
        treatments_today = Treatment.query.filter(
            func.date(Treatment.created_at) >= today
        ).count()
        
        calendly_today = Treatment.query.filter(
            func.date(Treatment.created_at) >= today,
            Treatment.calendly_invitee_uri.isnot(None)
        ).count()
        
        print(f"\n📅 TREATMENTS CREADOS HOY:")
        print(f"   Total: {treatments_today}")
        print(f"   Calendly: {calendly_today}")
        
        # 5. Verificar si hay treatments duplicados o problemáticos
        user = User.query.filter(
            User.calendly_api_token_encrypted.isnot(None)
        ).first()
        
        if user:
            upcoming_treatments = Treatment.query.filter(
                Treatment.status == 'Scheduled',
                func.date(Treatment.created_at) >= today
            ).join(Patient).filter(Patient.user_id == user.id).all()
            
            print(f"\n🔮 UPCOMING TREATMENTS (Status=Scheduled, Future):")
            for t in upcoming_treatments:
                calendly_marker = "📅" if t.calendly_invitee_uri else "🏥"
                print(f"   {calendly_marker} ID: {t.id} | {t.patient.name} | {t.created_at}")
        
        print(f"\n✅ VERIFICACIÓN COMPLETADA")

if __name__ == "__main__":
    main() 