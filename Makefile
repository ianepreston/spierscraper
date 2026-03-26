.PHONY: dev test lint type-check check run live-test clean docker docker-release

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

# Docker with CalVer tagging (YYYY.MM.DD.N format)
# Usage: make docker-release [REGISTRY=ghcr.io/username]
REGISTRY ?=
DATE := $(shell date +%Y.%m.%d)

docker-release:
	nix build .#docker
	docker load < result
	$(eval VERSION := $(shell \
		existing=$$(docker images --format '{{.Tag}}' spierscraper 2>/dev/null | grep '^$(DATE)\.' | sort -t. -k4 -n | tail -1); \
		if [ -z "$$existing" ]; then \
			echo "$(DATE).1"; \
		else \
			n=$$(echo "$$existing" | cut -d. -f4); \
			echo "$(DATE).$$((n + 1))"; \
		fi \
	))
	docker tag spierscraper:latest spierscraper:$(VERSION)
	@echo "Tagged spierscraper:$(VERSION)"
ifdef REGISTRY
	docker tag spierscraper:$(VERSION) $(REGISTRY)/spierscraper:$(VERSION)
	docker tag spierscraper:$(VERSION) $(REGISTRY)/spierscraper:latest
	docker push $(REGISTRY)/spierscraper:$(VERSION)
	docker push $(REGISTRY)/spierscraper:latest
	@echo "Pushed $(REGISTRY)/spierscraper:$(VERSION)"
endif

# Cleanup
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ result
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
