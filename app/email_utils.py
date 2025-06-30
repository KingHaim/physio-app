"""
Email utilities for sending verification emails and other notifications
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, url_for
import logging

def send_email(to_email, subject, html_body, text_body=None):
    """Send an email"""
    try:
        # For development, log instead of sending
        current_app.logger.info(f"""
========== EMAIL WOULD BE SENT ==========
To: {to_email}
Subject: {subject}
HTML Body: {html_body[:200]}...
==========================================
        """)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {str(e)}")
        return False

def send_verification_email(user):
    """Send email verification email to user"""
    token = user.generate_email_verification_token()
    verification_url = url_for('auth.verify_email', token=token, _external=True)
    subject = "Verifica tu email - TRXCKER PhysioApp"
    
    html_body = f"""
    <h1>TRXCKER PhysioApp</h1>
    <h2>Verifica tu email</h2>
    <p>Hola {user.email},</p>
    <p>Haz clic en el siguiente enlace para verificar tu email:</p>
    <a href="{verification_url}" style="background-color: #0d6efd; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verificar Email</a>
    <p>Este enlace expira en 24 horas.</p>
    """
    
    return send_email(user.email, subject, html_body)

def send_welcome_email(user):
    """Send welcome email after verification"""
    subject = "¡Bienvenido a TRXCKER!"
    
    html_body = f"""
    <h1>¡Bienvenido a TRXCKER!</h1>
    <p>Tu email {user.email} ha sido verificado exitosamente.</p>
    <p>Ya puedes usar todas las funcionalidades de la plataforma.</p>
    """
    
    return send_email(user.email, subject, html_body)
