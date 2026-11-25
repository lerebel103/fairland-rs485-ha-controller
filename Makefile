VERSION := $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
IMAGE_NAME = fairland-rs485-ha-controller
IMAGE_TAG = latest
DOCKER_USER = lerebel103
SRC = app/ tests/ scripts/

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  check       - Lint, map-doc check and tests with coverage (run before every commit)"
	@echo "  test        - Run all tests"
	@echo "  test-cov    - Run tests with coverage report"
	@echo "  lint        - Run ruff check, ruff format --check and the Modbus map doc check"
	@echo "  format      - Format code with ruff"
	@echo "  modbus-map  - Re-render the tables in docs/modbus-map.md from the code"
	@echo "  worktree    - Create a worktree and branch: make worktree name=<topic> [type=feature|fix|spec]"
	@echo "  build       - Build Docker image"
	@echo "  build-multi - Build and push multi-architecture Docker images (amd64, arm64)"
	@echo "  up/start    - Start the application with docker compose"
	@echo "  down/stop   - Stop the application with docker compose"
	@echo "  logs        - View application logs"
	@echo "  clean       - Remove Docker images and containers"

.PHONY: check
check: lint test-cov

.PHONY: test
test:
	uv run pytest tests/ -v

.PHONY: test-cov
test-cov:
	uv run pytest tests/ -v --cov=app --cov-report=term-missing

.PHONY: lint
lint:
	uv run ruff check $(SRC)
	uv run ruff format --check $(SRC)
	uv run python scripts/render_modbus_map.py --check

.PHONY: format
format:
	uv run ruff format $(SRC)
	uv run ruff check --fix $(SRC)

.PHONY: modbus-map
modbus-map:
	uv run python scripts/render_modbus_map.py

type ?= feature
.PHONY: worktree
worktree:
	@test -n "$(name)" || { echo "usage: make worktree name=<topic> [type=feature|fix|spec]"; exit 1; }
	git worktree add .claude/worktrees/$(name) -b $(type)/$(name) main
	@echo "Worktree ready: .claude/worktrees/$(name) on branch $(type)/$(name)"

.PHONY: build
build:
	docker build --build-arg VERSION=$(VERSION) -t $(IMAGE_NAME):$(IMAGE_TAG) .

.PHONY: build-multi
build-multi:
	docker buildx create --name multiarch --use --bootstrap 2>/dev/null || docker buildx use multiarch
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		--tag $(DOCKER_USER)/$(IMAGE_NAME):$(IMAGE_TAG) \
		--tag $(DOCKER_USER)/$(IMAGE_NAME):$(VERSION) \
		--build-arg VERSION=$(VERSION) \
		--push \
		.

.PHONY: up start
up start:
	@if [ ! -f config.yaml ]; then \
		echo "Error: config.yaml not found. Copy config.yaml.example to config.yaml and edit it."; \
		exit 1; \
	fi
	docker compose up -d

.PHONY: down stop
down stop:
	docker compose down

.PHONY: logs
logs:
	docker compose logs -f fairland-rs485-ha-controller

.PHONY: clean
clean:
	docker compose down --rmi all --volumes --remove-orphans
