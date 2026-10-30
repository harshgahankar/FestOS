import time

import jwt
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import config as C
from app.db import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

# --- local (offline/test) mode helpers ---------------------------------------
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(username: str, role: str) -> str:
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(hours=C.TOKEN_EXPIRE_HOURS)).timestamp()),
    }
    return jwt.encode(payload, C.SECRET_KEY, algorithm=C.JWT_ALGORITHM)


def decode_local_token(token: str) -> dict:
    try:
        return jwt.decode(token, C.SECRET_KEY, algorithms=[C.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")


# --- supabase mode ------------------------------------------------------------
class _FestosUser:
    """Auth identity record handed to dependencies (duck-typed like models.User)."""

    def __init__(self, username: str, role: str, email: str = ""):
        self.username = username
        self.role = role
        self.email = email
        self.id = username
        self.active = True


_token_cache: dict[str, tuple[float, _FestosUser]] = {}


def _resolve_role_from_email(email: str) -> str | None:
    for role, demo_email in C.DEMO_USER_EMAILS.items():
        if (email or "").lower() == demo_email:
            return role
    return None


def resolve_festos_role(claims_or_user: dict) -> str:
    """Role lookup priority: user_metadata.role > app_metadata.festos_role > demo email."""
    user_md = claims_or_user.get("user_metadata") or {}
    app_md = claims_or_user.get("app_metadata") or {}
    role = (user_md.get("role") or app_md.get("festos_role") or
            _resolve_role_from_email(claims_or_user.get("email", "")))
    if role not in C.ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"unknown festos role '{role}'; assign user_metadata.role "
                            f"in Supabase (one of: {', '.join(C.ROLES)})")
    return role


def supabase_login(identifier: str, password: str) -> tuple[_FestosUser, str]:
    """Exchange email-or-role + password for a Supabase session -> (user, token)."""
    email = identifier if "@" in identifier else C.DEMO_USER_EMAILS.get(identifier, identifier)
    headers = {"apikey": C.SUPABASE_ANON_KEY, "Content-Type": "application/json"}
    with httpx.Client(timeout=C.HTTP_TIMEOUT_S) as client:
        resp = client.post(f"{C.SUPABASE_URL}/auth/v1/token?grant_type=password",
                           headers=headers, json={"email": email, "password": password})
        if resp.status_code != 200:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
        token = resp.json().get("access_token")
        me = client.get(f"{C.SUPABASE_URL}/auth/v1/user",
                        headers={"apikey": C.SUPABASE_ANON_KEY,
                                 "Authorization": f"Bearer {token}"})
    user_info = {}
    if me.status_code == 200:
        user_info = me.json()
    role = resolve_festos_role(user_info)
    return _FestosUser(username=role, role=role, email=user_info.get("email", email)), token


def verify_supabase_token(token: str) -> _FestosUser:
    """Validate a Supabase access token.

    With SUPABASE_JWT_SECRET set: local HS256 verification (fast).
    Otherwise: /auth/v1/user introspection with a short-lived cache.
    """
    cached = _token_cache.get(token)
    if cached and cached[0] > time.time():
        return cached[1]

    if C.SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(token, C.SUPABASE_JWT_SECRET, algorithms=["HS256"],
                                 audience="authenticated")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
        role = resolve_festos_role(payload | {"email": payload.get("email", "")})
        user = _FestosUser(username=role, role=role, email=payload.get("email", ""))
    else:
        with httpx.Client(timeout=C.HTTP_TIMEOUT_S) as client:
            resp = client.get(f"{C.SUPABASE_URL}/auth/v1/user",
                              headers={"apikey": C.SUPABASE_ANON_KEY,
                                       "Authorization": f"Bearer {token}"})
        if resp.status_code != 200:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
        user_info = resp.json()
        role = resolve_festos_role(user_info)
        user = _FestosUser(username=role, role=role, email=user_info.get("email", ""))

    _token_cache[token] = (time.time() + C.SUPABASE_TOKEN_CACHE_TTL, user)
    return user


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    if C.AUTH_MODE == "supabase":
        return verify_supabase_token(creds.credentials)
    payload = decode_local_token(creds.credentials)
    user = db.query(User).filter(User.username == payload.get("sub"),
                                 User.active.is_(True)).first()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    return user


def require_role(*roles: str):
    """Server-side role gate. Usage: Depends(require_role('director'))"""

    def dependency(user=Depends(get_current_user)) -> _FestosUser | User:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"role '{user.role}' not allowed here; requires one of: {', '.join(roles)}",
            )
        return user

    return dependency


def require_permission(perm: str):
    """Capability gate driven by config.ROLE_PERMS; '*' means everything."""

    def dependency(user=Depends(get_current_user)):
        perms = C.ROLE_PERMS.get(user.role, set())
        if "*" not in perms and perm not in perms:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"missing permission: {perm}")
        return user

    return dependency


# --- field masking (permission matrix, config-driven) -------------------------
def mask_fields(role: str, values: dict, room: str | None = None) -> dict:
    """Return the record view for a role: sensitive fields -> 'masked' unless allowed.

    Config: config.ROLE_FIELD_ACCESS; blank/None passes through unchanged.
    """
    allowed = C.ROLE_FIELD_ACCESS.get(role, set())
    out = dict(values)
    for field in values:
        if field in C.MASKED_SENSITIVE_FIELDS and field not in allowed:
            out[field] = C.MASK_TEXT if values[field] not in (None, "", [], "unknown") \
                else values[field]
    if room is not None and "room" not in allowed:
        out["room"] = C.MASK_TEXT if room not in (None, "") else room
    return out


def can_reveal(role: str, fields: list[str]) -> tuple[bool, list[str]]:
    """Which requested fields the role may reveal (permission matrix, p.10)."""
    allowed = C.ROLE_FIELD_ACCESS.get(role, set())
    denied = [f for f in fields if f not in allowed]
    return (len(denied) == 0, denied)


def revealable_fields(role: str) -> list[str]:
    return sorted(C.ROLE_FIELD_ACCESS.get(role, set()))
