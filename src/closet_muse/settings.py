from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # app settings
    app_name: str = "closet-muse"
    debug: bool = False

    # endpoint
    backend_url: str = "http://localhost:8000"

    # api keys
    gemini_api_key: str | None = None

    # local database (SQLite)
    sqlite_path: str = "var/closet_muse.db"

    # local image storage
    storage_dir: str = "var/storage"
    storage_bucket_clothing: str = "clothing"   # stores clothing images
    storage_bucket_avatar: str = "avatar"       # stores user avatars
    storage_bucket_generated: str = "generated"  # stores generated outfit images

    # virtual try-on model image
    model_image_path: str = "assets/model3.jpg"

    # personal settings
    personal_note: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
