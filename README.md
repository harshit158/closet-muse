# Closet Muse

AI-based fashion assistant that helps you style your wardrobe.

## Architecture

Two processes talk to each other over HTTP:

```
frontend/  (Streamlit UI)  --- HTTP --->  src/closet_muse/api  (FastAPI)
                                                     |
                                                     +--> src/closet_muse/db       (SQLite via SQLModel)
                                                     +--> src/closet_muse/services (OpenRouter, local storage)
```

- `src/closet_muse/` — the importable application package (backend API + shared domain).
- `frontend/` — a thin Streamlit app that depends on the package and calls the API over HTTP only.

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- An OpenRouter API key (for image generation and attribute extraction)

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

### Attribute extraction

Attribute extraction uses an OpenRouter vision model with
[structured outputs](https://openrouter.ai/docs/features/structured-outputs):
the request sends a JSON schema derived from `ClothingBase` as
`response_format`, so the reply is schema-conforming JSON rather than free text.

| variable              | default                                        |
| --------------------- | ---------------------------------------------- |
| `ATTRIBUTE_MODEL`     | `deepseek/deepseek-v4.1-flash-1017`            |
| `OPENROUTER_CHAT_URL` | `https://openrouter.ai/api/v1/chat/completions` |
| `ATTRIBUTE_TIMEOUT`   | `120`                                          |

The model must accept image input and be served by a provider that supports
structured outputs; `provider.require_parameters` restricts routing to those
endpoints, so an unsupported model fails loudly instead of returning free text.

## Run

```bash
make migrate   # create/update the SQLite schema (Alembic)
make backend   # FastAPI at http://localhost:8000  (docs at /docs)
make frontend  # Streamlit UI
make dev       # both, in parallel
make seed      # create a local user in the SQLite DB
```

`make backend` and `make seed` run `make migrate` first, so the schema is always current.
The application itself never issues DDL.

## Database schema

The schema is owned by **Alembic**, not by `SQLModel.metadata.create_all()`. Migrations live
in `migrations/versions/`; `migrations/env.py` resolves the database URL from
`settings.sqlite_path`.

```bash
make migrate                    # apply pending revisions (safe to re-run)
make migration m="add color_hex" # autogenerate a revision from model changes
make downgrade                  # roll back one revision
make clean                      # delete the DB; follow with `make migrate`
```

**After changing a model, run `make migration` then `make migrate`.** Never hand-edit a
table with `ALTER TABLE`.

Two details worth knowing:

- **`render_as_batch=True`** — SQLite cannot `ALTER` a table in place, so every non-additive
  change (dropping a column, changing a constraint) is done as create-copy-drop-rename.
- **Alembic uses its own engine** and does not enable `PRAGMA foreign_keys`, because batch
  rebuilds fail when foreign keys are enforced mid-copy. The app's engine (`db/engine.py`)
  still enables it at runtime.

Enum columns store the enum **name** (`"ONE_PIECE"`, `"POLYESTER"`), not its value, and
SQLite renders them as `VARCHAR(n)` with no `CHECK` constraint.

### Adopting a pre-Alembic database

`make migrate` detects a database that has tables but no `alembic_version` row and stamps
the baseline revision instead of replaying it, so an existing wardrobe is never re-created.

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