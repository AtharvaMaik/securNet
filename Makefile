PYTHON ?= python
PIP ?= pip
COMPOSE ?= docker compose

.PHONY: install dev test lint compose-up compose-down validate-prometheus validate-compose

install:
	$(PYTHON) -m pip install -e .[dev]

dev:
	$(COMPOSE) -f infra/docker-compose.yml up --build

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

compose-up:
	$(COMPOSE) -f infra/docker-compose.yml up --build -d

compose-down:
	$(COMPOSE) -f infra/docker-compose.yml down -v

validate-prometheus:
	docker run --rm -v ${CURDIR}/infra/prometheus:/etc/prometheus prom/prometheus:v2.54.1 promtool check config /etc/prometheus/prometheus.yml

validate-compose:
	$(COMPOSE) -f infra/docker-compose.yml config > NUL
