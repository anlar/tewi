# SPDX-FileCopyrightText: 2024 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

check:
	uv run ruff check
	uv run reuse lint

# API keys of search provider containers for integration tests (empty if
# containers aren't running)
JACKETT_API_KEY = $(shell docker exec tewi-jackett-dev sed -n 's/.*"APIKey": *"\([^"]*\)".*/\1/p' /config/Jackett/ServerConfig.json 2>/dev/null)
PROWLARR_API_KEY = $(shell docker exec tewi-prowlarr-dev sed -n 's|.*<ApiKey>\(.*\)</ApiKey>.*|\1|p' /config/config.xml 2>/dev/null)

test test-all: export TEST_JACKETT_API_KEY ?= $(JACKETT_API_KEY)
test test-all: export TEST_PROWLARR_API_KEY ?= $(PROWLARR_API_KEY)

test:
	uv run python -m pytest -v

test-unit:
	uv run python -m pytest -v -m "not integration"

test-github:
	uv run python -m pytest -v --transmission-port=9092

test-github-min:
	uv run --resolution lowest-direct python -m pytest -v --transmission-port=9092

test-all:
	uv run python -m pytest -v --runxfail

fix:
	uv run ruff format
	uv run ruff check --fix

GEOIP_DATA = src/tewi/util/geoip.dat.gz

clean:
	rm --force dist/*
	rm -rf completions
	rm --force $(GEOIP_DATA)

completions:
	mkdir -p completions/bash
	uv run tewi --print-completion bash > completions/bash/tewi

# Download only if missing, "make clean" removes it to get latest data
geoip: $(GEOIP_DATA)

$(GEOIP_DATA):
	uv run python package/build_geoip.py --output $@

build: check test dist

# Package without lint and tests, used by release workflow. Phony as it's
# also a name of output directory
.PHONY: dist
dist: clean completions geoip
	uv run python -m build

install-pipx:
	$(MAKE) build
	pipx install --force ./dist/tewi_torrent-*-py3-none-any.whl

release-pypi-test: build
	uv run python -m twine upload --repository testpypi dist/*

release-pypi-main: build
	uv run python -m twine upload dist/*

docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-up-full:
	docker compose -f docker/docker-compose.yml --profile search up -d

docker-down:
	docker compose -f docker/docker-compose.yml --profile search down

docker-remove:
	docker compose -f docker/docker-compose.yml --profile search down -v

docker-init:
	./docker/init-torrents.sh

docker-init-full:
	./docker/init-torrents.sh 10

run-transmission:
	PYTHONPATH=src textual run --dev tewi.app:create_app -- --client-type transmission --port 9070

run-qbittorrent:
	PYTHONPATH=src textual run --dev tewi.app:create_app -- --client-type qbittorrent --port 9071 --username admin --password $$(docker logs tewi-qbittorrent-dev 2>&1 | grep 'temporary password' | tail -1 | sed 's/.*: //')

run-deluge:
	PYTHONPATH=src textual run --dev tewi.app:create_app -- --client-type deluge --port 9072 --password deluge

run-rtorrent:
	PYTHONPATH=src textual run --dev tewi.app:create_app -- --client-type rtorrent --port 9073 --path /RPC2

auto-test: docker-up docker-init check test-all
	@timeout 5 $(MAKE) run-transmission; status=$$?; [ $$status -eq 124 ] || exit $$status
	@timeout 5 $(MAKE) run-qbittorrent; status=$$?; [ $$status -eq 124 ] || exit $$status
	@timeout 5 $(MAKE) run-deluge; status=$$?; [ $$status -eq 124 ] || exit $$status
	@timeout 5 $(MAKE) run-rtorrent; status=$$?; [ $$status -eq 124 ] || exit $$status
