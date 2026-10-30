from fastapi import APIRouter, Depends, HTTPException, status

from app import schemas
from app.auth import create_access_token, get_current_user, require_role, verify_password
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, db=Depends(get_db)):
    from app import config as C
    from app import auth as auth_mod

    if C.AUTH_MODE == "supabase":
        user, token = auth_mod.supabase_login(body.username, body.password)
        # the Supabase access token is the bearer credential; role comes from claims
        return schemas.TokenOut(access_token=token, role=user.role)
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not user.active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    return schemas.TokenOut(access_token=create_access_token(user.username, user.role),
                            role=user.role)


@router.get("/me", response_model=schemas.MeOut)
def me(user: User = Depends(get_current_user)):
    return schemas.MeOut(username=user.username, role=user.role)


@router.get("/admin-only")
def admin_only(user: User = Depends(require_role("director"))):
    return {"ok": True, "role": user.role}
