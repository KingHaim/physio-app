#!/usr/bin/env python3
"""
Script para forzar sincronización completa de Calendly en production
"""

from app import create_app
from app.models import *
from app.utils import sync_calendly_for_user
from datetime import datetime, timedelta
from sqlalchemy import func
import requests

def main():
    app = create_app()
    with app.app_context():
        print("=== FORZANDO SINCRONIZACIÓN CALENDLY PRODUCTION ===\n")
        
        user = User.query.filter(
            User.calendly_api_token_encrypted.isnot(None),
            User.calendly_user_uri.isnot(None)
        ).first()
        
        if not user:
            print("❌ No se encontró usuario con Calendly configurado")
            return
        
        print(f"Usuario: {user.email} (ID: {user.id})")
        
        # 1. Probar conexión directa con Calendly API
        print(f"\n1. PROBANDO CONEXIÓN DIRECTA CON CALENDLY API...")
        
        try:
            api_token = user.calendly_api_token
            headers = {
                'Authorization': f'Bearer {api_token}',
                'Content-Type': 'application/json'
            }
            
            # Obtener eventos de los próximos 90 días
            min_time = datetime.utcnow().isoformat() + 'Z'
            max_time = (datetime.utcnow() + timedelta(days=90)).isoformat() + 'Z'
            
            events_url = 'https://api.calendly.com/scheduled_events'
            params = {
                'user': user.calendly_user_uri,
                'min_start_time': min_time,
                'max_start_time': max_time,
                'status': 'active',
                'sort': 'start_time:asc',
                'count': 100  # Aumentar límite
            }
            
            print(f"   Consultando eventos desde: {min_time}")
            print(f"   Hasta: {max_time}")
            
            response = requests.get(events_url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('collection', [])
                print(f"   ✅ API Response exitoso: {len(events)} eventos encontrados")
                
                if events:
                    print(f"\n   📅 EVENTOS FUTUROS EN CALENDLY:")
                    for i, event in enumerate(events[:10]):  # Mostrar primeros 10
                        start_time = event.get('start_time', 'No date')
                        name = event.get('name', 'No name')
                        print(f"   {i+1}. {name}: {start_time}")
                    
                    if len(events) > 10:
                        print(f"   ... y {len(events) - 10} eventos más")
                else:
                    print(f"   ⚠️ No hay eventos futuros en Calendly")
                    return
                    
            else:
                print(f"   ❌ Error en API: {response.status_code} - {response.text}")
                return
                
        except Exception as e:
            print(f"   ❌ Error conectando con Calendly: {str(e)}")
            return
        
        # 2. Forzar sincronización usando nuestra función
        print(f"\n2. FORZANDO SINCRONIZACIÓN CON SMART MATCHING...")
        
        try:
            result = sync_calendly_for_user(user)
            print(f"   ✅ Sincronización exitosa:")
            print(f"   - Treatments creados: {result.get('new_treatments', 0)}")
            print(f"   - Bookings sin match: {result.get('new_unmatched_bookings', 0)}")
        except Exception as e:
            print(f"   ❌ Error en sincronización: {str(e)}")
        
        # 3. Verificar resultado
        print(f"\n3. VERIFICANDO RESULTADO...")
        
        today = datetime.utcnow().date()
        future_treatments = Treatment.query.filter(
            Treatment.calendly_invitee_uri.isnot(None),
            func.date(Treatment.created_at) >= today,
            Treatment.status == 'Scheduled'
        ).join(Patient).filter(Patient.user_id == user.id).all()
        
        unmatched_future = UnmatchedCalendlyBooking.query.filter(
            UnmatchedCalendlyBooking.user_id == user.id,
            UnmatchedCalendlyBooking.status == 'Pending',
            func.date(UnmatchedCalendlyBooking.start_time) >= today
        ).all()
        
        print(f"   Treatments futuros creados: {len(future_treatments)}")
        print(f"   UnmatchedCalendlyBookings futuros: {len(unmatched_future)}")
        
        if future_treatments:
            print(f"\n   🎉 CITAS FUTURAS CREADAS:")
            for t in future_treatments:
                print(f"   - {t.patient.name}: {t.created_at} ({t.treatment_type})")
        
        if unmatched_future:
            print(f"\n   📋 BOOKINGS FUTUROS SIN PROCESAR:")
            for booking in unmatched_future:
                print(f"   - {booking.name} ({booking.email}): {booking.start_time}")
        
        # 4. Si no hay resultados, investigar más
        if not future_treatments and not unmatched_future:
            print(f"\n❌ TODAVÍA NO HAY CITAS FUTURAS")
            print(f"   Esto significa que:")
            print(f"   1. No hay eventos futuros en tu Calendly")
            print(f"   2. Los eventos no están en el rango de 90 días")
            print(f"   3. Hay un problema con la sincronización")
            
            # Verificar eventos en un rango más amplio
            print(f"\n   🔍 VERIFICANDO RANGO MÁS AMPLIO...")
            max_time_extended = (datetime.utcnow() + timedelta(days=365)).isoformat() + 'Z'
            params['max_start_time'] = max_time_extended
            
            response_extended = requests.get(events_url, headers=headers, params=params, timeout=30)
            if response_extended.status_code == 200:
                events_extended = response_extended.json().get('collection', [])
                print(f"   Eventos en próximos 365 días: {len(events_extended)}")
        
        print(f"\n✅ SINCRONIZACIÓN FORZADA COMPLETADA!")

if __name__ == "__main__":
    main() 