#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import psycopg2
import psycopg2.extras
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
DB_PATH = 'instance/physio.db'
DATABASE_URL = os.environ.get('DATABASE_URL')
API_ENDPOINT = os.environ.get('DEEPSEEK_API_ENDPOINT', 'https://api.deepseek.com/v1/chat/completions')
API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

def get_db_connection():
    """Get database connection - PostgreSQL if DATABASE_URL is set, otherwise SQLite."""
    if DATABASE_URL:
        # PostgreSQL connection for production
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn, 'postgresql'
    else:
        # SQLite connection for local development
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'

def get_patient_data(patient_id):
    """Get patient data from the database."""
    conn, db_type = get_db_connection()
    
    if db_type == 'postgresql':
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        placeholder = '%s'
    else:
        cursor = conn.cursor()
        placeholder = '?'
    
    # Get patient information along with user details
    cursor.execute(f"""
        SELECT p.*, u.first_name, u.last_name, u.license_number, u.clinic_name
        FROM patient p
        JOIN "user" u ON p.user_id = u.id
        WHERE p.id = {placeholder}
    """, (patient_id,))
    patient = cursor.fetchone()
    
    if not patient:
        print(f"Error: Patient with ID {patient_id} not found.")
        conn.close()
        return None, None, None
    
    # Get all treatments for this patient
    cursor.execute(f"""
        SELECT t.*, p.name as patient_name, p.diagnosis, p.treatment_plan
        FROM treatment t
        JOIN patient p ON t.patient_id = p.id
        WHERE t.patient_id = {placeholder}
        ORDER BY t.created_at
    """, (patient_id,))
    
    treatments = cursor.fetchall()
    
    # Get trigger points for all treatments
    treatments_with_points = []
    for treatment in treatments:
        cursor.execute(f"""
            SELECT * FROM trigger_point
            WHERE treatment_id = {placeholder}
        """, (treatment['id'],))
        trigger_points = cursor.fetchall()
        
        # Convert treatment row to dict
        if db_type == 'postgresql':
            treatment_dict = dict(treatment)
            treatment_dict['trigger_points'] = [dict(tp) for tp in trigger_points]
        else:
            treatment_dict = {key: treatment[key] for key in treatment.keys()}
            treatment_dict['trigger_points'] = [dict(tp) for tp in trigger_points]
        treatments_with_points.append(treatment_dict)
    
    # Print all treatments for debugging
    print(f"Treatments for patient {patient['name']}:")
    for treatment in treatments_with_points:
        print(f"Treatment Created At: {treatment['created_at']}")
    
    # Print current date and time
    print(f"Patient: {patient['name']}, ID: {patient_id}")
    now = datetime.now()
    print(f"Today: {now}")
    
    # Double-check with a direct query
    cursor.execute(f"""
        SELECT COUNT(*) as count FROM treatment
        WHERE patient_id = {placeholder}
    """, (patient_id,))
    count = cursor.fetchone()['count']
    print(f"Direct query found {count} treatments for patient {patient_id}")
    
    # Get details for a few treatments
    cursor.execute(f"""
        SELECT id, treatment_type, created_at, status
        FROM treatment
        WHERE patient_id = {placeholder}
        ORDER BY created_at
    """, (patient_id,))
    
    treatments_details = cursor.fetchall()
    for t in treatments_details:
        print(f"Direct treatment: ID={t['id']}, Type={t['treatment_type']}, Date={t['created_at']}, Status={t['status']}")
    
    conn.close()
    
    patient_dict = dict(patient)
    
    # Extract user information for signature
    user_info = {
        'first_name': patient['first_name'],
        'last_name': patient['last_name'],
        'license_number': patient['license_number'],
        'clinic_name': patient['clinic_name']
    }
    
    return patient_dict, treatments_with_points, user_info

def format_treatment_history(patient, treatments, user_info):
    """Format treatment history for the DeepSeek prompt."""
    # Extract initial and latest pain levels if available
    initial_pain = None
    latest_pain = None
    
    for t in treatments:
        if t['pain_level'] is not None:
            if initial_pain is None:
                initial_pain = t['pain_level']
            latest_pain = t['pain_level']
    
    # Calculate treatment duration
    first_date = None
    last_date = None
    if treatments:
        created_at = treatments[0]['created_at']
        if isinstance(created_at, str):
            first_date = datetime.fromisoformat(created_at.replace(' ', 'T'))
        else:
            first_date = created_at
            
        created_at = treatments[-1]['created_at']
        if isinstance(created_at, str):
            last_date = datetime.fromisoformat(created_at.replace(' ', 'T'))
        else:
            last_date = created_at
    
    treatment_duration = None
    if first_date and last_date:
        duration_days = (last_date - first_date).days
        if duration_days < 7:
            treatment_duration = f"{duration_days} days"
        elif duration_days < 30:
            treatment_duration = f"{duration_days // 7} weeks, {duration_days % 7} days"
        else:
            treatment_duration = f"{duration_days // 30} months, {(duration_days % 30) // 7} weeks"
    
    # Create the prompt (anonymized)
    prompt = f"""
    # ANONYMIZED CLINICAL INFORMATION
    - Diagnosis: {patient['diagnosis']}
    - Treatment Plan: {patient['treatment_plan']}
    - Total Treatment Sessions: {len(treatments)}
    - Treatment Duration: {treatment_duration or 'N/A'}
    - Initial Pain Level: {initial_pain or 'Not recorded'}
    - Latest Pain Level: {latest_pain or 'Not recorded'}
    
    # DETAILED TREATMENT HISTORY
    """
    
    for idx, t in enumerate(treatments, 1):
        # Format date string if needed
        if isinstance(t['created_at'], str):
            created_at = datetime.fromisoformat(t['created_at'].replace(' ', 'T'))
            session_date = created_at.strftime('%Y-%m-%d')
        else:
            session_date = t['created_at'].strftime('%Y-%m-%d')
            
        prompt += f"""
    ## Session {idx}: {session_date}
    - Treatment Type: {t['treatment_type']}
    - Progress Notes: {t['notes'] or 'None'}
    - Pain Level: {t['pain_level'] or 'Not recorded'} / 10
    - Movement Restriction: {t['movement_restriction'] or 'None recorded'}
    - Status: {t['status']}
    """
        
        # Include trigger point information if available
        if t['trigger_points']:
            prompt += "\n    - Trigger Points:\n"
            for tp in t['trigger_points']:
                prompt += f"      * {tp.get('muscle', 'Unspecified muscle')} (Intensity: {tp.get('intensity', 'N/A')}/10, Type: {tp.get('type', 'unspecified')})\n"
                if tp.get('symptoms'):
                    prompt += f"        Symptoms: {tp['symptoms']}\n"
    
    prompt += """
    # REPORT GENERATION INSTRUCTIONS
    
    As a professional physiotherapist, please generate a comprehensive physiotherapy treatment progress report based on the above information. The report should include:
    
    IMPORTANT: Do NOT include any patient header information, patient names, diagnosis summary, report dates, or physiotherapist information at the beginning of the report. Start directly with the clinical content.
    
    1. CLINICAL OVERVIEW: Brief introduction to the presenting condition based on the diagnosis
    
    2. CLINICAL ASSESSMENT:
       - Initial assessment findings and baseline measurements
       - Key impairments identified
       - Functional limitations observed
    
    3. TREATMENT APPROACH:
       - Overview of physiotherapy interventions provided
       - Specific techniques and modalities used
       - Progression of treatment over time
    
    4. PROGRESS EVALUATION:
       - Changes in pain levels with detailed comparison between initial and current state
       - Improvements in range of motion and functional capacity
       - Response to specific treatment techniques
    
    5. CURRENT STATUS:
       - Present physical condition
       - Remaining impairments and functional limitations
       - Self-management capabilities
    
    6. RECOMMENDATIONS:
       - Required further treatment (if applicable)
       - Home exercise program suggestions
       - Activity modifications and ergonomic advice
       - Preventative strategies to avoid recurrence
    
    7. PROGNOSIS:
       - Expected timeline for full recovery
       - Factors potentially influencing recovery
       - Long-term outlook
    
    Format the report with clear markdown headings, bullet points, and short paragraphs for optimal readability. Use physiotherapy-specific terminology while ensuring the report remains accessible to the patient and other healthcare providers.
    
    End the report with:
    
    ---
    
    **Report prepared by:**
    """
    
    # Build practitioner signature section flexibly
    practitioner_info = []
    
    # Add name if available
    if user_info.get('first_name') or user_info.get('last_name'):
        name_parts = []
        if user_info.get('first_name'):
            name_parts.append(user_info['first_name'])
        if user_info.get('last_name'):
            name_parts.append(user_info['last_name'])
        practitioner_info.append(f"**{' '.join(name_parts)}, Physiotherapist**")
    else:
        practitioner_info.append("**Physiotherapist**")
    
    # Add professional registration if available
    license_info = []
    if user_info.get('license_number'):
        license_info.append(f"License: {user_info['license_number']}")
    if user_info.get('college_acronym'):
        license_info.append(f"College: {user_info['college_acronym']}")
    
    if license_info:
        practitioner_info.append(" | ".join(license_info))
    
    # Add clinic name if available
    if user_info.get('clinic_name') and user_info['clinic_name'] != 'Independent Practice':
        practitioner_info.append(user_info['clinic_name'])
    
    # Add report date
    practitioner_info.append(f"Report Date: {datetime.now().strftime('%Y-%m-%d')}")
    
    # Join all available information
    prompt += "\n".join(practitioner_info)
    prompt += "\n"
    
    return prompt

def generate_report(patient_id):
    """Generate a report for the specified patient."""
    print(f"Generating report for patient {patient_id}...")
    
    # Get patient data
    patient, treatments, user_info = get_patient_data(patient_id)
    
    if not patient:
        return False, "Patient not found"
    
    if not treatments:
        return False, "No treatments found for this patient"
    
    # Format treatment history
    prompt = format_treatment_history(patient, treatments, user_info)
    
    # Check if API key is available
    if not API_KEY:
        return False, "DeepSeek API key not configured. Please set DEEPSEEK_API_KEY environment variable or add it to .env file."
    
    try:
        # Call DeepSeek API
        print(f"Calling DeepSeek API at {API_ENDPOINT}...")
        
        response = requests.post(
            API_ENDPOINT,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a professional physiotherapist with expertise in creating detailed, evidence-based treatment progress reports. You use precise physiotherapy terminology while ensuring your reports remain clear and accessible."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 4000
            },
            timeout=90
        )
        
        print(f"API response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return False, f"API error: {response.text}"
        
        # Parse the response
        result = response.json()
        report_content = result['choices'][0]['message']['content']
        
        # Sanitize report content - remove any instances of patient name
        if patient['name'] and len(patient['name']) > 2:  # Only replace if we have a valid name
            report_content = report_content.replace(patient['name'], "Patient")
        
        # Save the report to the database
        save_conn, save_db_type = get_db_connection()
        
        if save_db_type == 'postgresql':
            save_cursor = save_conn.cursor()
            save_placeholder = '%s'
        else:
            save_cursor = save_conn.cursor()
            save_placeholder = '?'
        
        save_cursor.execute(f"""
            INSERT INTO patient_reports (patient_id, content, generated_date, report_type)
            VALUES ({save_placeholder}, {save_placeholder}, {save_placeholder}, {save_placeholder})
        """, (patient_id, report_content, datetime.now().isoformat(), "AI Generated (CLI)"))
        
        if save_db_type == 'postgresql':
            save_cursor.execute("SELECT lastval()")
            report_id = save_cursor.fetchone()[0]
        else:
            report_id = save_cursor.lastrowid
            
        save_conn.commit()
        save_conn.close()
        
        # Save the report to a file
        report_filename = f"report_{patient_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_filename, 'w') as f:
            f.write(report_content)
        
        print(f"Report generated successfully and saved to {report_filename}")
        print(f"Report ID in database: {report_id}")
        
        return True, report_content
        
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        return False, str(e)

def delete_report(report_id):
    """Delete a patient report by its ID."""
    print(f"Deleting report with ID {report_id}...")
    
    # Connect to the database
    conn, db_type = get_db_connection()
    
    if db_type == 'postgresql':
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        placeholder = '%s'
    else:
        cursor = conn.cursor()
        placeholder = '?'
    
    try:
        # First check if the report exists
        cursor.execute(f"SELECT id, patient_id FROM patient_reports WHERE id = {placeholder}", (report_id,))
        report = cursor.fetchone()
        
        if not report:
            conn.close()
            return False, f"Report with ID {report_id} not found."
        
        # Get the patient ID for informational purposes
        if db_type == 'postgresql':
            patient_id = report['patient_id']
        else:
            patient_id = report[1]
        
        # Delete the report
        cursor.execute(f"DELETE FROM patient_reports WHERE id = {placeholder}", (report_id,))
        conn.commit()
        
        print(f"Report {report_id} for patient {patient_id} successfully deleted.")
        conn.close()
        return True, f"Report {report_id} successfully deleted."
    
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error deleting report: {str(e)}")
        return False, str(e)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python generate_patient_report.py generate <patient_id>  - Generate a new report")
        print("  python generate_patient_report.py delete <report_id>     - Delete a report")
        print("  python generate_patient_report.py list <patient_id>      - List all reports for a patient")
        return 1
    
    command = sys.argv[1]
    
    if command == "generate":
        if len(sys.argv) != 3:
            print("Usage: python generate_patient_report.py generate <patient_id>")
            return 1
        
        try:
            patient_id = int(sys.argv[2])
        except ValueError:
            print("Error: Patient ID must be a number")
            return 1
        
        success, result = generate_report(patient_id)
        
        if success:
            print("\nReport generated successfully!")
            
            # Ask if the report should be displayed
            display = input("Display the generated report? (y/n): ")
            if display.lower() == 'y':
                print("\n" + "="*80)
                print(result)
                print("="*80)
        else:
            print(f"\nError generating report: {result}")
            return 1
    
    elif command == "delete":
        if len(sys.argv) != 3:
            print("Usage: python generate_patient_report.py delete <report_id>")
            return 1
        
        try:
            report_id = int(sys.argv[2])
        except ValueError:
            print("Error: Report ID must be a number")
            return 1
        
        success, result = delete_report(report_id)
        
        if success:
            print(result)
        else:
            print(f"Error: {result}")
            return 1
    
    elif command == "list":
        if len(sys.argv) != 3:
            print("Usage: python generate_patient_report.py list <patient_id>")
            return 1
        
        try:
            patient_id = int(sys.argv[2])
        except ValueError:
            print("Error: Patient ID must be a number")
            return 1
        
        # Connect to the database
        conn, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            placeholder = '%s'
        else:
            cursor = conn.cursor()
            placeholder = '?'
        
        try:
            # Get patient info for display
            cursor.execute(f"SELECT name FROM patient WHERE id = {placeholder}", (patient_id,))
            patient = cursor.fetchone()
            
            if not patient:
                print(f"Error: Patient with ID {patient_id} not found.")
                conn.close()
                return 1
            
            # List all reports for the patient
            cursor.execute(f"""
                SELECT id, report_type, generated_date 
                FROM patient_reports 
                WHERE patient_id = {placeholder}
                ORDER BY generated_date DESC
            """, (patient_id,))
            
            reports = cursor.fetchall()
            
            patient_name = patient['name'] if db_type == 'postgresql' else patient[0]
            
            if not reports:
                print(f"No reports found for patient {patient_name} (ID: {patient_id}).")
                conn.close()
                return 0
            
            print(f"\nReports for patient {patient_name} (ID: {patient_id}):")
            print("-" * 80)
            print(f"{'ID':<5} | {'Type':<20} | {'Generated Date':<30}")
            print("-" * 80)
            
            for report in reports:
                if db_type == 'postgresql':
                    print(f"{report['id']:<5} | {report['report_type']:<20} | {report['generated_date']:<30}")
                else:
                    print(f"{report[0]:<5} | {report[1]:<20} | {report[2]:<30}")
            
            conn.close()
        
        except Exception as e:
            print(f"Error listing reports: {str(e)}")
            conn.close()
            return 1
    
    else:
        print(f"Unknown command: {command}")
        print("Use 'generate', 'delete', or 'list'")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 