from fastapi import FastAPI
from backend.db import create_db_and_tables
from backend import models

# Initialize database tables
create_db_and_tables() 

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}