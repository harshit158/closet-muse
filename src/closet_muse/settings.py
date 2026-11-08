from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # app settings
    app_name: str = "closet-muse"
    debug: bool = False

    # endpoint
    backend_url: str = "http://localhost:8000"

    # api keys
    openrouter_api_key: str | None = None

    # image generation (OpenRouter)
    openrouter_image_url: str = "https://openrouter.ai/api/v1/images"
    image_timeout: int = 180
    # Per-purpose image models, each with its own default.
    image_model_polish: str = "meta/muse-image"  # onboarding: dress a mannequin
    image_model_tryon: str = "meta/muse-image"  # outfit generator: dress the model
    image_model_mannequin: str = "openai/gpt-image-2.5-sunburst"  # generate_mannequins.py
    image_model_fashion_model: str = "meta/muse-image"  # generate_model.py
    image_aspect_ratio: str = "2:3"
    image_seed: int = 42
    mannequin_dir: str = "assets/avatar"

    # clothing-attribute extraction (local Ollama vision model)
    attribute_model: str = "qwen3-vl:4b"
    ollama_host: str | None = None  # None = the ollama client's default host

    # local database (SQLite)
    sqlite_path: str = "var/closet_muse.db"

    # local image storage
    storage_dir: str = "var/storage"
    storage_bucket_clothing: str = "clothing"   # stores clothing images
    storage_bucket_avatar: str = "avatar"       # stores user avatars
    storage_bucket_generated: str = "generated"  # stores generated outfit images

    # virtual try-on model image (subject used by the backend try-on)
    model_image_path: str = "assets/avatar/model_generated.png"

    # model views shown in the "Your Look" carousel, in display order
    # (name -> path): left, center, right
    model_image_views: dict[str, str] = {
        "left": "assets/avatar/model_generated_tilted_left.png",
        "center": "assets/avatar/model_generated.png",
        "right": "assets/avatar/model_generated_tilted_right.png",
    }

    # personal settings
    personal_note: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
