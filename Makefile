.PHONY: build up down restart logs test health clean

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

test:
	docker compose exec api python -m pytest backend/tests -v

health:
	curl -f http://localhost:8000/api/v1/health || true
	curl -f http://localhost:3000 || true

clean:
	docker compose down -v --remove-orphans
