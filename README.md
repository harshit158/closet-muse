# Closet Muse

AI-based fashion assistant that helps you style your wardrobe.

## Architecture

Two processes talk to each other over HTTP:

```
frontend/  (Streamlit UI)  --- HTTP --->  src/closet_muse/api  (FastAPI)
                                                     |
                                                     +--> src/closet_muse/db       (SQLite via SQLModel)
                                                     +--> src/closet_muse/services (OpenRouter, Ollama, local storage)
```

- `src/closet_muse/` — the importable application package (backend API + shared domain).
- `frontend/` — a thin Streamlit app that depends on the package and calls the API over HTTP only.

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) running locally with the `qwen3-vl:4b` model (for attribute extraction)
- An OpenRouter API key (for image generation)

## Setup

```bash
make install          # uv sync
cp .env.example .env  # then fill in your keys
```

## Environment variables

See `.env.example`. Populate `.env` with your values; it is git-ignored.

## Run

```bash
make backend   # FastAPI at http://localhost:8000  (docs at /docs)
make frontend  # Streamlit UI
make dev       # both, in parallel
make seed      # create a local user in the SQLite DB
```

## Assets

```bash
make mannequins  # regenerate the try-on mannequins in assets/avatar/
make model       # generate a fashion-model subject from reference photo(s)
```

`scripts/generate_model.py` builds two photorealistic model images from one or
more reference photos of the same person (pass several with
`--reference-image photo1.jpg photo2.jpg face.jpg`): a straight-on front view
(`assets/avatar/model_generated.png`) and a three-quarter view
(`assets/avatar/model_generated_tilted.png`). The tilted view is derived from the
generated front image (not the raw references, which may themselves be turned
shots). Tune it with `--tilt-direction {left,right}` and `--tilt-degrees N`, or
regenerate a single view with `--views {front,tilted}`.

## Local data

- SQLite database: `var/closet_muse.db` (git-ignored)
- Image storage: `var/storage/{clothing,avatar,generated}` (git-ignored)

## Notes

- No remote services: the database is local SQLite and images live on the local filesystem.
- Tests, CI, and lint/type-check tooling are not yet wired up.