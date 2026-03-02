"""
User self-service endpoints.

Routes
------
GET  /me               — retrieve own profile
PATCH /me              — update own profile
GET  /me/subscriptions — list active subscriptions
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.core.security import hash_password
from app.database.models import (
    Subscription,
    SubscriptionResponse,
    User,
    UserProfileResponse,
    UserUpdateRequest,
)
from app.models.responses import StandardResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=StandardResponse[UserProfileResponse])
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Return the authenticated user's profile.

    Args:
        current_user: JWT payload of the authenticated user.

    Returns:
        User profile wrapped in a standard response.

    Raises:
        HTTPException 404: If the user document is not found in the database.
    """
    user = await User.find_one(User.email == current_user["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return StandardResponse(
        success=True,
        message="Profile retrieved",
        data=UserProfileResponse(
            id=str(user.id),
            email=user.email,
            discord_id=user.discord_id,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.patch("/me", response_model=StandardResponse[UserProfileResponse])
async def update_me(
    body: UserUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update the authenticated user's profile.

    Only non-null fields in the request body will be updated.

    Args:
        body: Fields to update (email and/or password).
        current_user: JWT payload of the authenticated user.

    Returns:
        Updated user profile.

    Raises:
        HTTPException 404: If the user document is not found.
        HTTPException 409: If the new email is already taken by another user.
    """
    user = await User.find_one(User.email == current_user["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if body.email and body.email != user.email:
        conflict = await User.find_one(User.email == body.email)
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )
        user.email = body.email

    if body.password:
        user.hashed_password = hash_password(body.password)

    user.updated_at = datetime.now(timezone.utc)
    await user.save()

    return StandardResponse(
        success=True,
        message="Profile updated",
        data=UserProfileResponse(
            id=str(user.id),
            email=user.email,
            discord_id=user.discord_id,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.get(
    "/me/subscriptions",
    response_model=StandardResponse[list[SubscriptionResponse]],
)
async def get_my_subscriptions(current_user: dict = Depends(get_current_user)):
    """
    Return all subscriptions for the authenticated user.

    Args:
        current_user: JWT payload of the authenticated user.

    Returns:
        List of subscription records.
    """
    subscriptions = await Subscription.find(
        Subscription.user_id == current_user["user_id"]
    ).to_list()

    return StandardResponse(
        success=True,
        message="Subscriptions retrieved",
        data=[
            SubscriptionResponse(
                id=str(sub.id),
                tier_id=sub.tier_id,
                external_subscription_id=sub.external_subscription_id,
                status=sub.status,
                current_period_end=sub.current_period_end,
                created_at=sub.created_at,
            )
            for sub in subscriptions
        ],
    )
