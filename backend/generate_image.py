from dotenv import load_dotenv
load_dotenv()

from uuid import uuid4
from google import genai
from google.genai import types
from PIL import Image
from backend.models import ClothingWithImage
from io import BytesIO

client = genai.Client()

def generate_fashion_image(clothings: dict[str, ClothingWithImage], model_path: str):
    text_input = """Create a professional e-commerce fashion photo.
    Take the dresses from the first images and let the woman from the last image wear it.
    Generate a realistic, full-body shot of the woman wearing the dresses, with the lighting and shadows adjusted to match the outdoor environment same as the woman from the last image.
    """

    # Initialize payload contents
    contents = []
    
    # Add clothing images to contents
    contents.extend(
        types.Part.from_bytes(data=clothing.image_data, mime_type='image/png')
        for clothing in clothings.values() if clothing.image_data
    )

    # Add model image to contents
    model_bytes = open(model_path, "rb").read()
    contents.append(types.Part.from_bytes(data=model_bytes, mime_type='image/png'))
    
    # Add text prompt to contents
    contents.append(types.Part.from_text(text=text_input))
        
    # Generate an image from a text prompt
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=contents
    )

    image_parts = [
        part.inline_data.data
        for part in response.candidates[0].content.parts
        if part.inline_data
    ]

    if image_parts:
        image = Image.open(BytesIO(image_parts[0]))
        image.save(f'assets/dress_outputs/{uuid4()}.png')
        return image
    return None