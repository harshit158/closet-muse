"""FastAPI application factory and entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from closet_muse.api.routers import clothing, images, outfits, users
from closet_muse.db.engine import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (not at import time).
    create_db_and_tables()
    yield


def create_app() -> FastAPI:
    from closet_muse.settings import settings

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.include_router(images.router)
    app.include_router(clothing.router)
    app.include_router(outfits.router)
    app.include_router(users.router)

    return app


app = create_app()
