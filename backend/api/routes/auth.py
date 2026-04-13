from fastapi import APIRouter

router = APIRouter()


@router.get("/login")
async def login() -> dict[str, str]:
    """Redirect user to GitHub OAuth authorization page."""
    # TODO: Implement GitHub OAuth redirect
    return {"message": "not implemented"}


@router.get("/callback")
async def callback(code: str) -> dict[str, str]:
    """Handle GitHub OAuth callback and exchange code for token."""
    # TODO: Exchange code for access token, create/update user
    return {"message": "not implemented"}


@router.get("/me")
async def get_current_user() -> dict[str, str]:
    """Return the currently authenticated user."""
    # TODO: Validate JWT and return user info
    return {"message": "not implemented"}
