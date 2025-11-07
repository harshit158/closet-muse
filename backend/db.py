from backend.settings import settings
from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy import text
from supabase import create_client, Client

engine = create_engine(settings.supabase_db_url, 
                       echo=False, 
                       connect_args={"options": f"-csearch_path={settings.schema_name}"})


supabase: Client = create_client(settings.supabase_api_url, settings.supabase_secret_key)

def create_db_and_tables() -> None:
    """Initialize database tables from SQLModel classes."""
    schema = settings.schema_name
    
    # Create schema if it doesn't exist
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}";')) 
        
        # 2. Grant permissions
        conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO anon, authenticated, service_role;'))
        conn.execute(text(f'GRANT ALL ON ALL TABLES IN SCHEMA "{schema}" TO anon, authenticated, service_role;'))
        conn.execute(text(f'GRANT ALL ON ALL ROUTINES IN SCHEMA "{schema}" TO anon, authenticated, service_role;'))
        conn.execute(text(f'GRANT ALL ON ALL SEQUENCES IN SCHEMA "{schema}" TO anon, authenticated, service_role;'))
        conn.execute(text(f'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA "{schema}" GRANT ALL ON TABLES TO anon, authenticated, service_role;'))
        conn.execute(text(f'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA "{schema}" GRANT ALL ON ROUTINES TO anon, authenticated, service_role;'))
        conn.execute(text(f'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA "{schema}" GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;'))

    # 3. Create tables
        
    # Create tables in schema
    SQLModel.metadata.schema = schema
    SQLModel.metadata.create_all(engine)

def get_session() -> Session:
    """Get a new database session."""
    return Session(engine)