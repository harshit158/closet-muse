"""Outfit routes: virtual try-on generation and saved-outfit history."""

import io
import uuid
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlmodel import Session, select

from closet_muse.api.deps import SessionDep
from closet_muse.db import models
from closet_muse.domain.schemas import ClothingBase, ClothingWithImage, OutfitRequest
from closet_muse.services import credits, image_generation, storage
from closet_muse.settings import settings

router = APIRouter(prefix="/outfits", tags=["outfits"])


def _polished_path(item: models.Clothing, view: str) -> str | None:
    """The stored filename of one polished view, or ``None`` when it is missing.

    Polished renders live in ``clothing_image`` (one row per view) since revision
    ``0006``. Items onboarded before the tilted view existed have no ``tilted`` row.
    """
    for image in item.images:
        if image.view == view:
            return image.image_path
    return None


def _load_selections(
    user_id: int, clothing_ids: list[uuid.UUID], session: Session
) -> tuple[dict[str, ClothingWithImage], list[models.Clothing]]:
    """Resolve the requested items into try-on references.

    Returns the prompt payload (keyed by main category, as the generator expects) and
    the rows themselves, which the caller links to the new outfit.
    """
    selections: dict[str, ClothingWithImage] = {}
    items: list[models.Clothing] = []

    for clothing_id in clothing_ids:
        item = session.get(models.Clothing, clothing_id)
        if item is None or item.user_id != user_id:
            raise HTTPException(
                status_code=404, detail=f"Clothing item {clothing_id} not found."
            )

        front_path = _polished_path(item, "front")
        if front_path is None:
            raise HTTPException(
                status_code=422,
                detail=f"Clothing item {clothing_id} has no polished front image.",
            )

        data = storage.read_image(settings.storage_bucket_clothing, front_path)
        # The tilted perspective is optional: items onboarded before it existed
        # have no second image, and the try-on prompt handles a single reference.
        tilted_path = _polished_path(item, "tilted")
        tilted_data = (
            storage.read_image(settings.storage_bucket_clothing, tilted_path)
            if tilted_path
            else None
        )
        category = item.main_category
        key = category.value if hasattr(category, "value") else str(category)
        selections[key] = ClothingWithImage(
            # ``model_validate`` (not ``**model_dump()``) because the row now carries
            # ``images`` / ``source_images``, which ``ClothingBase`` does not declare.
            clothing=ClothingBase.model_validate(item),
            image_data=data,
            image_data_tilted=tilted_data,
        )
        items.append(item)

    return selections, items


def _persist_outfit(
    user_id: int,
    items: list[models.Clothing],
    views: dict[str, bytes],
    session: Session,
) -> tuple[models.Outfit, int]:
    """Write the outfit, its garment links, one image row per view, and the spend.

    The whole write is one transaction: if any step fails, the rows are rolled back
    and the files already written are removed, so a failed generation never leaves a
    half-written outfit (or orphaned PNGs) behind. The credit deduction is part of the
    same transaction, so a user is never charged for an outfit that was not stored.

    Returns the outfit and the balance remaining after the spend.
    """
    outfit = models.Outfit(user_id=user_id, created_by_ai=True)
    session.add(outfit)
    # Assigns outfit.id so the children below can reference it.
    session.flush()

    for item in items:
        session.add(
            models.OutfitClothingLink(outfit_id=outfit.id, clothing_item_id=item.id)
        )

    saved: list[str] = []
    try:
        for view, image_bytes in views.items():
            filename = storage.save_image(
                settings.storage_bucket_generated, image_bytes
            )
            saved.append(filename)
            session.add(
                models.OutfitImage(
                    user_id=user_id,
                    outfit_id=outfit.id,
                    view=view,
                    image_path=filename,
                    # The model that rendered this row cannot be re-derived later,
                    # because settings.image_model_tryon changes over time.
                    model=settings.image_model_tryon,
                )
            )
        # Charged last, so the ledger row can reference the outfit it paid for. A
        # failure here rolls back the outfit and deletes the PNGs above.
        balance = credits.spend(
            session,
            user_id,
            credits.CREDIT_COST_OUTFIT,
            credits.REASON_OUTFIT_GENERATION,
            outfit_id=outfit.id,
        )
        session.commit()
    except Exception:
        session.rollback()
        for filename in saved:
            storage.delete_image(settings.storage_bucket_generated, filename)
        raise

    session.refresh(outfit)
    return outfit, balance


@router.post("/generate/{user_id}")
def generate_outfit(
    user_id: int, request: OutfitRequest, session: SessionDep
) -> Response:
    """Generate a virtual try-on image per model view from selected wardrobe items.

    Every view in ``settings.model_image_views`` is dressed in the same outfit, so
    the response is a ZIP archive holding one PNG per view (``left.png``,
    ``center.png``, ``right.png``).

    The outfit is persisted before the response is built: one ``outfit`` row, one
    ``outfitclothinglink`` row per garment, and one ``outfitimage`` row per view. Its
    id is returned in the ``X-Outfit-Id`` header, since the body is a binary ZIP.

    Generation costs :data:`credits.CREDIT_COST_OUTFIT` credits. The balance is checked
    **before** the paid API calls, so an empty wallet fails fast with ``402`` instead of
    spending real money on images that cannot be saved. The remaining balance comes back
    in the ``X-Credits-Remaining`` header.
    """
    # Fail before any paid work. The authoritative check is the conditional UPDATE in
    # ``credits.spend``; this one only avoids paying for images we cannot charge for.
    try:
        balance = credits.get_balance(session, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if balance < credits.CREDIT_COST_OUTFIT:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Not enough credits: {balance} remaining, "
                f"{credits.CREDIT_COST_OUTFIT} required."
            ),
        )

    selections, items = _load_selections(user_id, request.clothing_ids, session)

    # One try-on per model view; fall back to the single subject image when no
    # view map is configured.
    model_paths = settings.model_image_views or {
        "center": settings.model_image_path
    }
    try:
        views = image_generation.generate_fashion_images(selections, model_paths)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    try:
        outfit, remaining = _persist_outfit(user_id, items, views, session)
    except credits.InsufficientCredits as exc:
        # The balance changed between the pre-flight check and the spend.
        raise HTTPException(status_code=402, detail=str(exc))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for view, image_bytes in views.items():
            archive.writestr(f"{view}.png", image_bytes)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "X-Outfit-Id": str(outfit.id),
            "X-Credits-Remaining": str(remaining),
        },
    )


@router.get("/image/{filename}")
def get_generated_image(filename: str) -> Response:
    try:
        data = storage.read_image(settings.storage_bucket_generated, filename)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Image not found.")
    return Response(content=data, media_type="image/png")


@router.get("/{user_id}/history")
def list_outfit_history(user_id: int, session: SessionDep) -> list[models.Outfit]:
    """List a user's saved outfits, newest first."""
    statement = (
        select(models.Outfit)
        .where(models.Outfit.user_id == user_id)
        .order_by(models.Outfit.created_at.desc())
    )
    return list(session.exec(statement).all())


@router.get("/{outfit_id}/images")
def list_outfit_images(
    outfit_id: uuid.UUID, session: SessionDep
) -> list[models.OutfitImage]:
    """Return the persisted renders for one outfit.

    Rows come back in no guaranteed order: the frontend orders them against
    ``settings.model_image_views``, which is why no ordering column is stored.
    """
    if session.get(models.Outfit, outfit_id) is None:
        raise HTTPException(status_code=404, detail="Outfit not found.")

    statement = select(models.OutfitImage).where(
        models.OutfitImage.outfit_id == outfit_id
    )
    return list(session.exec(statement).all())


@router.get("/{outfit_id}")
def get_outfit(outfit_id: uuid.UUID, session: SessionDep) -> models.Outfit:
    outfit = session.get(models.Outfit, outfit_id)
    if outfit is None:
        raise HTTPException(status_code=404, detail="Outfit not found.")
    return outfit
