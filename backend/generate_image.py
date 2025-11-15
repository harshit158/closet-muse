from dotenv import load_dotenv
load_dotenv()

from uuid import uuid4
import webcolors
from google import genai
from google.genai import types
from PIL import Image
from backend.models import ClothingWithImage
from io import BytesIO

client = genai.Client()

def get_prompt(clothings: dict[str, ClothingWithImage]) -> str:
    text_input = """
    Replace the women's outfit with the outfit composed of following clothing items in the given images:
    {clothing_details}
    
    Preserve the subject's face, hair and hand positions exactly; keep skin texture identical.
    Preserve the colors, styles and patterns in the given clothing items.
    Keep original lighting and shadows. Use photorealistic fabric textures.
    """
    
    clothing_details = ""
    for i, (_, clothing) in enumerate(clothings.items(), 1):
        # color = webcolors.hex_to_name(clothing.clothing.color)
        clothing_details += f"Clothing {i} (in image {i}): A {clothing.clothing.color} {clothing.clothing.sub_category} ({clothing.clothing.main_category})\n"
    
    return text_input.format(clothing_details=clothing_details)
    
def generate_fashion_image(clothings: dict[str, ClothingWithImage], model_path: str):
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
    text_input = get_prompt(clothings)
    print(text_input)
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