install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

lint:
	flake8 src/

format:
	black src/ tests/
