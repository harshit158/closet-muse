"""User routes."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlmodel import select

from closet_muse.api.deps import SessionDep
from closet_muse.db import models
from closet_muse.domain.schemas import UserCreate
from closet_muse.services import storage
from closet_muse.settings import settings

router = APIRouter(prefix="/users", tags=["users"])


def _get_user_or_404(user_id: int, session: SessionDep) -> models.User:
    user = session.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.post("/")
def create_user(user: UserCreate, session: SessionDep) -> models.User:
    db_user = models.User(**user.model_dump())
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@router.get("/{user_id}")
def get_user(user_id: int, session: SessionDep) -> models.User:
    return _get_user_or_404(user_id, session)


@router.post("/{user_id}/avatar/")
async def upload_avatar(
    user_id: int, session: SessionDep, file: UploadFile = File(...)
) -> models.AvatarImage:
    """Store an avatar image for a user and record it in the database."""
    _get_user_or_404(user_id, session)

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower() or "png"
    filename = storage.save_image(settings.storage_bucket_avatar, file_bytes, ext=ext)

    avatar = models.AvatarImage(user_id=user_id, image_path=filename)
    session.add(avatar)

    # Keep the user's body profile in sync with the latest avatar, if one exists.
    profile = session.exec(
        select(models.BodyProfile).where(models.BodyProfile.user_id == user_id)
    ).first()
    if profile is not None:
        profile.avatar_image_path = filename
        session.add(profile)

    session.commit()
    session.refresh(avatar)
    return avatar


@router.get("/{user_id}/avatar/")
def get_avatar(user_id: int, session: SessionDep) -> Response:
    """Return the user's most recently uploaded avatar image."""
    _get_user_or_404(user_id, session)

    avatar = session.exec(
        select(models.AvatarImage).where(models.AvatarImage.user_id == user_id)
    ).all()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")

    try:
        data = storage.read_image(
            settings.storage_bucket_avatar, avatar[-1].image_path
        )
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Avatar image not found.")
    return Response(content=data, media_type="image/png")
