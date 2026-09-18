.PHONY: dev demo down logs test

dev:
	@test -f .env || cp .env.example .env
	docker compose up --build

demo:
	docker compose exec backend python -m app.demo_seed --reset

down:
	docker compose down

logs:
	docker compose logs -f backend worker web

test:
	cd backend && pytest -q
	cd web && npm run typecheck
	cd mobile && flutter test
