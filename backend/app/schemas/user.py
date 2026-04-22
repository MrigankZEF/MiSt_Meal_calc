"""User Pydantic schemas — built on top of fastapi-users' base schemas."""

import uuid

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    """Returned from /auth/users/me and /auth/users/{id}."""

    full_name: str


class UserCreate(schemas.BaseUserCreate):
    """Posted to /auth/register."""

    full_name: str = ""


class UserUpdate(schemas.BaseUserUpdate):
    """Patched to /auth/users/me."""

    full_name: str | None = None
