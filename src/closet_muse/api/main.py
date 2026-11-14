"""FastAPI application factory and entrypoint."""

from fastapi import FastAPI

from closet_muse.api.routers import clothing, images, outfits, users


def create_app() -> FastAPI:
    from closet_muse.settings import settings

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    app.include_router(images.router)
    app.include_router(clothing.router)
    app.include_router(outfits.router)
    app.include_router(users.router)

    return app


app = create_app()
