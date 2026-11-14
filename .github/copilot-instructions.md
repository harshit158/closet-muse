# Copilot instructions — Closet Muse

> **Read before running any command or editing any file.**
>
> Single-user, local-first wardrobe app holding **photos of the user's home and body**.
> `make clean` destroys the database and every stored image, and there is no backup.
> **`var/` and `assets/` are both read-only.** Do not delete, overwrite, or regenerate
> anything in either — not even files that look reproducible.

---

## 1. Never run these

| Command | Destroys |
| --- | --- |
| `make clean` | `var/*.db` **and** `rm -rf var/storage` — the wardrobe and every image |
| `git clean -xdf` / `-fdX` | `assets/`, `.env`, `notebooks/`, `test_images/` |
| `git add -f <ignored path>` | pushes personal photos to a **public** repo |
| `make mannequins` / `make model` | **writes into `assets/avatar/`** — `mannequins` passes `--overwrite`, so existing PNGs are replaced (both cost API credits) |
| `rm` on `.env`, `*.db`, `var/`, `assets/` | irreplaceable |
| `alembic downgrade base` on a real DB | drops every table |

If a task seems to need one of these, **stop and ask**. There is always a safer path.

**Testing a migration needs no cleanup command** — use an isolated path:

```bash
SQLITE_PATH=/tmp/fresh.db make migrate     # ✅ touches nothing real
```

### `assets/` is off-limits — do not treat it as "regenerable"

Every file under `assets/` is to be treated as **user data, not build output**. Never delete,
overwrite, regenerate, move, or "clean up" anything there, even though scripts could recreate
parts of it.

- `make mannequins` writes into `assets/avatar/` and passes `--overwrite` (see the
  `Makefile`), so it **replaces existing images**. `make model` skips files that already exist
  unless `--overwrite` is added, but still writes new ones for missing views. Do not run either
  unless the user explicitly asks — onboarding and try-on never need them re-run.
- Do not hardcode or invent asset filenames. `settings.model_image_path` and
  `settings.model_image_views` point at specific files; a rename breaks the app silently.
- A "missing" asset is **not** permission to regenerate it. Report what is missing and ask.

### Before anything that writes, moves, or deletes files

- If the command names `var/` or `assets/`, treat it as destructive until proven otherwise.
- Never "test" a destructive path to see what it does. Read the `Makefile` target instead.
- Back up first: `sqlite3 var/closet_muse.db ".backup /tmp/b.db"` **and** `cp -R var/storage /tmp/`
  — a DB backup alone restores rows that point at missing files. Use `.backup`, not `cp`: WAL
  is on, so a plain copy can be torn.

### Never assume the data is disposable

Row counts, revisions, and stored-file counts change constantly. **Do not infer the current
state from this file, and do not act on a state you have not just measured.** Query the
live database before deciding anything is empty, orphaned, or safe to remove.

A row whose image file is missing is **not** permission to delete the row, re-seed, or treat
the 404 as a bug to fix. Report what is missing and ask.

---

## 2. Treat all of `var/` and `assets/` as read-only

**Nothing in this repo is disposable.** `var/` (database + stored images) and `assets/`
(mannequins, generated models, dress images/outputs, logos) are both off-limits. Do not
assume anything is rebuildable and delete it to "start fresh" — ask instead.

`assets/logo/*.png` is the only image intentionally tracked in git; the rest of `assets/` is
gitignored, so a deletion is unrecoverable from version control.

There is **no backup mechanism** in this project. A deleted file is gone for good.

---

## 3. The repo is public

- Never commit images, notebooks, `.env`, or anything under `var/`.
- Before committing: run `git status`, confirm no `*.png`, `*.jpg`, `*.db`, `.env`, `*.ipynb`.
- The only image blobs that may ever appear in history are `assets/logo/*.png`. Keep it that
  way.
- `.gitignore` cannot stop `git add -f`, so never use `-f` on an ignored path.

---

## 4. Two traps that corrupt data silently

**`CAST(x AS DATE)` mangles dates.** Alembic's batch row copy emits `CAST(col AS <new type>)`
when the target type differs from the source. SQLite's `DATE` cast has NUMERIC affinity, so
`'1995-01-01'` becomes the integer `1995`, then `'-4707-05-11'` on a later upgrade.

Fix: pass `copy_from=<Table>` with the column declared as the **post-migration** type, in both
`upgrade()` and `downgrade()`. `copy_from` must list every column the live table has at that
moment, and `drop_index` must run **before** a `recreate="always"` block.

**Paths are CWD-relative.** `settings.storage_dir` and `settings.sqlite_path` default to
`"var/storage"` / `"var/closet_muse.db"`. Running an entrypoint from another directory opens a
*different, empty* database — which looks like total data loss. Run from the repo root, or set
`SQLITE_PATH` / `STORAGE_DIR` explicitly.

---

## 5. Alembic owns the schema

`create_db_and_tables()` and `create_all()` were deleted; do not reintroduce them or migrate at
app start. `make migrate` is the only path. `alembic check` must report "No new upgrade
operations detected."

- `migrations/env.py` must **not** import `closet_muse.db.engine` — its `PRAGMA foreign_keys=ON`
  listener breaks batch rebuilds. `env.py` builds its own plain engine.
- `render_as_batch=True` + `compare_type=True` are mandatory.
- `migrations/script.py.mako` must use `${repr(up_revision)}` (stock `"${up_revision}"` renders
  a missing parent as `"None"` → `KeyError: 'None'`).
- Autogenerate omits `import sqlmodel`; add it by hand.
- New `NOT NULL` columns on populated tables need a `server_default`, then a follow-up alter to
  remove it — or `alembic check` reports permanent drift.

Always round-trip `make downgrade` → `make migrate` and confirm row counts and date/text values
are unchanged.

---

## 6. Decisions already made — do not revisit unasked

- **Single-user local.** `user_id=1` hardcoded. No auth, no multi-user.
- **`OutfitImage` has no ordering column.** Frontend orders views against
  `settings.model_image_views`.
- **`OutfitImage` stores `model` only** — `prompt`, `seed`, `kind`, `aspect_ratio` were removed.
- **Clothing images split across two child tables**, not one with a `kind` discriminator.
- **Enum columns store the enum *name*** (`"ONE_PIECE"`), not `.value`.
- **`view` and `sub_category` are free text** — adding a value needs no migration.

---

## 7. Architecture rules

- The frontend talks to the backend **only** via `frontend/api_utils.py`. It must never import
  `closet_muse.db` or `closet_muse.services`.
- `db/models.py` = table definitions only; DTOs live in `domain/schemas.py`.
- **The DB stores only an image *filename*** — the bucket is implied by the owning row, so
  backups must move the whole `storage_dir`.
- SQLite stores **UUID PKs without dashes**; raw `sqlite3` queries need the dashless form.
- `storage.bucket_dir()` does not validate its bucket (`"../../tmp/x"` escapes `storage_dir`).
  Never pass user input to it.
- `delete_clothing_item` → `delete_image()` permanently destroys the only copy of an image.
  Treat item deletion as destructive.
- `settings.py` is imported at module load, so editing it does not hot-reload Streamlit —
  restart `make frontend`.
- `settings.model_image_path` / `model_image_views` / `mannequin_dir` resolve to files under
  `assets/`. Never rename or move those files; do not add an `assets/` path to any
  delete/clean helper.

---

## 8. Plans and style

- **`db_plan.md`** — schema roadmap. It records which phases have landed and which is next;
  read it rather than assuming.
- Read it before schema work and update it when a phase lands. Don't silently overrule a
  decision recorded there — say so and ask.
- Keep changes scoped. Match surrounding style: type hints, docstrings on public functions,
  comments explaining *why*. Python 3.11 via `uv` — `uv add`, never `pip install`. Run from the
  repo root.

---

## 9. Verify before claiming done

```bash
uv run alembic check                                           # "No new upgrade operations detected"
sqlite3 var/closet_muse.db "select count(*) from clothing;"    # unchanged by your change
sqlite3 var/closet_muse.db "select * from alembic_version;"    # expected revision
find var/storage -type f | wc -l                               # must not go down
git status                                                     # no data files
```

Record the counts **before** you start and compare against them afterwards — never against a
number written in this file. Also: `make migrate` twice → the second is a no-op;
`make downgrade` → `make migrate` leaves row counts and date/text values unchanged;
`GET /clothing/1` and `GET /users/1` still return 200.

Use real command output. Never describe what a command "would" do and present it as
verification.