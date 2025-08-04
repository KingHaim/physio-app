#!/usr/bin/env python3
"""
Script para investigar qué datos tiene el treatment 120 que causa el error 500
"""

from app import create_app
from app.models import *
from datetime import datetime

def main():
    app = create_app()
    with app.app_context():
        print("=== INVESTIGANDO TREATMENT 120 ===\n")
        
        # Buscar el treatment
        treatment = Treatment.query.get(120)
        if not treatment:
            print("❌ Treatment 120 no existe")
            return
        
        print(f"✅ Treatment 120 encontrado:")
        print(f"   ID: {treatment.id}")
        print(f"   Patient ID: {treatment.patient_id}")
        print(f"   Created At: {treatment.created_at}")
        print(f"   Treatment Type: {treatment.treatment_type}")
        print(f"   Status: {treatment.status}")
        print(f"   Notes: {treatment.notes}")
        print(f"   Provider: {treatment.provider}")
        print(f"   Calendly URI: {treatment.calendly_invitee_uri}")
        
        # Verificar si el patient existe
        patient = treatment.patient
        if not patient:
            print(f"\n❌ PROBLEMA: El treatment 120 no tiene patient asociado!")
            return
        
        print(f"\n✅ Patient asociado:")
        print(f"   ID: {patient.id}")
        print(f"   Name: {patient.name}")
        print(f"   Email: {patient.email}")
        print(f"   User ID: {patient.user_id}")
        
        # Verificar campos que pueden ser None y causar errores
        problematic_fields = []
        
        if treatment.pain_level is not None:
            try:
                pain_level_int = int(treatment.pain_level)
                if pain_level_int < 0 or pain_level_int > 10:
                    problematic_fields.append(f"pain_level fuera de rango: {treatment.pain_level}")
            except (ValueError, TypeError):
                problematic_fields.append(f"pain_level no es número: {treatment.pain_level}")
        
        # Verificar campos de evaluación
        if treatment.evaluation_data:
            print(f"\n   Evaluation Data: {treatment.evaluation_data}")
        
        if treatment.trigger_points:
            print(f"   Trigger Points: {treatment.trigger_points}")
        
        if treatment.body_chart_url:
            print(f"   Body Chart URL: {treatment.body_chart_url}")
        
        if problematic_fields:
            print(f"\n⚠️ POSIBLES PROBLEMAS:")
            for issue in problematic_fields:
                print(f"   - {issue}")
        else:
            print(f"\n✅ No se detectaron problemas obvios en los datos")
        
        # Intentar recrear el mapped_treatment como en la función
        try:
            mapped_treatment = {
                'id': treatment.id,
                'created_at': treatment.created_at,
                'description': treatment.treatment_type,
                'progress_notes': treatment.notes,
                'treatment_type': treatment.treatment_type,
                'notes': treatment.notes,
                'status': treatment.status,
                'patient_id': treatment.patient_id,
                'pain_level': treatment.pain_level,
                'movement_restriction': treatment.movement_restriction,
                'assessment': treatment.assessment,
                'provider': treatment.provider,
                'body_chart_url': treatment.body_chart_url,
                'trigger_points': treatment.trigger_points,
                'evaluation_data': treatment.evaluation_data
            }
            print(f"\n✅ mapped_treatment se creó sin errores")
            
            # Verificar si algún campo es problemático para el template
            for key, value in mapped_treatment.items():
                if value is None:
                    print(f"   - {key}: None")
                elif isinstance(value, str) and len(value) > 100:
                    print(f"   - {key}: String muy largo ({len(value)} chars)")
                    
        except Exception as e:
            print(f"\n❌ ERROR al crear mapped_treatment: {e}")
        
        print(f"\n✅ DIAGNÓSTICO COMPLETADO")

if __name__ == "__main__":
    main() 