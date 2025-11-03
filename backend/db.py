from backend.settings import settings
from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy import text

engine = create_engine(settings.supabase_db_url, 
                       echo=False, 
                       connect_args={"options": f"-csearch_path={settings.schema_name}"})

def create_db_and_tables() -> None:
    """Initialize database tables from SQLModel classes."""
    # Create schema if it doesn't exist
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.schema_name}";'))
        
    # Create tables in schema
    SQLModel.metadata.schema = settings.app_name
    SQLModel.metadata.create_all(engine)

def get_session() -> Session:
    """Get a new database session."""
    return Session(engine)