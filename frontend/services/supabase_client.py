import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import streamlit as st
from supabase import Client, create_client

logger = logging.getLogger('ats_resume_scorer')


try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / '.env')
except ImportError:
    pass


def _secret(key: str, section: str = 'supabase') -> str:
    """Read from env first, then fall back to st.secrets[section][key]."""
    val = os.getenv(key, '')
    if val:
        return val
    try:
        return st.secrets[section][key]
    except (KeyError, FileNotFoundError, AttributeError):
        return ''


SUPABASE_URL = _secret('SUPABASE_URL')
SUPABASE_ANON_KEY = _secret('SUPABASE_ANON_KEY')

def get_oauth_redirect_url() -> str:
    """
    Resolve the OAuth redirect URL:
    1. AUTH_REDIRECT_URL environment variable
    2. OAUTH_REDIRECT_URL environment variable
    3. st.secrets['AUTH_REDIRECT_URL'] or st.secrets['google_oauth']['redirect_uri']
    4. http://localhost:8501 (default local fallback)
    Normalized by stripping whitespace and trailing slashes.
    """
    url = (
        os.getenv('AUTH_REDIRECT_URL')
        or os.getenv('OAUTH_REDIRECT_URL')
        or _secret('AUTH_REDIRECT_URL')
        or _secret('redirect_uri', 'google_oauth')
        or 'http://localhost:8501'
    )
    return str(url).strip().rstrip('/')


OAUTH_REDIRECT_URL = get_oauth_redirect_url()


def _missing_config() -> str | None:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return 'Supabase is not configured — set SUPABASE_URL and SUPABASE_ANON_KEY in .env or .streamlit/secrets.toml'
    return None


def get_client() -> Client | None:
    """Create a Supabase client instance isolated from shared disk storage."""
    if _missing_config():
        return None
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def _session_dict(session, user) -> Dict[str, Any]:
    return {
        'access_token':  getattr(session, 'access_token', None),
        'refresh_token': getattr(session, 'refresh_token', None),
        'user_id':       getattr(user, 'id', None),
        'email':         getattr(user, 'email', None),
    }


def sign_in_with_password(email: str, password: str) -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    try:
        client = get_client()
        resp = client.auth.sign_in_with_password(
            {'email': email, 'password': password}
        )
        if not resp or not resp.session or not resp.user:
            return {'error': 'Invalid credentials'}
        return _session_dict(resp.session, resp.user)
    except Exception as exc:
        logger.warning(f'sign_in_with_password failed: {exc}')
        return {'error': _humanize(exc)}


def sign_up_with_password(email: str, password: str) -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    try:
        client = get_client()
        resp = client.auth.sign_up({'email': email, 'password': password})
        if not resp:
            return {'error': 'Sign-up failed'}
        if resp.session and resp.user:
            return _session_dict(resp.session, resp.user)
        if resp.user:
            return {'pending_confirmation': True, 'email': email}
        return {'error': 'Sign-up failed'}
    except Exception as exc:
        logger.warning(f'sign_up failed: {exc}')
        return {'error': _humanize(exc)}


def google_oauth_url(redirect_url: Optional[str] = None) -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    try:
        redirect_to = (redirect_url or get_oauth_redirect_url()).strip().rstrip('/')
        client = get_client()
        resp = client.auth.sign_in_with_oauth({
            'provider': 'google',
            'options': {'redirect_to': redirect_to},
        })
        storage_key = f'{client.auth._storage_key}-code-verifier'
        code_verifier = client.auth._storage.get_item(storage_key) or ''
        return {
            'url': resp.url,
            'code_verifier': code_verifier,
            'redirect_to': redirect_to,
        }
    except Exception as exc:
        logger.warning(f'oauth url generation failed: {exc}')
        return {'error': _humanize(exc)}


def get_current_session() -> Dict[str, Any] | None:
    """Sessions are stored in st.session_state per-browser to prevent cross-user leakage."""
    return None


def exchange_code_for_session(
    auth_code: str,
    code_verifier: Optional[str] = None,
    redirect_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Called once after the OAuth provider redirects back with `?code=...`."""
    err = _missing_config()
    if err:
        return {'error': err}
    if not auth_code:
        return {'error': 'Missing authorization code'}

    client = get_client()
    try:
        redirect_to = (redirect_url or get_oauth_redirect_url()).strip().rstrip('/')
        storage_key = f'{client.auth._storage_key}-code-verifier'
        
        if code_verifier:
            client.auth._storage.set_item(storage_key, code_verifier)
        else:
            code_verifier = client.auth._storage.get_item(storage_key) or ''

        logger.info(f"Exchanging auth code (verifier present: {bool(code_verifier)}, redirect_to: {redirect_to})")
        resp = client.auth.exchange_code_for_session({
            'auth_code': auth_code,
            'code_verifier': code_verifier,
            'redirect_to': redirect_to,
        })
        if not resp or not resp.session or not resp.user:
            return {'error': 'OAuth exchange returned no session'}
            
        data = _session_dict(resp.session, resp.user)
        if not (data.get('access_token') and data.get('refresh_token') and data.get('user_id') and data.get('email')):
            return {'error': 'Incomplete session returned from auth exchange'}
            
        return data
    except Exception as exc:
        logger.error(f'exchange_code_for_session failed: {exc}')
        return {'error': _humanize(exc)}



def sign_out() -> None:
    if _missing_config():
        return
    try:
        client = get_client()
        if client:
            client.auth.sign_out()
    except Exception as exc:
        logger.warning(f'sign_out failed: {exc}')


def _humanize(exc: Exception) -> str:
    msg = str(exc)
    # supabase errors arrive as "<status>: {json blob}" — surface the human bit
    if 'invalid_grant' in msg.lower() or 'invalid login' in msg.lower():
        return 'Wrong email or password'
    if 'user already registered' in msg.lower() or 'already been registered' in msg.lower():
        return 'An account with this email already exists — try signing in'
    if 'password should be at least' in msg.lower():
        return 'Password too short (Supabase default is 6 characters)'
    return msg
