.PHONY: install test run docker-image
install:
	python -m pip install -r requirements-dev.txt
test:
	python -m pytest -q
run:
	PUBLIC_DEMO=1 DB_PATH=./data/inneros_agent_rush.sqlite uvicorn inneros_agent_rush.main:app --host 127.0.0.1 --port 8000
docker-image:
	docker pull python:3.12-alpine
