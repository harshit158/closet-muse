"""Image routes: polish, attribute extraction, upload, and retrieval."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from closet_muse.domain.schemas import ClothingBase
from closet_muse.services import attribute_extraction, image_generation, storage

router = APIRouter(prefix="/images", tags=["images"])


@router.post("/polish/")
async def polish_image(file: UploadFile = File(...)) -> Response:
    """Generate a polished, white-background version of a clothing image."""
    image_bytes = await file.read()
    result = image_generation.polish_clothing_image(image_bytes)
    if result is None:
        raise HTTPException(status_code=502, detail="Image generation returned no image.")
    return Response(content=result, media_type="image/png")


@router.post("/attributes/")
async def extract_attributes(file: UploadFile = File(...)) -> ClothingBase:
    """Extract clothing attributes from an image using the local vision model."""
    image_bytes = await file.read()
    return attribute_extraction.extract_clothing_attributes(image_bytes)


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
