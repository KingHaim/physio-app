"""H6: production cookie flags and removal of /debug/* routes."""
from datetime import timedelta

import pytest

from app import create_app
from config import DevelopmentConfig, ProductionConfig, TestConfig


DEBUG_PATHS = (
    '/debug/session',
    '/debug/patients',
    '/debug/force-welcome',
)


def test_production_config_sets_secure_cookie_flags():
    """Production cookies are Secure, HttpOnly, SameSite=Lax with short lifetimes."""
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
    assert ProductionConfig.SESSION_COOKIE_HTTPONLY is True
    assert ProductionConfig.SESSION_COOKIE_SAMESITE == 'Lax'
    assert ProductionConfig.REMEMBER_COOKIE_SECURE is True
    assert ProductionConfig.REMEMBER_COOKIE_HTTPONLY is True
    assert ProductionConfig.REMEMBER_COOKIE_SAMESITE == 'Lax'
    assert ProductionConfig.PERMANENT_SESSION_LIFETIME == timedelta(hours=12)
    assert ProductionConfig.REMEMBER_COOKIE_DURATION == timedelta(days=14)
    assert ProductionConfig.WTF_CSRF_SSL_STRICT is True
    assert ProductionConfig.SESSION_PROTECTION == 'strong'


def test_create_app_does_not_override_production_cookie_flags():
    """The app factory must not force SESSION_COOKIE_SECURE=False over ProductionConfig."""
    from app import login_manager

    previous_protection = login_manager.session_protection
    try:
        app = create_app(ProductionConfig)
        assert app.config['SESSION_COOKIE_SECURE'] is True
        assert app.config['SESSION_COOKIE_HTTPONLY'] is True
        assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
        assert app.config['REMEMBER_COOKIE_SECURE'] is True
        assert app.config['REMEMBER_COOKIE_HTTPONLY'] is True
        assert app.config['REMEMBER_COOKIE_SAMESITE'] == 'Lax'
        assert app.config['PERMANENT_SESSION_LIFETIME'] == timedelta(hours=12)
        assert app.config['REMEMBER_COOKIE_DURATION'] == timedelta(days=14)
        assert login_manager.session_protection == 'strong'
    finally:
        # login_manager is a process-wide singleton; restore so later tests keep HTTP/dev defaults
        login_manager.session_protection = previous_protection


def test_local_and_test_configs_keep_insecure_cookies_for_http():
    """Local HTTP and pytest clients still send cookies without the Secure flag."""
    assert DevelopmentConfig.SESSION_COOKIE_SECURE is False
    assert DevelopmentConfig.REMEMBER_COOKIE_SECURE is False
    assert TestConfig.SESSION_COOKIE_SECURE is False
    assert TestConfig.REMEMBER_COOKIE_SECURE is False

    test_app = create_app(TestConfig)
    assert test_app.config['SESSION_COOKIE_SECURE'] is False
    assert test_app.config['REMEMBER_COOKIE_SECURE'] is False


@pytest.mark.parametrize('path', DEBUG_PATHS)
def test_debug_routes_return_404(client, path):
    """Removed /debug/* endpoints must 404 rather than leak session data."""
    response = client.get(path)
    assert response.status_code == 404
