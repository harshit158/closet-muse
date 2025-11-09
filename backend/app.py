from fastapi import FastAPI, File, UploadFile, Response
from uuid import uuid4
from backend.db import create_db_and_tables, supabase, get_session
from google import genai
from google.genai import types
from backend.settings import settings
from backend import models

# Initialize database tables
create_db_and_tables()
gemini_client = genai.Client(api_key=settings.gemini_api_key)

app = FastAPI(debug=True)

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

@app.post("/upload-image/{bucket_name}/")
async def upload_image(bucket_name: str, file: UploadFile = File(...)):
    image_id = str(uuid4())
    file_bytes = await file.read()
    response = supabase.storage.from_(bucket_name).upload(f'{image_id}.png', file_bytes, {'content-type': 'image/png'})
    
    return {"image_path": response.full_path}

@app.post("/user/")
async def create_user(user: models.UserCreate):
    with get_session() as session:
        db_user = models.User(**user.model_dump())
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return db_user

@app.post("/clothing/{user_id}")
async def add_clothing_item(user_id: int, clothing: models.ClothingBase):
    with get_session() as session:
        db_clothing = models.Clothing(
            **clothing.model_dump(), 
            user_id=user_id
        )
        db_clothing.user_id = user_id
        session.add(db_clothing)
        session.commit()
        session.refresh(db_clothing)
        return db_clothing