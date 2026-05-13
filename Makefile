.PHONY: lint test format precommit-install dev-install

dev-install:
	python -m pip install --upgrade pip
	pip install -r backend/dev-requirements.txt

lint:
	ruff check backend

format:
	ruff format backend

test:
	pytest -q

precommit-install:
	pre-commit install
