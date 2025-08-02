#!/usr/bin/env python3
"""
Script para investigar las fechas de Calendly y por qué no hay upcoming appointments
"""

from app import create_app
from app.models import *
from datetime import datetime, timedelta
from sqlalchemy import func

def main():
    app = create_app()
    with app.app_context():
        print("=== INVESTIGACIÓN DE FECHAS CALENDLY ===\n")
        
        user = User.query.filter(
            User.calendly_api_token_encrypted.isnot(None),
            User.calendly_user_uri.isnot(None)
        ).first()
        
        today = datetime.utcnow().date()
        print(f"Fecha de hoy (UTC): {today}")
        
        # 1. Analizar fechas de treatments con Calendly
        print(f"\n1. ANALIZANDO FECHAS DE TREATMENTS CON CALENDLY...")
        
        calendly_treatments = Treatment.query.filter(
            Treatment.calendly_invitee_uri.isnot(None)
        ).join(Patient).filter(Patient.user_id == user.id).order_by(Treatment.created_at.desc()).limit(10).all()
        
        print(f"   Últimas 10 citas de Calendly:")
        for t in calendly_treatments:
            status_icon = "🔮" if t.created_at.date() >= today else "📅"
            print(f"   {status_icon} {t.patient.name}: {t.created_at} ({t.status})")
        
        # 2. Contar citas por fecha
        print(f"\n2. CONTANDO CITAS POR PERÍODO...")
        
        # Citas pasadas
        past_count = Treatment.query.filter(
            Treatment.calendly_invitee_uri.isnot(None),
            func.date(Treatment.created_at) < today
        ).join(Patient).filter(Patient.user_id == user.id).count()
        
        # Citas futuras
        future_count = Treatment.query.filter(
            Treatment.calendly_invitee_uri.isnot(None),
            func.date(Treatment.created_at) >= today
        ).join(Patient).filter(Patient.user_id == user.id).count()
        
        print(f"   Citas pasadas: {past_count}")
        print(f"   Citas futuras: {future_count}")
        
        # 3. Analizar UnmatchedCalendlyBookings
        print(f"\n3. ANALIZANDO UNMATCHED CALENDLY BOOKINGS...")
        
        unmatched_bookings = UnmatchedCalendlyBooking.query.filter_by(
            user_id=user.id,
            status='Pending'
        ).order_by(UnmatchedCalendlyBooking.start_time.desc()).limit(10).all()
        
        print(f"   Últimas 10 UnmatchedCalendlyBookings:")
        for booking in unmatched_bookings:
            date_obj = booking.start_time.date() if booking.start_time else None
            if date_obj:
                status_icon = "🔮" if date_obj >= today else "📅"
                print(f"   {status_icon} {booking.name} ({booking.email}): {booking.start_time}")
            else:
                print(f"   ❓ {booking.name} ({booking.email}): No date")
        
        # 4. Buscar citas futuras específicamente
        print(f"\n4. BUSCANDO CITAS FUTURAS ESPECÍFICAMENTE...")
        
        future_treatments = Treatment.query.filter(
            Treatment.calendly_invitee_uri.isnot(None),
            func.date(Treatment.created_at) >= today,
            Treatment.status == 'Scheduled'
        ).join(Patient).filter(Patient.user_id == user.id).all()
        
        print(f"   Citas futuras con status 'Scheduled': {len(future_treatments)}")
        
        if future_treatments:
            print(f"   📅 CITAS FUTURAS ENCONTRADAS:")
            for t in future_treatments:
                print(f"   🔮 {t.patient.name}: {t.created_at} ({t.treatment_type})")
        
        # 5. Buscar UnmatchedCalendlyBookings futuras
        future_unmatched = [b for b in unmatched_bookings if b.start_time and b.start_time.date() >= today]
        
        print(f"\n5. UNMATCHED BOOKINGS FUTURAS: {len(future_unmatched)}")
        
        if future_unmatched:
            print(f"   🔮 BOOKINGS FUTURAS SIN PROCESAR:")
            for booking in future_unmatched:
                print(f"   - {booking.name} ({booking.email}): {booking.start_time}")
                
                # Buscar si existe paciente con este nombre
                patient_by_name = Patient.query.filter(
                    Patient.user_id == user.id,
                    Patient.name.ilike(f'%{booking.name}%')
                ).first()
                
                if patient_by_name:
                    print(f"     ✅ Paciente encontrado: {patient_by_name.name} (Email: {patient_by_name.email})")
                else:
                    print(f"     ❌ No se encontró paciente con nombre similar")
        
        print(f"\n=== RESUMEN ===")
        print(f"📊 Total treatments Calendly: {len(calendly_treatments)}")
        print(f"📅 Tratamientos pasados: {past_count}")
        print(f"🔮 Tratamientos futuros: {future_count}")
        print(f"📋 UnmatchedCalendlyBookings: {len(unmatched_bookings)}")
        print(f"🔮 UnmatchedCalendlyBookings futuras: {len(future_unmatched)}")
        
        if future_count == 0 and len(future_unmatched) > 0:
            print(f"\n🎯 PROBLEMA IDENTIFICADO:")
            print(f"   Las citas futuras están en UnmatchedCalendlyBookings")
            print(f"   Necesitan ser procesadas con smart matching")
        elif future_count == 0 and len(future_unmatched) == 0:
            print(f"\n🎯 PROBLEMA IDENTIFICADO:")
            print(f"   No hay citas futuras en Calendly")
            print(f"   O no se están sincronizando correctamente")

if __name__ == "__main__":
    main() 