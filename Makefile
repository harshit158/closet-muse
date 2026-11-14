.PHONY: install migrate migration downgrade backend frontend dev seed mannequins model clean

VENV := .venv
UVICORN := $(VENV)/bin/uvicorn

install:
	uv sync

# Apply pending migrations. Adopts a pre-Alembic database by stamping the baseline,
# so an existing wardrobe is never re-created. Safe to run repeatedly.
migrate:
	uv run python scripts/migrate.py

# Autogenerate a revision from model changes: make migration m="add color_hex"
migration:
	uv run alembic revision --autogenerate -m "$(m)"

# Roll back one revision.
downgrade:
	uv run alembic downgrade -1

backend: migrate
	uv run $(UVICORN) closet_muse.api.main:app --host 0.0.0.0 --reload

frontend:
	uv run streamlit run frontend/app.py

dev:
	$(MAKE) -j2 backend frontend

seed: migrate
	uv run python -m closet_muse.seed

mannequins:
	uv run python scripts/generate_mannequins.py --overwrite

model:
	uv run python scripts/generate_model.py

clean:
	rm -f var/*.db
	rm -rf var/storage