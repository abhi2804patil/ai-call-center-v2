.PHONY: dev migrate test build logs

dev:
	docker-compose up --build

migrate:
	docker-compose exec backend alembic upgrade head

test:
	docker-compose exec backend python -m pytest tests/ -v

build:
	docker-compose build

logs:
	docker-compose logs -f

down:
	docker-compose down

reset-db:
	docker-compose exec backend alembic downgrade base
	docker-compose exec backend alembic upgrade head
