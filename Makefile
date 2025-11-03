.PHONY: backend frontend

VENV := .venv
UVICORN := $(VENV)/bin/uvicorn

backend:
	uv run $(UVICORN) backend.app:app --host 0.0.0.0 --reload

frontend:
	uv run streamlit run frontend/app.py