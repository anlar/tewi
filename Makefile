check:
	ruff check

test:
	python -m pytest -v

test-all:
	python -m pytest -v --runxfail

fix:
	ruff format
	ruff check --fix

clean:
	rm --force dist/*

build: check test clean
	python -m build

install-pipx: build
	pipx install --force ./dist/tewi_transmission-*-py3-none-any.whl

release-pypi-test: build
	python -m twine upload --repository testpypi dist/*

release-pypi-main: build
	python -m twine upload dist/*

docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down

docker-remove:
	docker compose -f docker/docker-compose.yml down -v

docker-init:
	./docker/init-torrents.sh

docker-init-full:
	./docker/init-torrents.sh 10

run-transmission:
	PYTHONPATH=src textual run --dev tewi.app:create_app -- --client-type transmission --port 9092

run-qbittorrent:
	PYTHONPATH=src textual run --dev tewi.app:create_app -- --client-type qbittorrent --port 9093 --username admin --password $$(docker logs tewi-qbittorrent-dev 2>&1 | grep 'temporary password' | tail -1 | sed 's/.*: //')

run-deluge:
	PYTHONPATH=src textual run --dev tewi.app:create_app -- --client-type deluge --port 8112 --password deluge

auto-test: docker-up docker-init check test-all
	@timeout 5 $(MAKE) run-transmission; status=$$?; [ $$status -eq 124 ] || exit $$status
	@timeout 5 $(MAKE) run-qbittorrent; status=$$?; [ $$status -eq 124 ] || exit $$status
	@timeout 5 $(MAKE) run-deluge; status=$$?; [ $$status -eq 124 ] || exit $$status
