.PHONY: run celery dev clean

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
