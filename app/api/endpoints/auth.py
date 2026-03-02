"""
Authentication and Discord OAuth2 endpoints.

Routes
------
POST /register      — create a new user account
POST /login         — exchange credentials for JWT
GET  /discord/login — redirect user to Discord OAuth2 consent page
GET  /discord/callback — handle OAuth2 callback and link Discord account
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.database.models import (
    User,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
)
from app.models.responses import StandardResponse
from app.services.discord_service import DiscordService

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post(
    "/register",
    response_model=StandardResponse[UserProfileResponse],
    status_code=status.HTTP_201_CREATED,
)
async def register(body: UserRegisterRequest):
    """
    Register a new user account.

    Args:
        body: Registration payload (email + password).

    Returns:
        Newly created user profile wrapped in a standard response.

    Raises:
        HTTPException 409: If the email is already registered.
    """
    existing = await User.find_one(User.email == body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    await user.insert()
    return StandardResponse(
        success=True,
        message="User registered successfully",
        data=UserProfileResponse(
            id=str(user.id),
            email=user.email,
            discord_id=user.discord_id,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.post("/login", response_model=StandardResponse[dict])
async def login(body: UserLoginRequest):
    """
    Authenticate with email and password.

    Args:
        body: Login payload (email + password).

    Returns:
        JWT access token dict wrapped in a standard response.

    Raises:
        HTTPException 401: If credentials are incorrect.
    """
    user = await User.find_one(User.email == body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id), "is_admin": user.is_admin}
    )
    return StandardResponse(
        success=True,
        message="Login successful",
        data={"access_token": token, "token_type": "bearer"},
    )


@router.get("/discord/login")
async def discord_login():
    """
    Redirect the browser to Discord's OAuth2 consent page.

    Returns:
        RedirectResponse to Discord authorization URL.
    """
    service = DiscordService()
    url = service.get_oauth_authorization_url()
    await service.close()
    return RedirectResponse(url=url)


@router.get("/discord/callback", response_model=StandardResponse[UserProfileResponse])
async def discord_callback(
    code: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Handle Discord OAuth2 callback.

    Exchanges the authorization *code* for a token set, fetches the Discord
    user profile, and links the Discord account to the authenticated user.

    Args:
        code: Authorization code received from Discord.
        current_user: JWT payload of the currently authenticated user.

    Returns:
        Updated user profile.

    Raises:
        HTTPException 400: If the OAuth exchange fails.
        HTTPException 409: If the Discord account is already linked to another user.
    """
    service = DiscordService()
    try:
        token_data = await service.exchange_code_for_token(code)
        discord_user = await service.get_current_user_info(token_data["access_token"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Discord OAuth failed: {exc}",
        )
    finally:
        await service.close()

    discord_id = discord_user["id"]

    # Ensure this Discord account isn't already linked to a different user
    conflict = await User.find_one(
        User.discord_id == discord_id,
        User.email != current_user["sub"],
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Discord account is already linked to another user",
        )

    user = await User.find_one(User.email == current_user["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    expires_in = token_data.get("expires_in", 604800)
    user.discord_id = discord_id
    user.discord_access_token = token_data["access_token"]
    user.discord_refresh_token = token_data.get("refresh_token")
    user.discord_token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=expires_in
    )
    user.updated_at = datetime.now(timezone.utc)
    await user.save()

    return StandardResponse(
        success=True,
        message="Discord account linked successfully",
        data=UserProfileResponse(
            id=str(user.id),
            email=user.email,
            discord_id=user.discord_id,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )
