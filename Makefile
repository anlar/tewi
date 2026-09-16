check:
	uv run ruff check

test:
	uv run python -m pytest -v

test-github:
	uv run python -m pytest -v --transmission-port=9092

test-all:
	uv run python -m pytest -v --runxfail

fix:
	uv run ruff format
	uv run ruff check --fix

clean:
	rm --force dist/*
	rm -rf completions

completions:
	mkdir -p completions/bash
	uv run tewi --print-completion bash > completions/bash/tewi

build: check test clean completions
	uv run python -m build

install-pipx:
	# temporary disable warning to be able to setup with old Python versions
	# https://github.com/rabuchaim/geoip2fast/issues/16#issuecomment-5677708133
	PYTEST_ADDOPTS='-W "ignore:invalid escape sequence:DeprecationWarning"' $(MAKE) build
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

auto-test: docker-up docker-init check test-all
	@timeout 5 $(MAKE) run-transmission; status=$$?; [ $$status -eq 124 ] || exit $$status
	@timeout 5 $(MAKE) run-qbittorrent; status=$$?; [ $$status -eq 124 ] || exit $$status
	@timeout 5 $(MAKE) run-deluge; status=$$?; [ $$status -eq 124 ] || exit $$status
