"""Absolute public URLs from APP_BASE_URL, never from the request Host.

Building _external URLs from request.host (or ProxyFix X-Forwarded-Host)
lets an attacker point verification emails, OAuth redirect_uri, Calendar
callbacks and Stripe return URLs at their own domain.
"""
from flask import current_app, url_for


def app_base_url():
    base = (current_app.config.get('APP_BASE_URL') or '').strip().rstrip('/')
    if not base:
        raise RuntimeError(
            'APP_BASE_URL is not configured. Set it to the public origin '
            '(production default is https://www.trxck.tech).'
        )
    return base


def absolute_url(endpoint, **values):
    """Build an absolute URL for emails, OAuth, Calendar, and Stripe."""
    values.pop('_external', None)
    values.pop('_scheme', None)
    path = url_for(endpoint, **values)
    return f'{app_base_url()}{path}'
