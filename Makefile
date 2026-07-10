.PHONY: help install dev test eval seed up down front-install front-dev

help:
	@echo "Ledgerly targets:"
	@echo "  make up            docker-compose: Postgres + API + web"
	@echo "  make down          stop docker-compose"
	@echo "  make install       install backend deps (local, no docker)"
	@echo "  make dev           run API locally on :8000 (SQLite)"
	@echo "  make seed          load sample invoices into the database"
	@echo "  make test          run backend tests"
	@echo "  make eval          run extraction accuracy eval (needs LLM_API_KEY)"
	@echo "  make front-install install frontend deps"
	@echo "  make front-dev     run Vite dev server on :5173"
	@echo "  make front-test    run frontend (Vitest) tests"

install:
	cd backend && pip install -r requirements.txt

dev:
	cd backend && uvicorn app.main:app --reload --port 8000

seed:
	cd backend && python seed.py

test:
	cd backend && python -m pytest -q

eval:
	cd backend && python -m eval.run_eval

up:
	docker compose up --build

down:
	docker compose down

front-install:
	cd frontend && npm install

front-dev:
	cd frontend && npm run dev

front-test:
	cd frontend && npm test
