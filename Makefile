.PHONY: all test run celery dev clean pc fix

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

redis:
	redis-server --daemonize yes

dev: clean redis
	trap 'make clean' EXIT; \
	make run & \
	make celery

pc:
	poetry run ruff check .
	poetry run ruff format --check .
	poetry run mypy src
	pre-commit run --all-files

fix:
	pre-commit run --all-files
