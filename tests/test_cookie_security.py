"""H6: production cookie flags, fail-closed env, removed debug routes, logout."""
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import pytest
from flask import has_request_context, request, url_for
from sqlalchemy.pool import StaticPool
from werkzeug.test import EnvironBuilder

from app import create_app, db, login_manager
from app.email_utils import send_trial_reminder_emails, send_verification_email
from app.models import Plan, User, UserSubscription
from app.urls import absolute_url
from config import (
    DevelopmentConfig,
    ProductionConfig,
    TestConfig,
    parse_trusted_hosts,
    resolve_config_name,
)


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
    APP_BASE_URL = 'https://www.trxck.tech'
    TRUSTED_HOSTS = ['www.trxck.tech', 'trxck.tech']
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
    assert ProductionConfig.SERVER_NAME is None
    assert not getattr(ProductionConfig, 'SESSION_COOKIE_DOMAIN', None)
    assert ProductionConfig.APP_BASE_URL == 'https://www.trxck.tech'
    assert ProductionConfig.TRUSTED_HOSTS == ['www.trxck.tech', 'trxck.tech']


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
    assert 'localhost' in test_app.config['TRUSTED_HOSTS']
    assert '127.0.0.1' in test_app.config['TRUSTED_HOSTS']
    assert 'localhost' in DevelopmentConfig.TRUSTED_HOSTS
    assert DevelopmentConfig.APP_BASE_URL == 'http://localhost:5002'


def test_unset_env_resolve_config_name_is_production(monkeypatch):
    """resolve_config_name reads the live env; unset → production.

    In-process create_app cannot prove the .flaskenv hole is closed:
    conftest sets FLASK_ENV before import, and config.py already ran
    load_dotenv. Boot-through-dotenv is the subprocess test below.
    """
    monkeypatch.delenv('FLASK_ENV', raising=False)
    monkeypatch.delenv('APP_ENV', raising=False)
    assert resolve_config_name() == 'production'


@pytest.mark.parametrize('value', ['staging', 'prodction', 'develop', 'productionn'])
def test_unknown_env_refuses_to_start(monkeypatch, value):
    monkeypatch.setenv('FLASK_ENV', value)
    with pytest.raises(RuntimeError, match='Unknown environment'):
        create_app()


@pytest.mark.parametrize('value,expected', [
    ('dev', 'development'),
    ('DEV', 'development'),
    ('prod', 'production'),
    ('PROD', 'production'),
])
def test_env_aliases(monkeypatch, value, expected):
    monkeypatch.setenv('FLASK_ENV', value)
    assert resolve_config_name() == expected


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


def test_production_refuses_insecure_remember_cookie():
    class InsecureRemember(ProductionConfig):
        REMEMBER_COOKIE_SECURE = False

    with pytest.raises(RuntimeError, match='REMEMBER_COOKIE_SECURE'):
        create_app(InsecureRemember)


def test_production_refuses_debug():
    class DebugProduction(ProductionConfig):
        DEBUG = True

    with pytest.raises(RuntimeError, match='DEBUG'):
        create_app(DebugProduction)


def test_production_refuses_http_app_base_url():
    class HttpBase(ProductionConfig):
        APP_BASE_URL = 'http://www.trxck.tech'
        TRUSTED_HOSTS = ['www.trxck.tech', 'trxck.tech']

    with pytest.raises(RuntimeError, match='APP_BASE_URL'):
        create_app(HttpBase)


def test_production_refuses_app_base_url_host_not_in_trusted_hosts():
    class UntrustedBase(ProductionConfig):
        APP_BASE_URL = 'https://evil.com'
        TRUSTED_HOSTS = ['www.trxck.tech', 'trxck.tech']

    with pytest.raises(RuntimeError, match='TRUSTED_HOSTS'):
        create_app(UntrustedBase)


@pytest.mark.parametrize('trusted_hosts', [None, [], ['', '  ']])
def test_production_refuses_empty_trusted_hosts(trusted_hosts):
    class EmptyTrusted(ProductionConfig):
        APP_BASE_URL = 'https://www.trxck.tech'
        TRUSTED_HOSTS = trusted_hosts

    with pytest.raises(RuntimeError, match='TRUSTED_HOSTS'):
        create_app(EmptyTrusted)


def test_production_accepts_app_base_url_host_case_insensitive():
    class MixedCase(ProductionConfig):
        APP_BASE_URL = 'https://WWW.TRXCK.TECH'
        TRUSTED_HOSTS = ['www.trxck.tech', 'trxck.tech']

    previous = login_manager.session_protection
    try:
        app = create_app(MixedCase)
        assert app.config['APP_BASE_URL'] == 'https://WWW.TRXCK.TECH'
    finally:
        login_manager.session_protection = previous


@pytest.mark.parametrize('base_url', [
    'https://www.trxck.tech/app',
    'https://www.trxck.tech?next=1',
    'https://www.trxck.tech#frag',
    'https://user:pass@www.trxck.tech',
    'https://user@www.trxck.tech',
])
def test_production_refuses_app_base_url_with_path_query_fragment_or_userinfo(base_url):
    class ExtraBits(ProductionConfig):
        APP_BASE_URL = base_url
        TRUSTED_HOSTS = ['www.trxck.tech', 'trxck.tech']

    with pytest.raises(RuntimeError, match='APP_BASE_URL'):
        create_app(ExtraBits)


def test_parse_trusted_hosts_lowercases_and_strips(monkeypatch):
    monkeypatch.setenv('TRUSTED_HOSTS', ' WWW.TRXCK.TECH , TRXCK.TECH ')
    assert parse_trusted_hosts(['Example.COM']) == ['www.trxck.tech', 'trxck.tech']
    monkeypatch.delenv('TRUSTED_HOSTS')
    assert parse_trusted_hosts(['WWW.TRXCK.TECH', ' trxck.tech ']) == [
        'www.trxck.tech',
        'trxck.tech',
    ]


def test_parse_trusted_hosts_empty_or_whitespace_env_falls_back(monkeypatch):
    default = ['www.trxck.tech', 'trxck.tech']
    monkeypatch.delenv('TRUSTED_HOSTS', raising=False)
    assert parse_trusted_hosts(default) == default
    monkeypatch.setenv('TRUSTED_HOSTS', '   ')
    assert parse_trusted_hosts(default) == default
    monkeypatch.setenv('TRUSTED_HOSTS', ',,,')
    assert parse_trusted_hosts(default) == default


def test_create_app_lowercases_trusted_hosts_on_config():
    class UpperTrusted(ProductionCookieTestConfig):
        TRUSTED_HOSTS = ['WWW.TRXCK.TECH']
        APP_BASE_URL = 'https://www.trxck.tech'

    previous = login_manager.session_protection
    try:
        app = create_app(UpperTrusted)
        assert app.config['TRUSTED_HOSTS'] == ['www.trxck.tech']
    finally:
        login_manager.session_protection = previous


def test_mixed_case_host_accepted_via_raw_wsgi():
    """Flask's test client lowercases Host; raw WSGI must still accept WWW."""
    class UpperTrusted(ProductionCookieTestConfig):
        TRUSTED_HOSTS = ['WWW.TRXCK.TECH']
        APP_BASE_URL = 'https://www.trxck.tech'

    previous = login_manager.session_protection
    builder = EnvironBuilder(method='GET', path='/auth/login')
    try:
        app = create_app(UpperTrusted)
        with app.app_context():
            db.create_all()

        captured = {}

        def start_response(status, headers, exc_info=None):
            captured['status'] = status

        environ = builder.get_environ()
        environ['HTTP_HOST'] = 'WWW.TRXCK.TECH'
        environ['SERVER_NAME'] = 'WWW.TRXCK.TECH'
        environ['SERVER_PORT'] = '443'
        environ['wsgi.url_scheme'] = 'https'
        list(app(environ, start_response))
        assert captured['status'].startswith('200'), captured
    finally:
        builder.close()
        login_manager.session_protection = previous


def test_app_base_url_strips_default_ports():
    class Port443(ProductionCookieTestConfig):
        APP_BASE_URL = 'https://www.trxck.tech:443'

    previous = login_manager.session_protection
    try:
        app = create_app(Port443)
        with app.app_context():
            assert not has_request_context()
            assert absolute_url('auth.login') == 'https://www.trxck.tech/auth/login'
    finally:
        login_manager.session_protection = previous


def test_app_base_url_strips_http_default_port():
    class Port80(TestConfig):
        APP_BASE_URL = 'http://localhost:80'

    previous = login_manager.session_protection
    try:
        app = create_app(Port80)
        with app.app_context():
            assert absolute_url('auth.login') == 'http://localhost/auth/login'
    finally:
        login_manager.session_protection = previous


def test_send_trial_reminders_cli_exits_nonzero_on_failure(monkeypatch):
    app, previous = _make_prod_app()
    try:
        monkeypatch.setattr(
            'app.email_utils.send_trial_reminder_emails',
            lambda: (0, 1),
        )
        result = app.test_cli_runner().invoke(args=['send-trial-reminders'])
        assert result.exit_code != 0
        assert 'sent successfully' not in result.output
    finally:
        login_manager.session_protection = previous


def test_send_trial_reminders_cli_exits_nonzero_when_batch_raises(monkeypatch):
    app, previous = _make_prod_app()
    try:
        def boom():
            raise RuntimeError('smtp unavailable')

        monkeypatch.setattr('app.email_utils.send_trial_reminder_emails', boom)
        result = app.test_cli_runner().invoke(args=['send-trial-reminders'])
        assert result.exit_code != 0
        assert 'sent successfully' not in result.output
    finally:
        login_manager.session_protection = previous


def test_maintenance_cli_exits_nonzero_on_reminder_failure(monkeypatch):
    app, previous = _make_prod_app()
    try:
        monkeypatch.setattr('app.cli.mark_past_treatments_as_completed', lambda: 0)
        monkeypatch.setattr('app.cli.mark_inactive_patients', lambda: 0)
        monkeypatch.setattr(
            'app.email_utils.send_trial_reminder_emails',
            lambda: (0, 1),
        )
        result = app.test_cli_runner().invoke(args=['maintenance'])
        assert result.exit_code != 0
        assert 'sent successfully' not in result.output
    finally:
        login_manager.session_protection = previous


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
    email = f'logout_user_{os.getpid()}@example.com'
    with app.app_context():
        user = User(
            username=email,
            email=email,
            role='physio',
            email_verified=True,
            is_new_user=False,
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()

    client.post(
        '/auth/login',
        data={'email': email, 'password': 'password123'},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        assert sess.get('_user_id')

    with client.session_transaction() as sess:
        sess['lang'] = 'es'
        sess['_permanent'] = True

    response = client.post('/auth/logout', follow_redirects=False)
    assert response.status_code in (302, 200)
    with client.session_transaction() as sess:
        assert sess.get('_user_id') is None
        assert sess.get('lang') is None
        assert not sess.get('_permanent')
        assert dict(sess) == {}


def test_www_host_reaches_login_and_oauth_uses_app_base_url():
    """With SERVER_NAME unset, www + X-Forwarded-Proto: https must not 404.

    Prod DNS today serves only https://www.trxck.tech. OAuth redirect_uri
    comes from APP_BASE_URL, not the request Host.
    """
    app, previous = _make_prod_app()
    try:
        assert not app.config.get('SERVER_NAME')
        assert not app.config.get('SESSION_COOKIE_DOMAIN')
        assert app.config['APP_BASE_URL'] == 'https://www.trxck.tech'

        from app.routes.auth import build_oauth_redirect_uri

        @app.route('/_oauth_uri_probe')
        def _oauth_uri_probe():
            return {'uri': build_oauth_redirect_uri()}

        client = app.test_client()
        www_headers = {
            'Host': 'www.trxck.tech',
            'X-Forwarded-Proto': 'https',
        }
        login = client.get('/auth/login', headers=www_headers)
        assert login.status_code == 200

        probe = client.get('/_oauth_uri_probe', headers=www_headers)
        assert probe.status_code == 200
        uri = probe.get_json()['uri']
        parsed = urlparse(uri)
        assert parsed.scheme == 'https'
        assert parsed.hostname == 'www.trxck.tech'
        assert parsed.path == '/auth/callback/google'
    finally:
        login_manager.session_protection = previous


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


def test_untrusted_host_header_returns_400():
    """Host: evil.com is not in TRUSTED_HOSTS and must be rejected."""
    app, previous = _make_prod_app()
    try:
        client = app.test_client()
        response = client.get(
            '/auth/login',
            headers={'Host': 'evil.com'},
            base_url='https://evil.com',
        )
        assert response.status_code == 400
    finally:
        login_manager.session_protection = previous


def test_untrusted_x_forwarded_host_returns_400():
    """ProxyFix x_host=1 would rewrite to evil.com; TRUSTED_HOSTS rejects it."""
    app, previous = _make_prod_app()
    try:
        client = app.test_client()
        response = client.get(
            '/auth/login',
            headers={
                'Host': 'www.trxck.tech',
                'X-Forwarded-Host': 'evil.com',
                'X-Forwarded-Proto': 'https',
            },
            base_url='https://www.trxck.tech',
        )
        assert response.status_code == 400
    finally:
        login_manager.session_protection = previous


def test_outbound_urls_use_app_base_url_on_trusted_alias(monkeypatch):
    """Verification email and OAuth redirect_uri use APP_BASE_URL, not Host.

    trxck.tech is a trusted alias; links must still point at www.trxck.tech.
    """
    app, previous = _make_prod_app()
    try:
        user_id = _create_verified_physio(app, email='verify_host@example.com')
        captured = {}

        def fake_send(to_email, subject, html_body, text_body=None):
            captured['html'] = html_body
            captured['text'] = text_body
            return True

        monkeypatch.setattr('app.email_utils.send_email', fake_send)

        from app.routes.auth import build_oauth_redirect_uri

        @app.route('/_outbound_probe')
        def _outbound_probe():
            user = User.query.get(user_id)
            send_verification_email(user)
            return {
                'oauth': build_oauth_redirect_uri(),
                'absolute': absolute_url('auth.verify_email', token='probe-token'),
            }

        client = app.test_client()
        alias_headers = {
            'Host': 'trxck.tech',
            'X-Forwarded-Proto': 'https',
        }
        response = client.get(
            '/_outbound_probe',
            headers=alias_headers,
            base_url='https://trxck.tech',
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['oauth'] == 'https://www.trxck.tech/auth/callback/google'
        assert data['absolute'] == 'https://www.trxck.tech/auth/verify_email/probe-token'
        assert 'https://www.trxck.tech/auth/verify_email/' in captured['text']
        assert 'https://www.trxck.tech/auth/verify_email/' in captured['html']
        assert 'https://trxck.tech/' not in captured['text']
        assert 'https://evil.com' not in captured['text']
    finally:
        login_manager.session_protection = previous


def test_absolute_url_without_request_context_uses_app_base_url():
    """CLI jobs only have an app context. url_for must not require SERVER_NAME."""
    app, previous = _make_prod_app()
    try:
        with app.app_context():
            assert not has_request_context()
            url = absolute_url('auth.verify_email', token='cli-token')
            manage = absolute_url('main.manage_subscription')
        assert url.startswith(app.config['APP_BASE_URL'])
        assert url == 'https://www.trxck.tech/auth/verify_email/cli-token'
        assert manage == 'https://www.trxck.tech/manage-subscription'
    finally:
        login_manager.session_protection = previous


def test_send_trial_reminders_without_request_uses_app_base_url(monkeypatch):
    """flask send-trial-reminders must not swallow a missing request context."""
    app, previous = _make_prod_app()
    captured = {}

    def fake_send(to_email, subject, html_body, text_body=None):
        captured['to'] = to_email
        captured['html'] = html_body
        captured['text'] = text_body
        return True

    monkeypatch.setattr('app.email_utils.send_email', fake_send)

    try:
        with app.app_context():
            user = User(
                username='trial_cli@example.com',
                email='trial_cli@example.com',
                role='physio',
                email_verified=True,
                is_new_user=False,
            )
            plan = Plan(
                name='Trial Reminder Plan',
                slug='trial-reminder-plan',
                plan_type='individual',
                price_cents=0,
                billing_interval='month',
                currency='usd',
                is_active=True,
            )
            db.session.add_all([user, plan])
            db.session.commit()
            ends = datetime.utcnow() + timedelta(days=7)
            subscription = UserSubscription(
                user_id=user.id,
                plan_id=plan.id,
                status='trialing',
                trial_starts_at=datetime.utcnow(),
                trial_ends_at=ends,
                current_period_starts_at=datetime.utcnow(),
                current_period_ends_at=ends,
                trial_reminder_7_days_sent=False,
            )
            db.session.add(subscription)
            db.session.commit()
            sub_id = subscription.id

            assert not has_request_context()
            sent, failed = send_trial_reminder_emails()
            flagged = UserSubscription.query.get(sub_id).trial_reminder_7_days_sent

        assert sent == 1
        assert failed == 0
        assert flagged is True
        assert captured.get('text')
        assert 'https://www.trxck.tech/manage-subscription' in captured['text']
        assert 'https://www.trxck.tech/manage-subscription' in captured['html']
    finally:
        login_manager.session_protection = previous


def test_from_run_import_app_ignores_flaskenv_when_env_is_production(tmp_path):
    """Temp dir: .flaskenv=development, .env=production, process env unset.

    load_dotenv does not override, so loading .flaskenv first would boot
    DevelopmentConfig even when PYTHONANYWHERE_SETUP.md's .env says
    production. config.py must load only .env.
    """
    repo = Path(__file__).resolve().parents[1]
    for name in ('run.py', 'config.py', 'app'):
        os.symlink(repo / name, tmp_path / name)
    (tmp_path / '.flaskenv').write_text('FLASK_ENV=development\nAPP_ENV=development\n')
    (tmp_path / '.env').write_text(
        'FLASK_ENV=production\n'
        'SECRET_KEY=subprocess-secret-key-for-ci\n'
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ('FLASK_ENV', 'APP_ENV')
    }
    env['PYTHONPATH'] = os.pathsep.join((str(tmp_path), str(repo)))
    env['SECRET_KEY'] = 'subprocess-secret-key-for-ci'
    result = subprocess.run(
        [
            sys.executable,
            '-c',
            'from config import ProductionConfig\n'
            'from run import app\n'
            'assert app.config["DEBUG"] is False\n'
            'assert app.config["SESSION_COOKIE_SECURE"] is True\n'
            'assert app.config["REMEMBER_COOKIE_SECURE"] is True\n'
            'assert app.config["SESSION_COOKIE_SECURE"] is ProductionConfig.SESSION_COOKIE_SECURE\n'
            'print("production")\n',
        ],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
    assert 'production' in result.stdout
