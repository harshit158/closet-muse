.PHONY: install backend frontend dev seed mannequins model clean

VENV := .venv
UVICORN := $(VENV)/bin/uvicorn

install:
	uv sync

backend:
	uv run $(UVICORN) closet_muse.api.main:app --host 0.0.0.0 --reload

frontend:
	uv run streamlit run frontend/app.py

dev:
	$(MAKE) -j2 backend frontend

seed:
	uv run python -m closet_muse.seed

mannequins:
	uv run python scripts/generate_mannequins.py --overwrite

model:
	uv run python scripts/generate_model.py

clean:
	rm -f var/*.db
	rm -rf var/storage