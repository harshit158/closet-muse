# Closet Muse — Image Storage & Data Safety Plan

> **Purpose:** a self-contained handoff document. A new session should be able to read only
> this file and continue the work.
>
> **Status:** PLAN — nothing implemented yet.
> **Audit date:** 2026-11-14.
> **Driver:** `make clean` destroyed `var/storage/` during db_plan Phase 3/5 verification.
> The image blobs were unrecoverable. This plan exists to make that un-repeatable.

---

## 1. The incident that motivated this

While verifying migration `0004`, `make clean` was run to test a from-scratch migration.
That target is:

```make
clean:
	rm -f var/*.db
	rm -rf var/storage
```

It deleted the SQLite database **and** every stored image. The DB was recovered from a
snapshot taken minutes earlier; the images were not. `var/` is gitignored, `~/.Trash` was
empty, there was no other copy, and none of the 14 referenced filenames existed in
`assets/dress_outputs/`.

Two independent facts made this unrecoverable rather than merely annoying:

1. **There is no backup of any kind.** `tmutil destinationinfo` → *"No destinations
   configured"* (no Time Machine). `restic`, `borg`, and `git-annex` are not installed.
   The only backup-capable tool present is `/usr/bin/rsync`.
2. **The only copy lives in the repo working tree**, in a gitignored directory. It is
   therefore invisible to git — no diff, no restore, no `git fsck` safety net — while still
   being inside the blast radius of every repo-scoped command.

The goal is not "back up more aggressively"; it is to **stop the data from sharing a
filesystem location with disposable build output**.

---

## 2. Threat model — ranked by actual risk

Ranked by the audit, not by how alarming they sound.

| # | Risk | Likelihood | Impact | Currently mitigated? |
| --- | --- | --- | --- | --- |
| 1 | `make clean` deletes images | **Happened** | Total image loss | ❌ No |
| 2 | Disk failure / accidental file deletion | Medium | Total loss | ❌ No backup at all |
| 3 | `git clean -xdf` wipes data | Medium | Total loss | ❌ No — dry run shows 26 entries incl. `assets/`, `.env` |
| 4 | Running the app from another CWD silently uses a **different empty** DB and storage dir | Medium | Appears as total data loss | ❌ No — paths are CWD-relative |
| 5 | Deleting a wardrobe item permanently deletes the user's only photo of it | Medium | Irrecoverable per-item loss | ❌ No — `delete_clothing_item` unlinks files |
| 6 | Runtime assets (`assets/avatar/*`) are gitignored, so a fresh clone cannot run | **Certain** | Confusing breakage for anyone cloning | ❌ No |
| 7 | Live OpenRouter key in plaintext in `notebooks/open_ai_image_model.ipynb` | Low (never committed) | Key leak **if** notebooks are ever shared/unignored | ⚠️ Partial — `notebooks/` is ignored |
| 8 | Storage path escape via unvalidated bucket name | Low (not reachable over HTTP) | Writes outside `storage_dir` | ❌ No |
| 9 | Orphaned image files with no DB row | **Happened** (47 orphans, db_plan §4.1) | Wasted disk, confusing | ⚠️ Planned (db_plan Phase 6 GC) |

### What is *not* a risk — verified, so do not re-litigate it

- **No image, notebook, or `.env` has ever been committed.** `git rev-list --objects --all`
  filtered for `*.png|jpg|jpeg|webp|gif|ipynb|.env` returns exactly **2** blobs:
  `assets/logo/sidebar_logo.png` and `assets/logo/title_logo.png`. Both are project logos.
- **No secrets in tracked files.** `git grep -nIE "sk-[A-Za-z0-9]{16,}"` → no matches.
  `.env.example` has placeholder values only.
- **Bucket traversal is not reachable over HTTP.** `/images/upload/../../tmp/x/` and the
  percent-encoded form both 404 at the router; nothing was created outside `var/storage`.
  (`storage.bucket_dir("../../tmp/x")` *does* escape when called directly in Python — see
  §6.3 — but no HTTP route can supply such a value today.)

The repository is public (`git@github.com:harshit158/closet-muse.git`), so keeping personal
photos out of git is a real requirement — but it is **already satisfied**. The work here is
about *durability*, not about *secrecy*.

---

## 3. Current state (audited)

### Storage layer

`src/closet_muse/services/storage.py` — filesystem-backed, 5 functions:

| Function | Behaviour |
| --- | --- |
| `bucket_dir(bucket)` | `Path(settings.storage_dir) / bucket`, `mkdir(parents=True, exist_ok=True)`. **No validation.** |
| `save_image(bucket, data, ext="png")` | Writes `<bucket>/<uuid4>.<ext>`, returns the filename. Not atomic. |
| `image_path(bucket, filename)` | Traversal-safe for **filename** (`Path(filename).name != filename` → `ValueError`). |
| `read_image` | `image_path(...).read_bytes()`. |
| `delete_image` | Unlinks; swallows `ValueError` / `FileNotFoundError`. Silently accepts a missing file. |

The DB stores **only the filename**; the bucket is implied by the owning row. That is a
deliberate simplification and is fine — but it means a row is useless without knowing which
bucket it came from, so any backup/restore tool must move the **whole** `storage_dir`, not
individual files.

### Settings

```python
storage_dir: str = "var/storage"
sqlite_path: str = "var/closet_muse.db"
storage_bucket_clothing: str = "clothing"
storage_bucket_avatar: str = "avatar"
storage_bucket_generated: str = "generated"
```

`db_plan` Phase 7 adds `storage_bucket_clothing_source`.

**`.env` does not override `STORAGE_DIR` or `SQLITE_PATH`** (verified: neither key is
present). Both are CWD-relative, so:

```
$ cd /tmp && uv run --project ~/…/closet-muse python -c "from closet_muse.settings import settings; …"
storage_dir -> var/storage
sqlite_path -> var/closet_muse.db
resolves to  -> /private/tmp/var/closet_muse.db
```

Running any entrypoint from a different directory silently targets a **different, empty**
database and storage tree. This is a latent footgun that reads to a user as "all my data is
gone".

### Data inventory

| Path | Size | In git? | Regenerable? |
| --- | --- | --- | --- |
| `var/closet_muse.db` | 156 K | No (`var/`, `*.db`) | ❌ **Irreplaceable** — the wardrobe |
| `var/storage/clothing/` | was 14 files | No (`var/`) | ❌ **Irreplaceable** — user photos + polished output |
| `var/storage/avatar/` | — | No | ⚠️ Re-uploadable by hand |
| `var/storage/generated/` | was 47 orphans | No | ⚠️ Re-runnable via try-on, costs API credits |
| `assets/avatar/` | 32 M | No (`assets/`) | ✅ `make mannequins` + `make model` (API key + cost) |
| `assets/dress_images/` | 5.8 M | No | ⚠️ Inputs for mannequin generation |
| `assets/dress_outputs/` | 28 M | No | ⚠️ Outputs |
| `test_images/` | 24 M | No | ⚠️ Test fixtures |
| `notebooks/` | 63 M | No (`notebooks/`) | ⚠️ Contains a live API key |
| `assets/logo/*.png` | tracked | **Yes** | ✅ The only intentionally versioned images |

Two hard categories: **user data** (`var/closet_muse.db`, `var/storage/`) is irreplaceable;
**generated assets** (`assets/`) is reproducible at API cost. They need different treatment.

---

## 4. Where images should live

### Recommendation: move storage out of the repo tree entirely

Keep the filesystem backend (see §5 for why not BLOBs/object storage), but relocate the
canonical store to a **per-user application data directory outside the git working tree**.

**macOS:** `~/Library/Application Support/closet-muse/`
**Linux:** `~/.local/share/closet-muse/`

```
~/Library/Application Support/closet-muse/
├── closet_muse.db
└── storage/
    ├── clothing/
    ├── clothing_source/
    ├── avatar/
    └── generated/
```

Why this and not "keep it in `var/` and add a backup":

| Property | `var/` in the repo (today) | `~/Library/Application Support` |
| --- | --- | --- |
| Reachable by `make clean` | **Yes** | No |
| Reachable by `git clean -xdf` | **Yes** (26 entries today) | No |
| Survives branch switch / re-clone / repo delete | No | Yes |
| Included in Time Machine default scope | Yes, but alongside 63 M of notebooks and 32 M of regenerable assets | Yes, **without** the noise |
| Risk of `git add -f` leaking photos to a public remote | **Real** | Impossible — outside the tree |
| Accidentally committed when someone edits `.gitignore` | Possible | Impossible |

The last two rows are the decisive ones for a **public** repo. A path outside the working
tree cannot be committed, cannot be force-added, and cannot be caught by a future
`.gitignore` edit. That is a structural guarantee rather than a policy that must be
remembered.

**Config change:** set absolute paths in `.env` (gitignored) and resolve them via a
helper, so no entrypoint depends on CWD:

```python
# settings.py
def _app_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "closet-muse"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "closet-muse"
```

Keep `storage_dir` / `sqlite_path` overridable, but default to `_app_data_dir()` and
**resolve to absolute** at load. This alone kills threat #4.

### Do not put images in the database

Tempting because it makes the DB a single file to back up. Rejected:

- Every read of a wardrobe list would pull megabytes of PNG into memory.
- SQLite row-size and VACUUM behaviour get worse, not better.
- `db_plan` Phase 7 is already splitting images into `clothing_image` /
  `clothing_source_image` **by filename** — storing blobs would contradict that design.
- Backups become all-or-nothing; you lose the ability to restore metadata without 200 M of
  images.

The mitigation for "one thing to back up" is a backup script that snapshots **both**
artifacts together (§5), not a schema change.

### Do not move to S3/R2 yet

Object storage solves multi-device and durability but adds credentials, egress, and a
network dependency to a **single-user local** app whose `.env` currently has no cloud config.
Revisit only if multi-device becomes a requirement. The bucket abstraction in `storage.py`
already makes that swap cheap later.

### Naming: keep UUIDs, add integrity metadata

Current `<uuid4>.png` names are fine and `db_plan` Phase 7 depends on nothing about naming.
Content-addressed (`<sha256>`) names would give dedupe and free integrity checks, but they
complicate the "same photo uploaded twice" story and gain little at this scale. **Keep
UUIDs.** Instead:

- Write atomically (`tmp` file + `os.replace`) so a crash mid-write cannot leave a truncated
  image that a row points at.
- Add a `scripts/verify_storage.py` that checks every DB-referenced filename exists, and
  every file is referenced — reporting both missing rows and orphans.

---

## 5. Backup strategy

The app is single-user and local, so "the best way" is a boring, automatic, verifiable 3-2-1
setup. Do not hand-roll a sync.

### 5.1 Primary local backup — scripted, committed to the repo

Add `scripts/backup_data.py` + `make backup`. It is the one piece of tooling that must live
in the repo, because it must know exactly which paths matter:

1. Snapshot SQLite **safely** — `sqlite3 var/closet_muse.db ".backup '<dest>/closet_muse.db'"`,
   never a bare `cp` (WAL is enabled, so a copy can be torn). Fall back to
   `VACUUM INTO '<dest>'` on older builds.
2. Copy `storage/` with `rsync -a --delete` into a **timestamped** directory
   (`backups/2026-11-14T1030/`), or a rotating `current/` + `previous/` pair.
3. Write a `MANIFEST.json` recording: revision (`alembic_version`), row counts per table,
   file count, total bytes, and a sha256 of the DB.
4. **Verify** the snapshot by opening it read-only and running
   `PRAGMA integrity_check` + a row count. Fail loudly if it does not match the manifest.

Destination default: `~/Library/Application Support/closet-muse/backups/`, with
`--dest` to point at an external drive. Keep **3** snapshots by default.

Making the backup destination live *inside* the app-data dir is deliberate: Time Machine
then picks it up for free, and it is never inside the repo.

### 5.2 Offsite copy — turn Time Machine on, and use it

`tmutil` reports **no destinations**. This is the single highest-value fix and it costs one
external drive:

```
tmutil destinationinfo          # currently: No destinations configured
```

Also add `~/Library/Application Support/closet-muse/` to Time Machine's scope if the user
has excluded large directories. Because storage now lives outside the repo, Time Machine
backs up **the wardrobe without backing up 63 M of notebooks and 32 M of regenerable
mannequins**.

Second copy to a different physical medium (external SSD, or `restic` to Backblaze B2 if the
user later wants encryption + dedupe). Not required on day one; required before the app holds
data the user would be upset to lose.

### 5.3 What is explicitly *not* backed up by default

- `assets/` (regenerable, 32 M) — `make mannequins` / `make model`. The script should accept
  `--include-assets` for the case where the user does not want to pay to regenerate.
- `.venv/`, `__pycache__/`, `.git/` (already on the remote).

---

## 6. Making destructive operations safe

This is the section that directly prevents a repeat of the incident.

### 6.1 Split `make clean` into two targets

Today one target means two very different things. Split them:

```make
# Remove generated build/test artefacts only. Never touches user data.
clean:
	rm -f var/*.db-journal var/*.db-wal var/*.db-shm
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache

# DESTRUCTIVE. Deletes the database and every stored image.
# Requires explicit confirmation and takes a backup first.
reset-data:
	@printf 'This deletes the database AND all stored images. Type "delete" to continue: ' && \
	 read answer && [ "$$answer" = "delete" ] || (echo "Aborted."; exit 1)
	$(MAKE) backup
	rm -f "$${SQLITE_PATH:-var/closet_muse.db}"
	rm -rf "$${STORAGE_DIR:-var/storage}"

# Print paths without deleting anything — use during migration testing.
show-data:
	@echo "sqlite_path: $$(uv run python -c 'from closet_muse.settings import settings; print(settings.sqlite_path)')"
	@echo "storage_dir: $$(uv run python -c 'from closet_muse.settings import settings; print(settings.storage_dir)')"
```

Rules that follow from this:

- **Migration testing must never require `clean`.** `db_plan` §8 asks for "a fresh DB" — that
  is `SQLITE_PATH=/tmp/fresh.db make migrate`, which is exactly how `0003` and `0004` were
  verified. Put that in the Makefile as `migrate-fresh` so the safe path is the convenient one.
- `reset-data` takes a backup **before** deleting, and its type-the-word confirmation is
  deliberately not a `-i` prompt (which is trivially piped).
- Once storage moves out of the repo (§4), `reset-data` operating on an absolute path is the
  only way to reach the images — the target list is no longer in `var/`.

### 6.2 Guard the other repo-scoped commands

`git clean -xdf` currently lists 26 entries, including `assets/`, `.env`, and `notebooks/`
(hence the API key). Once storage is outside the tree this is no longer catastrophic, but it
still destroys `assets/` and `.env`. Two cheap guards:

- A `git-safe-clean` target: `git clean -xdn` (dry run) printed, then prompt.
- Document in `README.md` that `git clean -xdf` and `git add -f` are forbidden here, with the
  reason. A `.gitignore` entry cannot protect a path that someone force-adds.

Optionally add a `.git/hooks/pre-commit` that rejects any staged path under
`var/`, `assets/`, `test_images/`, `notebooks/`, or matching `*.db` / `.env`. Hooks are not
versioned by default, so this is a "nice to have" — note it in the README and offer a
one-liner to install it.

### 6.3 Harden `storage.py`

Three small changes, all cheap:

1. **Validate the bucket.** `bucket_dir` must reject a name containing a path separator or
   `..`, mirroring the check `image_path` already does for filenames:

   ```python
   if Path(bucket).name != bucket or bucket in {"", ".", ".."}:
       raise ValueError(f"Invalid bucket: {bucket!r}")
   ```

   Not reachable over HTTP today, but `save_image(bucket, …)` is called from internal code
   and `upload_image`'s `bucket` is a plain path parameter one refactor away from being
   user-controlled.

2. **Sanitize `ext`.** `save_image(..., ext="../../escaped")` currently raises
   `FileNotFoundError` rather than writing outside the bucket — accidental, not designed.
   Restrict to an allowlist (`png`, `jpg`, `jpeg`, `webp`).

3. **Write atomically.** `tmp = target.with_suffix(target.suffix + ".tmp")`, write, then
   `os.replace(tmp, target)`. A crash can no longer leave a half-written image that a row
   points at.

Also: `delete_image` silently succeeds on a missing file. That is correct for cleanup, but
`delete_clothing_item` uses it for the *only* copy of a user's photo (threat #5). See §7.

---

## 7. Never delete the user's only copy of a photo

`delete_clothing_item` currently unlinks the polished images immediately and irreversibly.
Combined with db_plan §4.11 (uploaded source photos are discarded today), deleting an item
destroys the user's photo of that garment **and** the polished output.

Three-part fix, ordered by value:

1. **Land the source-image table first** — `db_plan` Phase 7 (`clothing_source_image`)
   keeps the original uploads. That is the real fix: after it, the worst case is "I deleted
   the item, re-upload the photo".
2. **Make deletion a two-step.** `DELETE /clothing/item/{id}` removes rows; a separate
   `scripts/gc_storage.py` (already planned in db_plan Phase 6) removes unreferenced files,
   with `--dry-run` **as the default**. Between the two, an accidental delete is recoverable
   from the last backup or from the GC's grace period.
3. **Move new files to a trash bucket, not `unlink`.** `storage.move_to_trash(bucket, name)`
   into `storage/.trash/<date>/`, purged by the GC after N days. This makes even step 2
   reversible and costs one `os.replace`.

`delete_image` should stay as-is for genuinely-failed generations (nothing references them),
but item deletion should route through trash.

---

## 8. Secrets and the public repo

### 8.1 The notebook key — act on this one now

`notebooks/open_ai_image_model.ipynb` contains a live-looking OpenRouter key
(`sk-or-v1-e00…`, value masked here) in plaintext.

- **It has never been committed** — `git log --all -- notebooks/` is empty, and the history
  audit found no `*.ipynb` blob. So nothing has leaked *yet*.
- It is ignored only by the `notebooks/` rule at `.gitignore:217`. Anyone who removes that
  rule, or who shares the notebook file directly, leaks it.

Recommended: **rotate the key**, then move it out of the notebook into `.env` and read it via
`settings.openrouter_api_key` (which already exists). Rotating is cheap insurance and makes
the notebook safe to share.

### 8.2 `.env` handling

`.env` is ignored (`.gitignore:138`) and `.env.example` carries placeholders only — good.
Add the new location variables to `.env.example` once §4 lands:

```
# Canonical data location (outside the repo tree). Leave unset to use the OS default.
# STORAGE_DIR=/Users/you/Library/Application Support/closet-muse/storage
# SQLITE_PATH=/Users/you/Library/Application Support/closet-muse/closet_muse.db
```

### 8.3 Runtime assets are gitignored — document the consequence

`assets/avatar/` (32 M, 15 files) is required by `settings.model_image_path` and
`settings.mannequin_image_views`, but `assets/` is ignored. A fresh clone therefore **cannot
run** until `make mannequins` and `make model` succeed, which needs an API key and money.

Options considered:

| Option | Verdict |
| --- | --- |
| Commit `assets/avatar/*` | ❌ Bloats a public repo with 32 M of AI-generated people; git history grows permanently. |
| Ignore + document `make mannequins` as a setup step | ✅ **Recommended.** They are synthetic, not personal, and fully reproducible from `scripts/`. |
| Ignore + ship a tiny placeholder set | ⚠️ Extra machinery; only worth it if clone-and-run is a goal. |
| Generate lazily on first run | ❌ Surprising cost and latency at startup. |

Recommendation: ignore + document, **and** add a clear startup check so the failure is a
message, not a stack trace:

```
Mannequin assets are missing. Run `make mannequins` (needs OPENROUTER_API_KEY).
```

This mirrors the "run `make migrate`" startup guard already recommended in `db_plan` §2c.

---

## 9. Implementation plan

Ordered so that each phase is independently useful and nothing is destructive.

### Phase A — Stop the bleeding *(15 min, highest value per minute)*

1. **Turn on Time Machine** with an external drive (`tmutil` currently has no destination).
   This is a user action; everything else in this plan assumes it eventually happens.
2. Split `make clean` → `clean` / `reset-data` / `show-data` (§6.1). **Land this first** — it
   is the direct fix for the incident.
3. Add `migrate-fresh` (`SQLITE_PATH=/tmp/… make migrate`) so migration testing never needs a
   destructive command.
4. Update `README.md`: what `clean` and `reset-data` do, and that `git clean -xdf` /
   `git add -f` are forbidden here.

**Verify:** `make show-data` prints both paths; `make clean` removes no data;
`make reset-data` aborts unless the word is typed.

### Phase B — Add a real backup *(1 h)*

5. `scripts/backup_data.py` + `make backup` — SQLite `.backup`, `rsync` storage, manifest,
   integrity check, keep 3 (§5.1).
6. `scripts/restore_data.py` — inverse, with a **dry run by default** and refusal to
   overwrite a newer DB without `--force`.
7. `scripts/verify_storage.py` — parse the DB, list missing referenced files and orphaned
   files. Read-only.

**Verify:** run `make backup`, delete a file, run `verify_storage` (reports 1 missing), restore
it, run `verify_storage` again (clean). Confirm the manifest's row count matches the live DB.

### Phase C — Move storage out of the repo *(2–3 h, unblocks everything after)*

8. Add `_app_data_dir()` to `settings.py`; default `storage_dir` / `sqlite_path` to it;
   resolve to absolute paths at load (§4).
9. `scripts/migrate_data_dir.py` — copy (not move) `var/` → app-data dir, verify counts and
   file manifests, then print instructions to remove `var/` manually. Never auto-delete.
10. Update `.env.example`, `README.md`, and `Makefile` paths.
11. Remove `var/` from the destructive target list once it is no longer the data location.

**Verify:** run the app from `$HOME` and from `/tmp` — both must resolve the **same** DB (§3).
Wardrobe count is 14 from both. `make clean` leaves the wardrobe intact.

### Phase D — Hardening *(1 h)*

12. `storage.py`: bucket validation, `ext` allowlist, atomic `os.replace` writes (§6.3).
13. `storage.move_to_trash()` + route item deletion through it (§7, needs Phase 7's source
    table for the full fix; the trash bucket alone already helps).
14. Startup check for missing mannequin assets (§8.3).
15. Rotate the OpenRouter key; move it to `.env`; clean the notebook (§8.1).

**Verify:** unit-level — `bucket_dir("../x")` raises `ValueError`; `save_image(ext="../../x")`
raises `ValueError`; a killed write leaves no `.tmp` behind and no dangling row.

### Phase E — Ongoing integrity *(0.5 h)*

16. `make gc` (db_plan Phase 6) — orphan cleanup, `--dry-run` default.
17. Optional `pre-commit` hook rejecting staged `var/` / `assets/` / `notebooks/` / `*.db` /
    `.env` (§6.2).

---

## 10. Verification checklist

1. `make clean` → wardrobe count still 14; `var/storage` equivalent untouched.
2. `make reset-data` → aborts without the literal word; with it, takes a backup first.
3. `make backup` → manifest row count == live DB row count; `PRAGMA integrity_check` == `ok`.
4. `make restore` with no `--force` and a newer DB present → refuses.
5. `make verify-storage` → 0 missing, 0 orphans on a healthy store; reports exactly 1 missing
   after deleting a referenced file.
6. App started from `/tmp` and from the repo root → same `sqlite_path`, same wardrobe.
7. `git status` clean after a full app session (no image ever appears as untracked).
8. `git rev-list --objects --all | grep -E '\.(png|jpg|ipynb)$'` → still exactly the 2 logos.
9. `sqlite3 … ".backup"` output opens read-only and reports the right row counts.
10. Fresh clone + documented setup → app runs without touching the user's data directory.

---

## 11. Open questions

Recorded, not yet answered. Proceed with the recommendation unless told otherwise.

1. **Keep the OS-default data directory, or a user-chosen path?**
   **Recommendation:** OS default, overridable via `STORAGE_DIR` / `SQLITE_PATH` in `.env`.
   Zero-config, Time Machine picks it up, and the override covers power users.

2. **Encrypt the backup?**
   Local snapshots: no (Time Machine already handles at-rest encryption via FileVault).
   Offsite/cloud: **yes** — use `restic` rather than plain `rsync` if the copy ever leaves the
   machine, because the data is photos of the user's home and body.

3. **How long should `storage/.trash` retain deleted files?**
   **Recommendation:** 30 days, purged by `make gc`. Cheap (a wardrobe is tens of MB) and
   turns "I deleted the wrong item" from a restore into a `mv`.

4. **Commit mannequin assets or regenerate?** See §8.3 — **regenerate**, documented.

5. **Should `backup` run automatically?** Recommendation: not on every app start (surprising
   I/O and disk growth). Run before `reset-data`, and put `make backup` in the README as the
   thing to do before any migration. Time Machine covers the rest.

---

## 12. Out of scope

Multi-device sync, multi-user, remote object storage (S3/R2), image processing/CDN, and
per-image encryption. Also out of scope: changing the DB's `image_path` semantics — this plan
keeps "DB stores a bare filename, bucket implied by the row" and only changes **where** the
bucket directories live.