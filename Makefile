.PHONY: dev test lint type-check check run live-test clean docker

# Development
dev:
	nix develop

# Run the scraper
run:
	python -m spierscraper

# Run with live data (hits real site)
live-test:
	python -m spierscraper --live

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=spierscraper --cov-report=term-missing

# Linting and type checking
lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

lint-fix:
	ruff check --fix src/ tests/
	ruff format src/ tests/

type-check:
	mypy src/

check: lint type-check test

# Docker
docker:
	nix build .#docker
	docker load < result

# Cleanup
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ result
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
