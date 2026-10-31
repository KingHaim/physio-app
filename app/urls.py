"""Absolute public URLs from APP_BASE_URL, never from the request Host.

Building _external URLs from request.host (or ProxyFix X-Forwarded-Host)
lets an attacker point verification emails, OAuth redirect_uri, Calendar
callbacks and Stripe return URLs at their own domain.

Works inside an app context with no request (CLI / cron), by binding
the URL map to APP_BASE_URL instead of Flask's SERVER_NAME.
"""
from urllib.parse import urlparse

from flask import current_app, has_request_context, url_for
from werkzeug.sansio.utils import host_is_trusted


def app_base_url():
    base = (current_app.config.get('APP_BASE_URL') or '').strip().rstrip('/')
    if not base:
        raise RuntimeError(
            'APP_BASE_URL is not configured. Set it to the public origin '
            '(production default is https://www.trxck.tech).'
        )
    return base


def _relative_path(endpoint, values):
    """Build a path for endpoint without using the request Host."""
    if has_request_context():
        path = url_for(endpoint, **values)
    else:
        parsed = urlparse(app_base_url())
        adapter = current_app.url_map.bind(
            parsed.netloc,
            url_scheme=parsed.scheme or 'https',
            script_name=current_app.config.get('APPLICATION_ROOT') or '/',
        )
        path = adapter.build(endpoint, dict(values), force_external=False)
    if path.startswith(('http://', 'https://')):
        parsed_path = urlparse(path)
        path = parsed_path.path
        if parsed_path.query:
            path = f'{path}?{parsed_path.query}'
    return path


def absolute_url(endpoint, **values):
    """Build an absolute URL for emails, OAuth, Calendar, and Stripe.

    Safe from a CLI or background job that only has an app context.
    """
    values.pop('_external', None)
    values.pop('_scheme', None)
    return f'{app_base_url()}{_relative_path(endpoint, values)}'


def require_production_app_base_url(app):
    """Refuse to start if APP_BASE_URL is not https:// on a trusted host."""
    base = (app.config.get('APP_BASE_URL') or '').strip()
    parsed = urlparse(base)
    if parsed.scheme != 'https' or not parsed.hostname:
        raise RuntimeError(
            'APP_BASE_URL must be an https:// origin in production '
            f'(got {base!r}).'
        )
    trusted = app.config.get('TRUSTED_HOSTS') or []
    if not host_is_trusted(parsed.netloc, trusted):
        raise RuntimeError(
            f'APP_BASE_URL host {parsed.hostname!r} must be listed in '
            f'TRUSTED_HOSTS {list(trusted)!r}.'
        )
