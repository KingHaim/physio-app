"""
Email utilities for sending verification emails and other notifications
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, url_for
import logging

def send_email(to_email, subject, html_body, text_body=None):
    """Send an email using SMTP"""
    try:
        # Check if email configuration is available
        mail_server = current_app.config.get('MAIL_SERVER')
        mail_username = current_app.config.get('MAIL_USERNAME')
        mail_password = current_app.config.get('MAIL_PASSWORD')
        
        if not all([mail_server, mail_username, mail_password]):
            # Fall back to logging if not configured
            current_app.logger.info(f"""
========== EMAIL WOULD BE SENT (NO SMTP CONFIG) ==========
To: {to_email}
Subject: {subject}
HTML Body: {html_body[:200]}...
=========================================================
            """)
            return True
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = current_app.config.get('MAIL_SUBJECT_PREFIX', '') + subject
        msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER', mail_username)
        msg['To'] = to_email
        
        # Create text and HTML parts
        if text_body:
            part1 = MIMEText(text_body, 'plain')
            msg.attach(part1)
        
        part2 = MIMEText(html_body, 'html')
        msg.attach(part2)
        
        # Send email
        mail_port = current_app.config.get('MAIL_PORT', 587)
        mail_use_tls = current_app.config.get('MAIL_USE_TLS', True)
        
        server = smtplib.SMTP(mail_server, mail_port)
        
        if mail_use_tls:
            server.starttls()
        
        server.login(mail_username, mail_password)
        text = msg.as_string()
        server.sendmail(mail_username, to_email, text)
        server.quit()
        
        current_app.logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

def send_verification_email(user):
    """Send email verification email to user"""
    token = user.generate_email_verification_token()
    verification_url = url_for('auth.verify_email', token=token, _external=True)
    subject = "Verifica tu email - TRXCKER"
    
    # Get user's name or use a generic greeting
    user_name = user.first_name if user.first_name else "Usuario"
    
    text_body = f"""
Hola {user_name},

Gracias por registrarte en TRXCKER!

Para completar tu registro, por favor verifica tu dirección de email haciendo clic en el siguiente enlace:

{verification_url}

Este enlace expirará en 24 horas.

Si no te registraste en TRXCKER, puedes ignorar este email.

Saludos,
El equipo de TRXCKER
    """
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #0d6efd; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .button {{ 
                background-color: #0d6efd !important; 
                color: #ffffff !important; 
                padding: 15px 30px !important; 
                text-decoration: none !important; 
                border-radius: 8px !important; 
                display: inline-block !important; 
                margin: 20px 0 !important; 
                font-weight: bold !important;
                font-size: 16px !important;
                border: 2px solid #0d6efd !important;
                text-align: center !important;
            }}
            a.button {{ color: #ffffff !important; }}
            a.button:visited {{ color: #ffffff !important; }}
            a.button:hover {{ 
                color: #ffffff !important; 
                background-color: #0b5ed7 !important; 
                border-color: #0b5ed7 !important; 
            }}
            a.button:active {{ color: #ffffff !important; }}
            .footer {{ background-color: #f8f9fa; padding: 15px; text-align: center; color: #6c757d; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>TRXCKER</h1>
        </div>
        <div class="content">
            <h2>¡Bienvenido a TRXCKER!</h2>
            <p>Hola <strong>{user_name}</strong>,</p>
            <p>Gracias por registrarte en TRXCKER. Para completar tu registro y acceder a todas las funcionalidades, necesitas verificar tu dirección de email.</p>
            <p>Haz clic en el siguiente botón para verificar tu email:</p>
            <a href="{verification_url}" class="button">✅ Verificar Email</a>
            <p>También puedes copiar y pegar este enlace en tu navegador:</p>
            <p><small>{verification_url}</small></p>
            <p><strong>Importante:</strong> Este enlace expira en 24 horas.</p>
            <p>Si no te registraste en TRXCKER, puedes ignorar este email.</p>
        </div>
        <div class="footer">
            <p>TRXCKER - Tu plataforma de gestión de fisioterapia</p>
            <p>Este es un email automático, por favor no respondas a esta dirección.</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user.email, subject, html_body, text_body)

def send_welcome_email(user):
    """Send welcome email after verification"""
    subject = "¡Bienvenido a TRXCKER!"
    
    # Get user's name or use a generic greeting
    user_name = user.first_name if user.first_name else "Usuario"
    
    text_body = f"""
¡Hola {user_name}!

¡Tu email ha sido verificado exitosamente!

Ya puedes acceder a todas las funcionalidades de TRXCKER:
- Gestión de pacientes
- Calendario de citas
- Reportes y análisis
- Y mucho más...

Accede a tu cuenta: {url_for('auth.login', _external=True)}

¡Bienvenido a TRXCKER!

El equipo de TRXCKER
    """
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #28a745; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .button {{ 
                background-color: #0d6efd !important; 
                color: #ffffff !important; 
                padding: 15px 30px !important; 
                text-decoration: none !important; 
                border-radius: 8px !important; 
                display: inline-block !important; 
                margin: 20px 0 !important; 
                font-weight: bold !important;
                font-size: 16px !important;
                border: 2px solid #0d6efd !important;
                text-align: center !important;
            }}
            a.button {{ color: #ffffff !important; }}
            a.button:visited {{ color: #ffffff !important; }}
            a.button:hover {{ 
                color: #ffffff !important; 
                background-color: #0b5ed7 !important; 
                border-color: #0b5ed7 !important; 
            }}
            a.button:active {{ color: #ffffff !important; }}
            .features {{ background-color: #f8f9fa; padding: 15px; border-left: 4px solid #28a745; margin: 20px 0; }}
            .footer {{ background-color: #f8f9fa; padding: 15px; text-align: center; color: #6c757d; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>¡Bienvenido a TRXCKER!</h1>
        </div>
        <div class="content">
            <p>¡Hola <strong>{user_name}</strong>!</p>
            <p>🎉 <strong>¡Tu email ha sido verificado exitosamente!</strong></p>
            <p>Ya puedes acceder a todas las funcionalidades de TRXCKER.</p>
            
            <div class="features">
                <h3>¿Qué puedes hacer ahora?</h3>
                <ul>
                    <li>✅ Gestionar pacientes y expedientes</li>
                    <li>📅 Organizar tu calendario de citas</li>
                    <li>📊 Generar reportes y análisis</li>
                    <li>💼 Configurar tu clínica</li>
                    <li>🔧 Personalizar tu cuenta</li>
                </ul>
            </div>
            
            <p>¡Comienza ahora!</p>
            <a href="{url_for('auth.login', _external=True)}" class="button">🚀 Acceder a mi Cuenta</a>
            
            <p>Si tienes alguna pregunta o necesitas ayuda, no dudes en contactarnos.</p>
        </div>
        <div class="footer">
            <p>TRXCKER - Tu plataforma de gestión fisioterapéutica</p>
            <p>Este es un email automático, por favor no respondas a esta dirección.</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user.email, subject, html_body, text_body)

def send_trial_reminder_email(user, days_remaining):
    """Send trial reminder email to user"""
    subject = f"Your TRXCKER trial expires in {days_remaining} days"
    
    # Get user's name or use a generic greeting
    user_name = user.first_name if user.first_name else "User"
    
    # Customize message based on days remaining
    if days_remaining == 7:
        urgency = "Just a friendly reminder"
        urgency_class = "info"
        urgency_icon = "🔔"
    elif days_remaining == 2:
        urgency = "Important reminder"
        urgency_class = "warning"
        urgency_icon = "⚠️"
    elif days_remaining == 1:
        urgency = "Final reminder"
        urgency_class = "danger"
        urgency_icon = "🚨"
    else:
        urgency = "Trial reminder"
        urgency_class = "info"
        urgency_icon = "🔔"
    
    # Get plan name
    plan_name = user.active_plan.name if user.active_plan else "plan"
    
    text_body = f"""
Hello {user_name},

{urgency_icon} {urgency}: Your TRXCKER {plan_name} trial expires in {days_remaining} day{'s' if days_remaining != 1 else ''}.

To continue using all the features you've been enjoying, please upgrade to a paid plan before your trial ends.

Your current {plan_name} trial includes:
- Patient management with encrypted records
- AI-powered treatment reports
- Appointment scheduling
- Financial reporting
- And much more!

Upgrade now to continue without interruption:
{url_for('main.manage_subscription', _external=True)}

Questions? We're here to help - just reply to this email.

Best regards,
The TRXCKER Team
    """
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #0d6efd; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .alert {{ 
                padding: 15px;
                margin: 20px 0;
                border-radius: 8px;
                border: 1px solid;
            }}
            .alert-{urgency_class} {{ 
                background-color: {'#fff3cd' if urgency_class == 'warning' else '#f8d7da' if urgency_class == 'danger' else '#d1ecf1'};
                border-color: {'#ffeaa7' if urgency_class == 'warning' else '#f5c6cb' if urgency_class == 'danger' else '#bee5eb'};
                color: {'#856404' if urgency_class == 'warning' else '#721c24' if urgency_class == 'danger' else '#0c5460'};
            }}
            .button {{ 
                background-color: #0d6efd !important; 
                color: #ffffff !important; 
                padding: 15px 30px !important; 
                text-decoration: none !important; 
                border-radius: 8px !important; 
                display: inline-block !important; 
                margin: 20px 0 !important; 
                font-weight: bold !important;
                font-size: 16px !important;
                border: 2px solid #0d6efd !important;
                text-align: center !important;
            }}
            .button-urgent {{ 
                background-color: #dc3545 !important; 
                border-color: #dc3545 !important;
            }}
            a.button {{ color: #ffffff !important; }}
            a.button:visited {{ color: #ffffff !important; }}
            a.button:hover {{ 
                color: #ffffff !important; 
                background-color: #0b5ed7 !important; 
                border-color: #0b5ed7 !important; 
            }}
            .features {{ 
                background-color: #f8f9fa; 
                padding: 15px; 
                border-left: 4px solid #0d6efd; 
                margin: 20px 0; 
            }}
            .footer {{ 
                background-color: #f8f9fa; 
                padding: 15px; 
                text-align: center; 
                color: #6c757d; 
                font-size: 0.9em; 
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>TRXCKER</h1>
        </div>
        <div class="content">
            <div class="alert alert-{urgency_class}">
                <h3>{urgency_icon} {urgency}</h3>
                <p><strong>Your TRXCKER {plan_name} trial expires in {days_remaining} day{'s' if days_remaining != 1 else ''}.</strong></p>
            </div>
            
            <p>Hello <strong>{user_name}</strong>,</p>
            
            <p>We hope you've been enjoying your TRXCKER experience! To continue using all the features you've been enjoying, please upgrade to a paid plan before your trial ends.</p>
            
            <div class="features">
                <h3>Your {plan_name} trial includes:</h3>
                <ul>
                    <li>✅ Patient management with encrypted records</li>
                    <li>🤖 AI-powered treatment reports</li>
                    <li>📅 Appointment scheduling</li>
                    <li>💰 Financial reporting</li>
                    <li>⚠️ Beta version - GDPR compliance pending</li>
                    <li>📊 Advanced analytics</li>
                    <li>🔧 API access and integrations</li>
                </ul>
            </div>
            
            <p>Don't lose access to your data and all these powerful features!</p>
            
            <a href="{url_for('main.manage_subscription', _external=True)}" class="button {'button-urgent' if days_remaining <= 2 else ''}">
                🚀 Upgrade Now to Continue
            </a>
            
            <p>Questions? We're here to help - just reply to this email.</p>
            
            <p>Best regards,<br>
            The TRXCKER Team</p>
        </div>
        <div class="footer">
            <p>TRXCKER - Your AI-powered physiotherapy practice management platform</p>
            <p>This is an automated email. You can manage your subscription preferences in your account.</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user.email, subject, html_body, text_body)

def send_trial_reminder_emails():
    """Send trial reminder emails to users who need them"""
    from app.models import User, UserSubscription, db
    from datetime import datetime, timedelta
    
    # Get users who need reminder emails (7, 2, 1 days remaining)
    reminder_configs = [
        {'days': 7, 'field': 'trial_reminder_7_days_sent'},
        {'days': 2, 'field': 'trial_reminder_2_days_sent'},
        {'days': 1, 'field': 'trial_reminder_1_day_sent'}
    ]
    
    total_sent = 0
    
    for config in reminder_configs:
        days = config['days']
        field_name = config['field']
        
        # Calculate the target date range for this reminder
        target_date = datetime.utcnow() + timedelta(days=days)
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Find users whose trial ends on the target date and haven't received this reminder
        users_to_remind = User.query.join(UserSubscription).filter(
            UserSubscription.status == 'trialing',
            UserSubscription.trial_ends_at >= start_of_day,
            UserSubscription.trial_ends_at <= end_of_day,
            getattr(UserSubscription, field_name) == False
        ).all()
        
        for user in users_to_remind:
            try:
                # Send the reminder email
                if send_trial_reminder_email(user, days):
                    # Mark this reminder as sent
                    subscription = user.current_subscription
                    if subscription:
                        setattr(subscription, field_name, True)
                        db.session.commit()
                        total_sent += 1
                        print(f"Sent {days}-day reminder to {user.email}")
                else:
                    print(f"Failed to send {days}-day reminder to {user.email}")
            except Exception as e:
                print(f"Error sending {days}-day reminder to {user.email}: {str(e)}")
    
    print(f"Total trial reminder emails sent: {total_sent}")
    return total_sent
