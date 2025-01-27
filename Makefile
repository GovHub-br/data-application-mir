setup:
	pip install poetry==1.8.5
	poetry config virtualenvs.in-project false
	poetry config warnings.export false
	poetry lock
	poetry install --no-root --with dev
	poetry export --without-hashes --format=requirements.txt > requirements.txt
	bash setup-git-hooks.sh

format:
	poetry run black .
	poetry run ruff check --fix .
	poetry run sqlfmt ./dbt
	poetry run sqlfluff fix ./dbt

lint:
	poetry run black . --check
	poetry run ruff check .
	poetry run mypy .
	poetry run sqlfmt ./dbt --check
	poetry run sqlfluff lint ./dbt

test:
	poetry run pytest tests
