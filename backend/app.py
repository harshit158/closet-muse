from fastapi import FastAPI, File, UploadFile, Response
from backend.db import create_db_and_tables
from google import genai
from google.genai import types
import base64
from backend.settings import settings

# Initialize database tables
create_db_and_tables()
gemini_client = genai.Client(api_key=settings.gemini_api_key)

app = FastAPI()

@app.post("/generate-image/")
async def generate_image(file: UploadFile = File(...)):
    text_input = """Create a professional and polished photo of the dress for an e-commerce fashion store.
    Take the dress from the first image and polish it up so that it can be posted on e-commerce fashion store.
    Background should be white.
    """
    
    # Read uploaded image
    image_bytes = await file.read()
    
    # Generate an image from a text prompt
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[
        types.Part.from_bytes(data=image_bytes, mime_type='image/png'),
        types.Part.from_text(text=text_input)
        ]
    )

    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        image_parts = [
            part.inline_data.data
            for part in response.candidates[0].content.parts
            if part.inline_data
        ]
        
        return Response(content=image_parts[0])
    
    else:
        return None 