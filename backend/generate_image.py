from dotenv import load_dotenv
load_dotenv()

from uuid import uuid4
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client()

def generate_fashion_image(dress_paths: list[str], model_path: str):
    text_input = """Create a professional e-commerce fashion photo.
    Take the dress from the first image and let the woman from the second image wear it.
    Generate a realistic, full-body shot of the woman wearing the dress, with the lighting and shadows adjusted to match the outdoor environment same as the woman from the second image."""

    # Load images as bytes
    with open(dress_paths[0], "rb") as f:
        dress_bytes = f.read()

    with open(model_path, "rb") as f:
        model_bytes = f.read()
        
    # Generate an image from a text prompt
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[
        types.Part.from_bytes(data=dress_bytes, mime_type='image/png'),
        types.Part.from_bytes(data=model_bytes, mime_type='image/png'),
        types.Part.from_text(text=text_input)
        ]
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