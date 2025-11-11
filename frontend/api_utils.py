import requests
from io import BytesIO
from backend.settings import settings
from backend import models

def generate_clothing_image(image: BytesIO):
    files = {"file": (image.name, image.getvalue(), image.type)}
    response = requests.post(
        f"{settings.backend_url}/generate-image/",
        files=files
    )
    return response

def upload_image(bucket: str, file) -> str:
    files = {"file": (file.name, file.getvalue(), file.type)}
    response = requests.post(
        f"{settings.backend_url}/upload-image/{bucket}/",
        files=files
    )
    return response.json()["image_path"]

def add_clothing_item(user_id: int, clothing: models.ClothingBase, image: BytesIO):
    # upload image first and get image_id
    image_path = upload_image("clothing", image)
    clothing.image_path = image_path

    response = requests.post(
        f"{settings.backend_url}/clothing/{user_id}",
        json=clothing.model_dump()
    )
    
    print(response.status_code, response.json())