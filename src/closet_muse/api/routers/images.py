"""Image routes: polish, attribute extraction, upload, and retrieval."""

import io
import zipfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from closet_muse.domain.enums import WomenClothingMainCategory
from closet_muse.domain.schemas import ClothingBase
from closet_muse.services import attribute_extraction, image_generation, storage

router = APIRouter(prefix="/images", tags=["images"])


@router.post("/polish/")
async def polish_image(
    files: list[UploadFile] = File(...),
    garment_type: str = Form(...),
    mannequin_form: str = Form(...),
) -> Response:
    """Dress a studio mannequin in the garment worn by the person in the photo(s).

    The garment is applied to both perspectives of the chosen form, so the
    response is a ZIP archive containing ``front.png`` and ``tilted.png``.
    """
    if not files:
        raise HTTPException(status_code=422, detail="At least one image is required.")

    image_bytes = [await file.read() for file in files]
    mime_types = [file.content_type or "image/png" for file in files]
    try:
        # Generation is blocking (two concurrent HTTP calls), so keep it off the
        # event loop.
        views = await run_in_threadpool(
            image_generation.polish_clothing_image,
            image_bytes,
            garment_type,
            mannequin_form,
            mime_types,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for view, data in views.items():
            archive.writestr(f"{view}.png", data)
    return Response(content=buffer.getvalue(), media_type="application/zip")


@router.post("/attributes/")
async def extract_attributes(
    files: list[UploadFile] = File(...),
    main_category: WomenClothingMainCategory | None = Form(None),
) -> ClothingBase:
    """Extract clothing attributes from one or more photos of the item.

    ``main_category`` is the garment type the user already selected; when given,
    the extraction is constrained to it so the result fits the form.

    The extraction is a blocking HTTP call to OpenRouter, so it runs in a
    threadpool to keep the event loop free.
    """
    if not files:
        raise HTTPException(status_code=422, detail="At least one image is required.")

    image_bytes = [await file.read() for file in files]
    try:
        return await run_in_threadpool(
            attribute_extraction.extract_clothing_attributes,
            image_bytes,
            main_category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/upload/{bucket}/")
async def upload_image(bucket: str, file: UploadFile = File(...)) -> dict[str, str]:
    """Store an uploaded image in a storage bucket; return its filename."""
    file_bytes = await file.read()
    filename = storage.save_image(bucket, file_bytes)
    return {"image_path": filename}


@router.get("/{bucket}/{filename}")
async def get_image(bucket: str, filename: str) -> Response:
    """Retrieve a stored image by bucket and filename."""
    try:
        data = storage.read_image(bucket, filename)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Image not found.")
    return Response(content=data, media_type="image/png")
