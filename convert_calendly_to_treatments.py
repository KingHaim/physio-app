from app import create_app
from app.models import *
from datetime import datetime

app = create_app()
with app.app_context():
    print("=== CONVERTIR CALENDLY BOOKINGS A TREATMENTS (SMART MATCHING) ===\n")
    
    # Encontrar el usuario con Calendly configurado
    user = User.query.filter(
        User.calendly_api_token_encrypted.isnot(None),
        User.calendly_user_uri.isnot(None)
    ).first()
    
    if not user:
        print("❌ No se encontró usuario con Calendly configurado")
        exit()
    
    print(f"Usuario: {user.email} (ID: {user.id})")
    
    # Obtener todos los UnmatchedCalendlyBooking pendientes
    unmatched_bookings = UnmatchedCalendlyBooking.query.filter_by(
        user_id=user.id,
        status='Pending'
    ).order_by(UnmatchedCalendlyBooking.start_time.asc()).all()
    
    print(f"UnmatchedCalendlyBookings pendientes: {len(unmatched_bookings)}")
    
    if len(unmatched_bookings) == 0:
        print("✅ No hay bookings pendientes para convertir")
        exit()
    
    # Obtener todos los pacientes existentes
    existing_patients = Patient.query.filter_by(user_id=user.id).all()
    print(f"Pacientes existentes en base de datos: {len(existing_patients)}")
    
    print("\n=== ANÁLISIS DE MATCHING ===")
    
    # Analizar cada booking
    matches = {
        'exact_match': [],      # Nombre y email coinciden exactamente
        'name_match_no_email': [],  # Nombre coincide, paciente no tiene email
        'name_match_diff_email': [],  # Nombre coincide, email diferente (conflicto)
        'new_patients': []      # No existe el nombre, paciente nuevo
    }
    
    for booking in unmatched_bookings:
        booking_name = booking.name.strip()
        booking_email = booking.email.lower().strip()
        
        # Buscar pacientes con nombre similar (case-insensitive)
        matching_patients = [p for p in existing_patients 
                           if p.name and p.name.strip().lower() == booking_name.lower()]
        
        if not matching_patients:
            # No existe el nombre - paciente nuevo
            matches['new_patients'].append({
                'booking': booking,
                'action': 'create_new',
                'patient': None
            })
        else:
            # Existe el nombre - verificar email
            patient = matching_patients[0]  # Tomar el primero si hay múltiples
            
            if not patient.email or patient.email.strip() == '':
                # Paciente existe pero sin email - match perfecto
                matches['name_match_no_email'].append({
                    'booking': booking,
                    'action': 'update_email',
                    'patient': patient
                })
            elif patient.email.lower().strip() == booking_email:
                # Nombre y email coinciden - match exacto
                matches['exact_match'].append({
                    'booking': booking,
                    'action': 'use_existing',
                    'patient': patient
                })
            else:
                # Nombre coincide pero email diferente - conflicto
                matches['name_match_diff_email'].append({
                    'booking': booking,
                    'action': 'manual_review',
                    'patient': patient,
                    'conflict': f"Existing: {patient.email} vs Calendly: {booking_email}"
                })
    
    # Mostrar resultados del análisis
    print(f"✅ Matches exactos (nombre + email): {len(matches['exact_match'])}")
    print(f"🔄 Pacientes existentes sin email: {len(matches['name_match_no_email'])}")
    print(f"⚠️  Conflictos de email: {len(matches['name_match_diff_email'])}")
    print(f"🆕 Pacientes nuevos: {len(matches['new_patients'])}")
    
    if matches['name_match_diff_email']:
        print(f"\n⚠️  CONFLICTOS DETECTADOS:")
        for match in matches['name_match_diff_email']:
            print(f"  - {match['booking'].name}: {match['conflict']}")
    
    # Calcular acciones automáticas
    auto_actions = (len(matches['exact_match']) + 
                   len(matches['name_match_no_email']) + 
                   len(matches['new_patients']))
    manual_reviews = len(matches['name_match_diff_email'])
    
    print(f"\n🔄 PLAN DE CONVERSIÓN:")
    print(f"✅ Conversiones automáticas: {auto_actions}")
    print(f"📋 Revisiones manuales necesarias: {manual_reviews}")
    
    if manual_reviews > 0:
        print(f"\n⚠️  Los conflictos se marcarán para revisión manual en el dashboard")
    
    # Mostrar detalles de las acciones automáticas
    if matches['exact_match']:
        print(f"\n✅ MATCHES EXACTOS:")
        for match in matches['exact_match'][:5]:  # Mostrar solo primeros 5
            print(f"  - {match['booking'].name} ({match['booking'].email}) → Usar paciente existente")
        if len(matches['exact_match']) > 5:
            print(f"  ... y {len(matches['exact_match']) - 5} más")
    
    if matches['name_match_no_email']:
        print(f"\n🔄 PACIENTES SIN EMAIL (se actualizará):")
        for match in matches['name_match_no_email'][:5]:
            print(f"  - {match['booking'].name} → Agregar email: {match['booking'].email}")
        if len(matches['name_match_no_email']) > 5:
            print(f"  ... y {len(matches['name_match_no_email']) - 5} más")
    
    if matches['new_patients']:
        print(f"\n🆕 PACIENTES NUEVOS (se crearán):")
        # Agrupar por email para mostrar pacientes únicos
        new_patient_emails = {}
        for match in matches['new_patients']:
            email = match['booking'].email
            if email not in new_patient_emails:
                new_patient_emails[email] = match['booking'].name
        
        for email, name in list(new_patient_emails.items())[:5]:
            print(f"  - {name} ({email})")
        if len(new_patient_emails) > 5:
            print(f"  ... y {len(new_patient_emails) - 5} más")
    
    # Confirmar acción
    confirm = input(f"\n¿Proceder con {auto_actions} conversiones automáticas? (y/N): ").lower().strip()
    
    if confirm != 'y':
        print("❌ Conversión cancelada")
        exit()
    
    print("\n🚀 INICIANDO CONVERSIÓN INTELIGENTE...")
    
    created_patients = 0
    updated_patients = 0
    created_treatments = 0
    updated_bookings = 0
    manual_reviews_created = 0
    
    try:
        # Procesar matches exactos
        for match in matches['exact_match']:
            booking = match['booking']
            patient = match['patient']
            
            # Crear treatment
            treatment = Treatment(
                patient_id=patient.id,
                created_at=booking.start_time,
                treatment_type=booking.event_type,
                status="Scheduled",
                provider=user.email,
                notes=f"Auto-converted from Calendly booking. Invitee: {booking.name} ({booking.email})",
                calendly_invitee_uri=booking.calendly_invitee_id
            )
            db.session.add(treatment)
            created_treatments += 1
            
            # Actualizar booking
            booking.status = 'Matched'
            booking.matched_patient_id = patient.id
            updated_bookings += 1
            
            print(f"  ✅ Match exacto: {booking.name} → Treatment creado")
        
        # Procesar pacientes existentes sin email
        for match in matches['name_match_no_email']:
            booking = match['booking']
            patient = match['patient']
            
            # Actualizar email del paciente
            patient.email = booking.email
            updated_patients += 1
            
            # Crear treatment
            treatment = Treatment(
                patient_id=patient.id,
                created_at=booking.start_time,
                treatment_type=booking.event_type,
                status="Scheduled",
                provider=user.email,
                notes=f"Auto-converted from Calendly booking. Email updated. Invitee: {booking.name} ({booking.email})",
                calendly_invitee_uri=booking.calendly_invitee_id
            )
            db.session.add(treatment)
            created_treatments += 1
            
            # Actualizar booking
            booking.status = 'Matched'
            booking.matched_patient_id = patient.id
            updated_bookings += 1
            
            print(f"  🔄 Email actualizado: {booking.name} ({booking.email}) → Treatment creado")
        
        # Procesar pacientes nuevos (agrupados por email)
        new_patient_groups = {}
        for match in matches['new_patients']:
            email = match['booking'].email
            if email not in new_patient_groups:
                new_patient_groups[email] = {
                    'name': match['booking'].name,
                    'email': email,
                    'bookings': []
                }
            new_patient_groups[email]['bookings'].append(match['booking'])
        
        for email, patient_data in new_patient_groups.items():
            # Crear nuevo paciente
            patient = Patient(
                user_id=user.id,
                name=patient_data['name'],
                email=patient_data['email'],
                created_at=datetime.utcnow(),
                status='Active'
            )
            db.session.add(patient)
            db.session.flush()  # Para obtener el ID
            created_patients += 1
            
            print(f"  🆕 Paciente creado: {patient.name} ({patient.email})")
            
            # Crear treatments para todos los bookings de este paciente
            for booking in patient_data['bookings']:
                treatment = Treatment(
                    patient_id=patient.id,
                    created_at=booking.start_time,
                    treatment_type=booking.event_type,
                    status="Scheduled",
                    provider=user.email,
                    notes=f"Auto-converted from Calendly booking. New patient. Invitee: {booking.name} ({booking.email})",
                    calendly_invitee_uri=booking.calendly_invitee_id
                )
                db.session.add(treatment)
                created_treatments += 1
                
                # Actualizar booking
                booking.status = 'Matched'
                booking.matched_patient_id = patient.id
                updated_bookings += 1
        
        # Marcar conflictos para revisión manual
        for match in matches['name_match_diff_email']:
            booking = match['booking']
            booking.status = 'Needs Review'
            booking.notes = f"Email conflict: Existing patient has {match['patient'].email}, Calendly has {booking.email}"
            manual_reviews_created += 1
            print(f"  ⚠️  Marcado para revisión: {booking.name} (conflicto de email)")
        
        # Commit todos los cambios
        db.session.commit()
        
        print(f"\n🎉 CONVERSIÓN INTELIGENTE COMPLETADA:")
        print(f"  ✅ Pacientes nuevos creados: {created_patients}")
        print(f"  🔄 Pacientes existentes actualizados: {updated_patients}")
        print(f"  📅 Treatments creados: {created_treatments}")
        print(f"  📋 Bookings procesados: {updated_bookings}")
        print(f"  ⚠️  Conflictos marcados para revisión: {manual_reviews_created}")
        
        # Verificar el resultado
        upcoming_treatments = Treatment.query.filter(
            Treatment.status == 'Scheduled',
            Treatment.created_at >= datetime.utcnow()
        ).join(Patient).filter(Patient.user_id == user.id).count()
        
        print(f"\n📈 RESULTADOS:")
        print(f"  → Upcoming treatments en dashboard: {upcoming_treatments}")
        if manual_reviews_created > 0:
            print(f"  → Revisar conflictos en: Dashboard → Calendly Bookings")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error durante la conversión: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
    
    print("\n✅ ¡CONVERSIÓN INTELIGENTE COMPLETADA! Tus citas de Calendly ahora aparecen en el dashboard.") 