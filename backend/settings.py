from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # app settings
    app_name: str = "closet-muse"
    
    # endpoint
    backend_url: str = "http://localhost:8000"
    
    # api keys
    gemini_api_key: str
    
    # db settings
    schema_name: str = "closet-muse"
    supabase_db_url: str
    
    # S3 bucket names
    s3_bucket_clothing: str = "clothing" # stores clothing images
    s3_bucket_avatar: str = "avatar"     # stores user avatars
    s3_bucket_generated: str = "generated" # stores generated outfit images

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

settings = Settings()