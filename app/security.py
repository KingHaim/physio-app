# app/security.py
"""
Security middleware to prevent malicious script injection
"""

from flask import request, abort, current_app
import re

class SecurityMiddleware:
    """Security middleware to block malicious requests"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize security middleware"""
        app.before_request(self.block_malicious_requests)
        app.after_request(self.add_security_headers)
    
    def block_malicious_requests(self):
        """Block requests with malicious patterns"""
        
        # Block requests with suspicious Google Analytics tracking
        if 'G-9Q6H0QETRF' in request.url:
            current_app.logger.warning(f"🚨 Blocked malicious GA request: {request.url}")
            abort(403, description="Suspicious tracking request blocked")
        
        # Block doubleclick.net requests
        if 'doubleclick.net' in request.url:
            current_app.logger.warning(f"🚨 Blocked doubleclick request: {request.url}")
            abort(403, description="Tracking request blocked")
        
        # Block suspicious @ patterns in URLs
        if request.url.startswith('@'):
            current_app.logger.warning(f"🚨 Blocked malformed URL: {request.url}")
            abort(400, description="Malformed URL blocked")
        
        # Block requests with tracking patterns
        suspicious_patterns = [
            r'td\.doubleclick\.net',
            r'google-analytics\.com/collect',
            r'googletagmanager\.com',
            r'@https?://',
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, request.url):
                current_app.logger.warning(f"🚨 Blocked suspicious pattern: {pattern} in {request.url}")
                abort(403, description="Suspicious request blocked")
    
    def add_security_headers(self, response):
        """Add security headers to all responses"""
        
        # Block inline JavaScript execution
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # CSP to block unauthorized scripts
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdn.jsdelivr.net "
            "https://assets.calendly.com "
            "https://js.stripe.com "
            "https://code.jquery.com "
            "https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' "
            "https://cdn.jsdelivr.net "
            "https://fonts.googleapis.com "
            "https://assets.calendly.com; "
            "font-src 'self' "
            "https://fonts.gstatic.com "
            "https://fonts.googleapis.com "
            "https://cdn.jsdelivr.net; "
            "img-src 'self' data: "
            "https://cdn.jsdelivr.net "
            "https://assets.calendly.com "
            "https://trxck.tech; "
            "connect-src 'self' "
            "https://api.calendly.com "
            "https://api.stripe.com "
            "https://hooks.stripe.com; "
            "frame-src 'self' "
            "https://calendly.com "
            "https://js.stripe.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        
        response.headers['Content-Security-Policy'] = csp_policy
        
        return response
