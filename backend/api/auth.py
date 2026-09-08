import logging
from typing import Optional, Dict, Any
import jwt
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.config import SUPABASE_JWT_SECRET, SUPABASE_URL, SUPABASE_KEY, SUPABASE_ANON_KEY

logger = logging.getLogger('ats_resume_scorer')

_bearer_scheme = HTTPBearer(auto_error=False)
_ASYMMETRIC_ALGS = ['ES256', 'RS256']
_jwks_client: Optional[jwt.PyJWKClient] = None


def _get_jwks_client() -> Optional[jwt.PyJWKClient]:
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client
    if not SUPABASE_URL:
        return None
    jwks_url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    _jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
    return _jwks_client


def _verify_token_locally(token: str) -> Dict[str, Any]:
    header = jwt.get_unverified_header(token)
    alg = header.get('alg', 'HS256')

    if alg in _ASYMMETRIC_ALGS:
        jwks_client = _get_jwks_client()
        if jwks_client is None:
            raise jwt.InvalidTokenError(
                'SUPABASE_URL not configured — cannot fetch JWKS to verify token'
            )
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=_ASYMMETRIC_ALGS,
            audience='authenticated',
        )

    if alg == 'HS256':
        if not SUPABASE_JWT_SECRET:
            raise jwt.InvalidTokenError(
                'HS256 token received but SUPABASE_JWT_SECRET is not configured'
            )
        return jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=['HS256'],
            audience='authenticated',
        )

    raise jwt.InvalidTokenError(f'Unsupported JWT algorithm: {alg}')


async def _verify_token_with_supabase_api(token: str) -> Optional[str]:
    """Fallback: Validate token directly against Supabase Auth API."""
    if not SUPABASE_URL:
        return None
    api_key = SUPABASE_ANON_KEY or SUPABASE_KEY
    if not api_key:
        return None

    url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                user_data = resp.json()
                return user_data.get('id')
    except Exception as exc:
        logger.warning(f"Supabase Auth API token check failed: {exc}")
    return None


async def verify_jwt_token(token: str) -> str:
    """
    Verify JWT token and extract user_id (sub).
    Raises HTTPException(401) on failure.
    """
    try:
        payload = _verify_token_locally(token)
        user_id = payload.get('sub')
        if user_id:
            return str(user_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token has expired. Please sign in again.',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    except jwt.InvalidTokenError as exc:
        fallback_uid = await _verify_token_with_supabase_api(token)
        if fallback_uid:
            return str(fallback_uid)
        logger.warning(f"JWT verification rejected: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or expired authentication token.',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    except Exception as exc:
        fallback_uid = await _verify_token_with_supabase_api(token)
        if fallback_uid:
            return str(fallback_uid)
        logger.warning(f"Token verification error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication failed. Please sign in again.',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Token is missing user identifier (sub claim).',
        headers={'WWW-Authenticate': 'Bearer'},
    )


async def get_current_user_id(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """Dependency for protected endpoints that require an authenticated user."""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Missing or invalid Authorization header.',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    return await verify_jwt_token(creds.credentials)


async def get_optional_user_id(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[str]:
    """Dependency for optional authentication (e.g. guest vs logged-in analysis)."""
    if creds is None or not creds.credentials:
        return None
    try:
        return await verify_jwt_token(creds.credentials)
    except HTTPException:
        return None


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    return await get_current_user_id(creds)

