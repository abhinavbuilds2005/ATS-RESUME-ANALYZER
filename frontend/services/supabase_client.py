import os
import logging
import urllib.parse
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
@st.cache_resource
def _get_cached_client(url: str, anon_key: str) -> Client:
    """Cache base client instance for connection pooling and PKCE verifier state."""
    return create_client(url, anon_key)


def get_client() -> Optional[Client]:
    """Get the active Supabase client."""
    if _missing_config():
        return None
    try:
        return _get_cached_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except Exception as exc:
        logger.error(f"Failed to initialize Supabase client: {exc}")
        return None


def _session_dict(session, user) -> Dict[str, Any]:
    return {
        'access_token':  getattr(session, 'access_token', None),
        'refresh_token': getattr(session, 'refresh_token', None),
        'user_id':       getattr(user, 'id', None),
        'email':         getattr(user, 'email', None),
    }


def extract_session_data(resp_or_session: Any, user: Any = None) -> Optional[Dict[str, Any]]:
    """
    Safely extract a normalized session dictionary from any Supabase AuthResponse,
    Session, or dict representation.
    """
    if resp_or_session is None:
        return None

    # If it's already a dictionary
    if isinstance(resp_or_session, dict):
        acc = resp_or_session.get("access_token")
        ref = resp_or_session.get("refresh_token")
        uid = resp_or_session.get("user_id") or resp_or_session.get("id")
        email = resp_or_session.get("email") or resp_or_session.get("user_email")
        if acc and uid:
            return {
                "access_token": str(acc),
                "refresh_token": str(ref) if ref else "",
                "user_id": str(uid),
                "email": str(email) if email else "",
            }
        session_obj = resp_or_session.get("session") or resp_or_session
        user_obj = resp_or_session.get("user") or user
        if isinstance(session_obj, dict):
            acc = session_obj.get("access_token")
            ref = session_obj.get("refresh_token")
            u = session_obj.get("user") or user_obj
            if isinstance(u, dict):
                uid = u.get("id")
                email = u.get("email")
            else:
                uid = getattr(u, "id", None)
                email = getattr(u, "email", None)
            if acc and uid:
                return {
                    "access_token": str(acc),
                    "refresh_token": str(ref) if ref else "",
                    "user_id": str(uid),
                    "email": str(email) if email else "",
                }

    # If it's an AuthResponse or object with .session / .user
    session = getattr(resp_or_session, "session", None) or resp_or_session
    user = user or getattr(resp_or_session, "user", None) or getattr(session, "user", None)

    acc = getattr(session, "access_token", None)
    ref = getattr(session, "refresh_token", None)
    uid = getattr(user, "id", None) if user else None
    email = getattr(user, "email", None) if user else None

    if acc and uid:
        return {
            "access_token": str(acc),
            "refresh_token": str(ref) if ref else "",
            "user_id": str(uid),
            "email": str(email) if email else "",
        }

    return None


def is_authenticated() -> bool:
    """Single source of truth for user authentication state in Streamlit."""
    token = st.session_state.get("access_token")
    uid = st.session_state.get("user_id")
    return bool(token and uid)


def set_auth_session(session_data: Dict[str, Any]) -> bool:
    """
    Centralized helper to persist an authenticated session into Streamlit session_state.
    Validates required fields before saving.
    """
    normalized = extract_session_data(session_data)
    if not normalized:
        logger.warning(f"Invalid or incomplete session data provided to set_auth_session: {session_data}")
        return False

    st.session_state["auth_session"] = normalized
    st.session_state["access_token"] = normalized["access_token"]
    st.session_state["refresh_token"] = normalized.get("refresh_token")
    st.session_state["user_id"] = normalized["user_id"]
    st.session_state["user_email"] = normalized.get("email")
    st.session_state["auth_error"] = None
    return True


def clear_auth_session() -> None:
    """Centralized helper to clear all user and authentication state."""
    keys_to_clear = [
        "auth_session",
        "access_token",
        "refresh_token",
        "user_id",
        "user_email",
        "auth_error",
        "auth_info",
        "google_oauth",
        "google_oauth_verifier",
    ]
    for key in keys_to_clear:
        st.session_state[key] = None

    # Clear user specific cached results
    st.session_state.pop("scorer_analysis", None)
    st.session_state.pop("scorer_pdf_bytes", None)


def get_current_session() -> Optional[Dict[str, Any]]:
    """Return the validated current session if authenticated, otherwise attempt restore."""
    if is_authenticated():
        session = st.session_state.get("auth_session")
        if session and isinstance(session, dict) and session.get("access_token"):
            return session
        return {
            'access_token': st.session_state.get("access_token"),
            'refresh_token': st.session_state.get("refresh_token"),
            'user_id': st.session_state.get("user_id"),
            'email': st.session_state.get("user_email"),
        }
    return restore_auth_session()


def restore_auth_session() -> Optional[Dict[str, Any]]:
    """Restore and synchronize auth session from session state across reruns."""
    print("[AUTH DEBUG] restore_auth_session START", flush=True)
    existing_session = st.session_state.get("auth_session")
    print(f"[AUTH DEBUG] existing auth_session = {bool(existing_session)}", flush=True)
    
    if existing_session and isinstance(existing_session, dict):
        normalized = extract_session_data(existing_session)
        if normalized:
            set_auth_session(normalized)
            print("[AUTH DEBUG] restored = True (from auth_session)", flush=True)
            print(f"[AUTH DEBUG] final authenticated = {is_authenticated()}", flush=True)
            print("[AUTH DEBUG] restore_auth_session END", flush=True)
            return normalized

    # Fallback to individual keys if present
    token = st.session_state.get("access_token")
    uid = st.session_state.get("user_id")
    email = st.session_state.get("user_email")
    if token and uid:
        data = {
            'access_token': token,
            'refresh_token': st.session_state.get("refresh_token"),
            'user_id': uid,
            'email': email,
        }
        set_auth_session(data)
        print("[AUTH DEBUG] restored = True (from individual keys)", flush=True)
        print(f"[AUTH DEBUG] final authenticated = {is_authenticated()}", flush=True)
        print("[AUTH DEBUG] restore_auth_session END", flush=True)
        return data

    print("[AUTH DEBUG] restored = False", flush=True)
    print(f"[AUTH DEBUG] final authenticated = {is_authenticated()}", flush=True)
    print("[AUTH DEBUG] restore_auth_session END", flush=True)
    return None



def sign_in_with_password(email: str, password: str) -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    try:
        client = get_client()
        if not client:
            return {'error': 'Authentication client initialization failed'}
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
        if not client:
            return {'error': 'Authentication client initialization failed'}
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
        base_redirect = (redirect_url or get_oauth_redirect_url()).strip().rstrip('/')
        client = get_client()
        if not client:
            return {'error': 'Authentication client initialization failed'}
        resp = client.auth.sign_in_with_oauth({
            'provider': 'google',
            'options': {'redirect_to': base_redirect},
        })
        storage_key = f'{client.auth._storage_key}-code-verifier'
        code_verifier = client.auth._storage.get_item(storage_key) or ''

        final_url = resp.url
        final_redirect = base_redirect
        if code_verifier and resp.url:
            delim = '&' if '?' in base_redirect else '?'
            final_redirect = f"{base_redirect}{delim}cv={urllib.parse.quote(code_verifier)}"
            parsed = urllib.parse.urlparse(resp.url)
            qs = urllib.parse.parse_qs(parsed.query)
            qs['redirect_to'] = [final_redirect]
            new_query = urllib.parse.urlencode(qs, doseq=True)
            final_url = urllib.parse.urlunparse(parsed._replace(query=new_query))

        return {
            'url': final_url,
            'code_verifier': code_verifier,
            'redirect_to': final_redirect,
        }
    except Exception as exc:
        logger.warning(f'oauth url generation failed: {exc}')
        return {'error': _humanize(exc)}


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
    if not client:
        return {'error': 'Authentication client initialization failed'}
    try:
        base_redirect = (redirect_url or get_oauth_redirect_url()).strip().rstrip('/')
        storage_key = f'{client.auth._storage_key}-code-verifier'
        
        if code_verifier:
            client.auth._storage.set_item(storage_key, code_verifier)
            delim = '&' if '?' in base_redirect else '?'
            redirect_to = f"{base_redirect}{delim}cv={urllib.parse.quote(code_verifier)}"
        else:
            code_verifier = client.auth._storage.get_item(storage_key) or ''
            redirect_to = base_redirect

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
        clear_auth_session()
        return
    try:
        client = get_client()
        if client:
            client.auth.sign_out()
    except Exception as exc:
        logger.warning(f'sign_out remote call failed: {exc}')
    finally:
        clear_auth_session()


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
