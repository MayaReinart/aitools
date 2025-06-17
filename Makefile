.PHONY: all test run celery dev clean pc fix check-web

all: pc

test:
	poetry run pytest

run:
	poetry run uvicorn src.main:app --reload --port 8080

celery:
	poetry run celery -A celery_worker worker --loglevel=info

clean:
	-pkill -f "uvicorn" || true
	-pkill -f "celery" || true
	-redis-cli shutdown || true
	sleep 2
	rm -rf logs/*
	rm -rf results/*

redis:
	redis-server --daemonize yes

dev: clean redis
	trap 'make clean' EXIT; \
	make run & \
	make celery

check-web:
	@echo "Checking web files exist..."
	@test -d web || (echo "web directory not found" && exit 1)
	@test -f web/index.html || (echo "web/index.html not found" && exit 1)

pc: check-web
	poetry run ruff check .
	poetry run ruff format --check .
	poetry run mypy src
	pre-commit run --all-files

fix:
	pre-commit run --all-files
