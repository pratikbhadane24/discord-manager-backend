"""JWT authentication and authorization utilities."""

from fastapi import HTTPException, Request, status

from app.core.security import decode_access_token


async def get_current_user(request: Request) -> dict:
    """
    Extract and validate JWT token from request.

    Token sources (in order of precedence):
    1. Authorization header: Bearer <token>
    2. Cookie: access_token

    Args:
        request: FastAPI Request object

    Returns:
        Decoded user information from token

    Raises:
        HTTPException: If token is missing or invalid
    """
    token = None

    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix

    # Fallback to cookie if header not present
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode and validate token
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_admin(request: Request) -> dict:
    """
    Extract and validate JWT token, enforcing admin role.

    Args:
        request: FastAPI Request object

    Returns:
        Decoded user information from token (admin only)

    Raises:
        HTTPException: If token is missing, invalid, or user is not admin
    """
    payload = await get_current_user(request)
    if not payload.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return payload
