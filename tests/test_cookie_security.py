"""H6: production cookie flags, fail-closed env, removed debug routes, logout."""
from datetime import timedelta

import pytest
from flask import request, url_for
from sqlalchemy.pool import StaticPool

from app import create_app, db, login_manager
from app.models import User
from config import DevelopmentConfig, ProductionConfig, TestConfig, resolve_config_name


DEBUG_AND_REMOVED_PATHS = (
    '/debug/session',
    '/debug/patients',
    '/debug/force-welcome',
    '/test_anamnesis',
    '/auth/clear-session',
)

PROD_HOST = 'trxck.tech'
PROD_BASE = f'https://{PROD_HOST}'


class ProductionCookieTestConfig(ProductionConfig):
    """Production cookie/ProxyFix settings with an isolated SQLite DB for tests."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False},
        'poolclass': StaticPool,
    }


def _cookie_headers(response, name):
    return [
        header
        for header in response.headers.getlist('Set-Cookie')
        if header.lower().startswith(name.lower() + '=')
    ]


def _assert_secure_cookie_flags(header):
    assert header, 'expected a Set-Cookie header'
    parts = {part.strip().lower() for part in header.split(';')}
    assert 'secure' in parts, header
    assert 'httponly' in parts, header
    assert 'samesite=lax' in parts, header


def _make_prod_app():
    previous = login_manager.session_protection
    app = create_app(ProductionCookieTestConfig)
    with app.app_context():
        db.create_all()
    return app, previous


def _create_verified_physio(app, email='physio_cookie@example.com', password='password123'):
    with app.app_context():
        user = User(
            username=email,
            email=email,
            role='physio',
            email_verified=True,
            is_new_user=False,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


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
    assert ProductionConfig.SESSION_PROTECTION == 'basic'


def test_create_app_does_not_override_production_cookie_flags():
    """The app factory must not force SESSION_COOKIE_SECURE=False over ProductionConfig."""
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
        assert login_manager.session_protection == 'basic'
    finally:
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


def test_unset_env_defaults_to_production(monkeypatch):
    """An unset FLASK_ENV/APP_ENV must not fall back to insecure development cookies."""
    monkeypatch.delenv('FLASK_ENV', raising=False)
    monkeypatch.delenv('APP_ENV', raising=False)
    assert resolve_config_name() == 'production'
    app = create_app()
    assert app.config['SESSION_COOKIE_SECURE'] is True
    assert app.config['REMEMBER_COOKIE_SECURE'] is True
    assert app.config['DEBUG'] is False
    assert app.config['SQLALCHEMY_ECHO'] is False


@pytest.mark.parametrize('value', ['staging', 'prodction', 'dev', 'PROD'])
def test_unknown_env_refuses_to_start(monkeypatch, value):
    monkeypatch.setenv('FLASK_ENV', value)
    with pytest.raises(RuntimeError, match='Unknown environment'):
        create_app()


def test_env_value_is_stripped_and_lowercased(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', '  TeStInG  ')
    app = create_app()
    assert app.config['TESTING'] is True
    assert app.config['SESSION_COOKIE_SECURE'] is False


def test_app_env_alias_when_flask_env_unset(monkeypatch):
    monkeypatch.delenv('FLASK_ENV', raising=False)
    monkeypatch.setenv('APP_ENV', 'testing')
    assert resolve_config_name() == 'testing'


def test_production_refuses_insecure_session_cookie():
    class InsecureProduction(ProductionConfig):
        SESSION_COOKIE_SECURE = False

    with pytest.raises(RuntimeError, match='SESSION_COOKIE_SECURE'):
        create_app(InsecureProduction)


def test_production_login_set_cookie_headers_are_secure():
    """Real Set-Cookie flags on session and remember cookies under production + HTTPS."""
    app, previous = _make_prod_app()
    try:
        _create_verified_physio(app)
        client = app.test_client()
        response = client.post(
            '/auth/login',
            data={
                'email': 'physio_cookie@example.com',
                'password': 'password123',
                'remember_me': 'y',
            },
            base_url=PROD_BASE,
            follow_redirects=False,
        )
        assert response.status_code in (302, 200)
        session_headers = _cookie_headers(response, 'session')
        remember_headers = _cookie_headers(response, 'remember_token')
        assert session_headers, response.headers.getlist('Set-Cookie')
        assert remember_headers, response.headers.getlist('Set-Cookie')
        _assert_secure_cookie_flags(session_headers[0])
        _assert_secure_cookie_flags(remember_headers[0])
    finally:
        login_manager.session_protection = previous


def test_remember_me_survives_missing_session_cookie_on_prod_https():
    """Drop session, keep remember_token, GET /patients 3 times.

    With SESSION_PROTECTION='strong' the 2nd request 302s to login and deletes
    remember_token. With 'basic' all 3 return 200.
    """
    app, previous = _make_prod_app()
    try:
        _create_verified_physio(app)
        client = app.test_client()
        login = client.post(
            '/auth/login',
            data={
                'email': 'physio_cookie@example.com',
                'password': 'password123',
                'remember_me': 'y',
            },
            base_url=PROD_BASE,
            follow_redirects=False,
        )
        assert login.status_code in (302, 200)
        assert client.get_cookie('remember_token', domain=PROD_HOST) is not None

        client.delete_cookie('session', domain=PROD_HOST)
        assert client.get_cookie('session', domain=PROD_HOST) is None

        statuses = []
        for _ in range(3):
            response = client.get('/patients', base_url=PROD_BASE, follow_redirects=False)
            statuses.append(response.status_code)
        assert statuses == [200, 200, 200], statuses
        assert client.get_cookie('remember_token', domain=PROD_HOST) is not None
    finally:
        login_manager.session_protection = previous


def test_remember_cookie_deletion_keeps_secure_flags():
    app, previous = _make_prod_app()
    try:
        _create_verified_physio(app)
        client = app.test_client()
        client.post(
            '/auth/login',
            data={
                'email': 'physio_cookie@example.com',
                'password': 'password123',
                'remember_me': 'y',
            },
            base_url=PROD_BASE,
            follow_redirects=False,
        )
        response = client.post('/auth/logout', base_url=PROD_BASE, follow_redirects=False)
        remember_headers = _cookie_headers(response, 'remember_token')
        assert remember_headers, response.headers.getlist('Set-Cookie')
        _assert_secure_cookie_flags(remember_headers[0])
    finally:
        login_manager.session_protection = previous


@pytest.mark.parametrize('path', DEBUG_AND_REMOVED_PATHS)
def test_debug_routes_return_404(client, path):
    """Removed /debug/*, /test_anamnesis and /auth/clear-session must 404."""
    response = client.get(path)
    assert response.status_code == 404


def test_logout_get_not_allowed(client):
    response = client.get('/auth/logout')
    assert response.status_code == 405


def test_logout_post_logs_out(client, app):
    with app.app_context():
        user = User(
            username='logout_user@example.com',
            email='logout_user@example.com',
            role='physio',
            email_verified=True,
            is_new_user=False,
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()

    client.post(
        '/auth/login',
        data={'email': 'logout_user@example.com', 'password': 'password123'},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        assert sess.get('_user_id')

    response = client.post('/auth/logout', follow_redirects=False)
    assert response.status_code in (302, 200)
    with client.session_transaction() as sess:
        assert sess.get('_user_id') is None


def test_proxyfix_x_forwarded_proto_makes_request_secure():
    """ProxyFix (x_for=1, x_proto=1, x_host=1) trusts one PythonAnywhere hop."""
    app, previous = _make_prod_app()
    try:
        @app.route('/_secure_probe')
        def _secure_probe():
            return {
                'is_secure': request.is_secure,
                'host': request.host,
                'url': url_for('_secure_probe', _external=True),
            }

        client = app.test_client()
        response = client.get(
            '/_secure_probe',
            headers={
                'X-Forwarded-Proto': 'https',
                'X-Forwarded-Host': 'www.trxck.tech',
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['is_secure'] is True
        assert data['host'] == 'www.trxck.tech'
        assert data['url'].startswith('https://')
    finally:
        login_manager.session_protection = previous
