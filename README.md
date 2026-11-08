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

### Image models

Every OpenRouter call site has its own model setting, so different models can be
used for different jobs. Each has its own default; set only the ones you want to
change.

| variable                     | used by                              | default                         |
| ---------------------------- | ------------------------------------ | ------------------------------- |
| `IMAGE_MODEL_POLISH`         | onboarding (dress a mannequin)       | `meta/muse-image`               |
| `IMAGE_MODEL_TRYON`          | outfit generator (virtual try-on)    | `meta/muse-image`               |
| `IMAGE_MODEL_MANNEQUIN`      | `scripts/generate_mannequins.py`     | `openai/gpt-image-2.5-sunburst` |
| `IMAGE_MODEL_FASHION_MODEL`  | `scripts/generate_model.py`          | `meta/muse-image`               |

`OPENROUTER_IMAGE_URL`, `IMAGE_TIMEOUT`, `IMAGE_ASPECT_RATIO`, and `IMAGE_SEED`
apply to all of them. The scripts also accept `--model` to override the model for
a single run.

Attribute extraction uses a local Ollama vision model: `ATTRIBUTE_MODEL`
(default `qwen3-vl:4b`) and `OLLAMA_HOST` (default: the Ollama client's own
default).

## Run

```bash
make backend   # FastAPI at http://localhost:8000  (docs at /docs)
make frontend  # Streamlit UI
make dev       # both, in parallel
make seed      # create a local user in the SQLite DB
```

## Database schema

Tables are created from the SQLModel definitions on backend startup
(`create_db_and_tables()`), so there is no migration step to run.

`create_all()` is idempotent — it creates missing tables and leaves existing
ones and their rows alone — but it does **not** add a column to a table that
already exists. After adding a field to a model, either start from a fresh
database (`make clean`) or apply a one-off `ALTER TABLE`:

```bash
sqlite3 var/closet_muse.db "ALTER TABLE clothing ADD COLUMN image_path_tilted VARCHAR;"
```

## Assets

```bash
make mannequins  # regenerate the try-on mannequins in assets/avatar/
make model       # generate a fashion-model subject from reference photo(s)
```

`scripts/generate_mannequins.py` builds **ten** mannequin images: five display
forms, each in a straight-on front view and a three-quarter tilted view.

| form     | frame                        | used for                        |
| -------- | ---------------------------- | ------------------------------- |
| `face`   | head, neck and shoulders     | hats, sunglasses, scarves       |
| `top`    | head to upper hips           | tops, shirts, jackets           |
| `full`   | head to feet                 | dresses, one-piece outfits      |
| `bottom` | waist to feet                | pants, skirts, shorts           |
| `feet`   | knees to feet                | shoes                           |

Files are named `mannequin_<form>.png` and `mannequin_<form>_tilted.png`. The
`full` front view is generated from the person photo; the other four forms are
derived from it, and every tilted view is derived from its own form's front
image. Select what to build with `--forms` and `--views`:

```bash
uv run python scripts/generate_mannequins.py --forms face top --overwrite
uv run python scripts/generate_mannequins.py --views tilted --overwrite
uv run python scripts/generate_mannequins.py --views tilted --tilt-direction left --tilt-degrees 35
```

Onboarding dresses **both** perspectives of the chosen form in one click, and
the try-on generator uses both images per garment so the model can read the
fit and drape from two angles.

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