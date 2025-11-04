import requests
from backend.settings import settings

def generate_clothing_image(image):
    files = {"file": (image.name, image.getvalue(), image.type)}
    response = requests.post(
        f"{settings.backend_url}/generate-image/",
        files=files
    )
    return response