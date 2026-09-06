"""Auth seam. The role is always decided on the server.
Demo headers are intentionally forgeable and ONLY for local synthetic testing.
Supabase identities are verified with the project's Auth server on every request.
"""
import httpx
from fastapi import Depends, HTTPException, Request
from ..config import DEMO_USERS
from ..schemas import User

async def verify_supabase(token: str, settings) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                settings.supabase_url.rstrip("/") + "/auth/v1/user",
                headers={"apikey": settings.supabase_publishable_key, "Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(503, "Cannot reach the configured identity provider") from exc
    if response.status_code in (401, 403):
        raise HTTPException(401, "Session expired or invalid; sign in again")
    if not response.is_success:
        raise HTTPException(503, "Identity provider could not verify this session")
    try:
        user = response.json()
    except ValueError as exc:
        raise HTTPException(503, "Invalid identity-provider response") from exc
    if not isinstance(user.get("id"), str) or not user["id"]:
        raise HTTPException(401, "No verified user identity")
    return user

async def current_user(request: Request) -> User:
    settings = request.app.state.settings
    if settings.auth_mode == "demo":
        if settings.app_env == "production":
            raise HTTPException(503, "Demo identities disabled")
        identity = request.headers.get("X-Demo-User", "")
        if identity not in DEMO_USERS:
            raise HTTPException(401, "Choose a local demo profile")
        return User(**DEMO_USERS[identity])
    bearer = request.headers.get("Authorization", "")
    if not bearer.startswith("Bearer ") or len(bearer) < 12:
        raise HTTPException(401, "Sign in first")
    verified = await verify_supabase(bearer[7:], settings)
    # Never trust user_metadata.role, a request body, or a frontend role selector.
    role = "officer" if verified["id"] in settings.officer_ids else "requester"
    return User(id=verified["id"], name=verified.get("email") or "Member", role=role)

def officer_only(user: User = Depends(current_user)) -> User:
    if user.role != "officer":
        raise HTTPException(403, "Only a planning officer can perform this action")
    return user
